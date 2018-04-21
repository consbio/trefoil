"""
Render a set of NetCDF files to images.

Stretched renderers may have one of the following colormap values:
1.0 (absolute)
max (calculate max across datasets)
0.5*max (calculate max across datasets, and multiply by value)

TODO:
* connect palettes to create matching class breaks
* combine palette and scale over which to stretch


"""

import os
import glob
import json
import webbrowser

import numpy
from netCDF4 import Dataset
import click
from pyproj import Proj
from rasterio.crs import CRS
from rasterio.warp import calculate_default_transform
from rasterio.enums import Resampling
from jinja2 import Environment, PackageLoader

from trefoil.render.renderers.utilities import renderer_from_dict
from trefoil.render.renderers.legend import composite_elements
from trefoil.netcdf.variable import SpatialCoordinateVariables
from trefoil.geometry.bbox import BBox
from trefoil.netcdf.warp import warp_array
from trefoil.netcdf.crs import get_crs, is_geographic
from trefoil.cli import cli
from trefoil.cli.utilities import (
    render_image, collect_statistics, colormap_to_stretched_renderer,
    palette_to_stretched_renderer, palette_to_classified_renderer,
    get_leaflet_anchors, get_mask)



# Common defaults for usability wins
DEFAULT_PALETTES = {
    'tmin': ('colorbrewer.sequential.YlOrRd_5', 'min,max'),
    'tmax': ('colorbrewer.sequential.YlOrRd_5', 'min,max'),
    'ppt': ('colorbrewer.diverging.RdYlGn_5', 'min,max'),
    'pet': ('colorbrewer.diverging.RdYlGn_5', 'max,min')
}



@cli.command(short_help="Render netcdf files to images")
@click.argument('filename_pattern')
@click.argument('variable')
@click.argument('output_directory', type=click.Path())
@click.option('--renderer_file', help='File containing renderer JSON', type=click.Path(exists=True))
@click.option('--save', 'save_file', type=click.Path(), default=None, help='Save renderer to renderer_file')
@click.option('--renderer_type', type=click.Choice(['stretched', 'classified']), default='stretched', help='Name of renderer.', show_default=True)
@click.option('--colormap', default=None, help='Provide colormap as comma-separated lookup of value to hex color code.  (Example: -1:#FF0000,1:#0000FF)')
@click.option('--fill', type=click.FLOAT, default=None, help='Fill value (will be rendered as transparent)')
@click.option('--colorspace', default='hsv', type=click.Choice(['hsv', 'rgb']), help='Color interpolation colorspace')
@click.option('--palette', default=None, help='Palettable color palette (Example: colorbrewer.sequential.Blues_3)')
@click.option('--palette_stretch', default='min,max', help='Value range over which to apply the palette when using stretched renderer (comma-separated)', show_default=True)
@click.option('--scale', default=1.0, help='Scale factor for data pixel to screen pixel size')
@click.option('--id_variable', help='ID variable used to provide IDs during image generation.  Must be of same dimensionality as first dimension of variable (example: time).  Guessed from the 3rd dimension')
@click.option('--lh', default=150, help='Height of the legend in pixels [default: 150]')
@click.option('--legend_breaks', default=None, type=click.INT, help='Number of breaks to show on legend for stretched renderer')
@click.option('--legend_ticks', default=None, type=click.STRING, help='Legend tick values for stretched renderer')
@click.option('--legend_precision', default=2, type=click.INT, help='Number of decimal places of precision for legend labels', show_default=True)
@click.option('--format', default='png', type=click.Choice(['png', 'jpg', 'webp']), show_default=True)
# Projection related options
@click.option('--src-crs', '--src_crs', default=None, type=click.STRING, help='Source coordinate reference system (limited to EPSG codes, e.g., EPSG:4326).  Will be read from file if not provided.')
@click.option('--dst-crs', '--dst_crs', default=None, type=click.STRING, help='Destination coordinate reference system')
@click.option('--res', default=None, type=click.FLOAT, help='Destination pixel resolution in destination coordinate system units' )
@click.option('--resampling', default='nearest', type=click.Choice(('nearest', 'cubic', 'lanczos', 'mode')), help='Resampling method for reprojection (default: nearest')
@click.option('--anchors', default=False, is_flag=True, help='Print anchor coordinates for use in Leaflet ImageOverlay')
@click.option('--map', 'interactive_map', default=False, is_flag=True, help='Open in interactive map')
# Other options
@click.option('--mask', 'mask_path', default=None, help='Mask dataset:variable (e.g., mask.nc:mask).  Mask variable assumed to be named "mask" unless otherwise provided')
def render_netcdf(
        filename_pattern,
        variable,
        output_directory,
        renderer_file,
        save_file,
        renderer_type,
        colormap,
        fill,
        colorspace,
        palette,
        palette_stretch,
        scale,
        id_variable,
        lh,
        legend_breaks,
        legend_ticks,
        legend_precision,
        format,
        src_crs,
        dst_crs,
        res,
        resampling,
        anchors,
        interactive_map,
        mask_path):
    """
    Render netcdf files to images.

    colormap is ignored if renderer_file is provided

    --dst-crs is ignored if using --map option (always uses EPSG:3857

    If no colormap or palette is provided, a default palette may be chosen based on the name of the variable.

    If provided, mask must be 1 for areas to be masked out, and 0 otherwise.  It
    must be in the same CRS as the input datasets, and have the same spatial
    dimensions.

    """

    # Parameter overrides
    if interactive_map:
        dst_crs = 'EPSG:3857'

    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='filename_pattern', param_hint='FILENAME_PATTERN')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    mask = get_mask(mask_path) if mask_path is not None else None

    if renderer_file is not None and not save_file:
        if not os.path.exists(renderer_file):
            raise click.BadParameter('does not exist', param='renderer_file', param_hint='renderer_file')

        # see https://bitbucket.org/databasin/ncdjango/wiki/Home for format
        renderer_dict = json.loads(open(renderer_file).read())

        if variable in renderer_dict and not 'colors' in renderer_dict:
            renderer_dict = renderer_dict[variable]

        renderer_type = renderer_dict['type']
        if renderer_type == 'stretched':
            colors = ','.join([str(c[0]) for c in renderer_dict['colors']])
            if 'min' in colors or 'max' in colors or 'mean' in colors:
                statistics = collect_statistics(filenames, (variable,), mask=mask)[variable]
                for entry in renderer_dict['colors']:
                    if isinstance(entry[0], basestring):
                        if entry[0] in ('min', 'max', 'mean'):
                            entry[0] = statistics[entry[0]]
                        elif '*' in entry[0]:
                            rel_value, statistic = entry[0].split('*')
                            entry[0] = float(rel_value) * statistics[statistic]

        renderer = renderer_from_dict(renderer_dict)

    else:

        if renderer_type == 'stretched':
            if palette is not None:
                renderer = palette_to_stretched_renderer(palette, palette_stretch, filenames, variable, fill_value=fill, mask=mask)

            elif colormap is None and variable in DEFAULT_PALETTES:
                palette, palette_stretch = DEFAULT_PALETTES[variable]
                renderer = palette_to_stretched_renderer(palette, palette_stretch, filenames, variable, fill_value=fill, mask=mask)

            else:
                if colormap is None:
                    colormap = 'min:#000000,max:#FFFFFF'
                renderer = colormap_to_stretched_renderer(colormap, colorspace, filenames, variable, fill_value=fill, mask=mask)

        elif renderer_type == 'classified':
            if not palette:
                raise click.BadParameter('palette required for classified (for now)',
                                         param='--palette', param_hint='--palette')

            renderer = palette_to_classified_renderer(palette, filenames, variable, method='equal', fill_value=fill, mask=mask)  # TODO: other methods

    if save_file:

        if os.path.exists(save_file):
            with open(save_file, 'r+') as output_file:
                data = json.loads(output_file.read())
                output_file.seek(0)
                output_file.truncate()
                data[variable] = renderer.serialize()
                output_file.write(json.dumps(data, indent=4))
        else:
            with open(save_file, 'w') as output_file:
                output_file.write(json.dumps({variable: renderer.serialize()}))

    if renderer_type == 'stretched':
        if legend_ticks is not None and not legend_breaks:
            legend_ticks = [float(v) for v in legend_ticks.split(',')]

        legend = renderer.get_legend(image_height=lh, breaks=legend_breaks, ticks=legend_ticks, max_precision=legend_precision)[0].to_image()

    elif renderer_type == 'classified':
        legend = composite_elements(renderer.get_legend())

    legend.save(os.path.join(output_directory, '{0}_legend.png'.format(variable)))

    with Dataset(filenames[0]) as ds:
        var_obj = ds.variables[variable]
        dimensions = var_obj.dimensions
        shape = var_obj.shape
        num_dimensions = len(shape)

        if num_dimensions == 3:
            if id_variable:
                if shape[0] != ds.variables[id_variable][:].shape[0]:
                    raise click.BadParameter('must be same dimensionality as 3rd dimension of {0}'.format(variable),
                                             param='--id_variable', param_hint='--id_variable')
            else:
                # Guess from the 3rd dimension
                guess = dimensions[0]
                if guess in ds.variables and ds.variables[guess][:].shape[0] == shape[0]:
                    id_variable = guess

        ds_crs = get_crs(ds, variable)
        if not ds_crs and is_geographic(ds, variable):
            ds_crs = 'EPSG:4326'  # Assume all geographic data is WGS84

        src_crs = CRS.from_string(ds_crs) if ds_crs else CRS({'init': src_crs}) if src_crs else None

        # get transforms, assume last 2 dimensions on variable are spatial in row, col order
        y_dim, x_dim = dimensions[-2:]
        coords = SpatialCoordinateVariables.from_dataset(
            ds, x_dim, y_dim, projection=Proj(src_crs.to_dict()) if src_crs else None
        )

        if mask is not None and not mask.shape == shape[-2:]:
            # Will likely break before this if collecting statistics
            raise click.BadParameter(
                'mask variable shape does not match shape of input spatial dimensions',
                param='--mask', param_hint='--mask'
            )

        flip_y = False
        reproject_kwargs = None
        if dst_crs is not None:
            if not src_crs:
                raise click.BadParameter('must provide src_crs to reproject',
                                         param='--src-crs',
                                         param_hint='--src-crs')

            dst_crs = CRS.from_string(dst_crs)

            src_height, src_width = coords.shape
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src_crs, dst_crs, src_width, src_height,
                *coords.bbox.as_list(), resolution=res
            )

            reproject_kwargs = {
                'src_crs': src_crs,
                'src_transform': coords.affine,
                'dst_crs': dst_crs,
                'dst_transform': dst_transform,
                'resampling': getattr(Resampling, resampling),
                'dst_shape': (dst_height, dst_width)
            }

        else:
            dst_transform = coords.affine
            dst_height, dst_width = coords.shape
            dst_crs = src_crs

            if coords.y.is_ascending_order():
                # Only needed if we are not already reprojecting the data, since that will flip it automatically
                flip_y = True

        if anchors or interactive_map:
            if not (dst_crs or src_crs):
                raise click.BadParameter('must provide at least src_crs to get Leaflet anchors or interactive map',
                                         param='--src-crs', param_hint='--src-crs')

            leaflet_anchors = get_leaflet_anchors(BBox.from_affine(dst_transform, dst_width, dst_height,
                                                           projection=Proj(dst_crs) if dst_crs else None))

            if anchors:
                click.echo('Anchors: {0}'.format(leaflet_anchors))


    layers = {}
    for filename in filenames:
        with Dataset(filename) as ds:
            click.echo('Processing {0}'.format(filename))

            filename_root = os.path.split(filename)[1].replace('.nc', '')

            if not variable in ds.variables:
                raise click.BadParameter('variable {0} was not found in file: {1}'.format(variable, filename),
                                         param='variable', param_hint='VARIABLE')

            var_obj = ds.variables[variable]
            if not var_obj.dimensions == dimensions:
                raise click.ClickException('All datasets must have the same dimensions for {0}'.format(variable))

            if num_dimensions == 2:
                data = var_obj[:]
                if mask is not None:
                    data = numpy.ma.masked_array(data, mask=mask)
                image_filename = os.path.join(output_directory, '{0}_{1}.{2}'.format(filename_root, variable, format))
                if reproject_kwargs:
                    data = warp_array(data, **reproject_kwargs)
                render_image(renderer, data, image_filename, scale, flip_y=flip_y, format=format)

                local_filename = os.path.split(image_filename)[1]
                layers[os.path.splitext(local_filename)[0]] = local_filename

            elif num_dimensions == 3:
                for index in range(shape[0]):
                    id = ds.variables[id_variable][index] if id_variable is not None else index
                    image_filename = os.path.join(output_directory, '{0}_{1}__{2}.{3}'.format(filename_root, variable, id, format))
                    data = var_obj[index]
                    if mask is not None:
                        data = numpy.ma.masked_array(data, mask=mask)
                    if reproject_kwargs:
                        data = warp_array(data, **reproject_kwargs)
                    render_image(renderer, data, image_filename, scale, flip_y=flip_y, format=format)

                    local_filename = os.path.split(image_filename)[1]
                    layers[os.path.splitext(local_filename)[0]] = local_filename



            # TODO: not tested recently.  Make sure still correct
            # else:
            #     # Assume last 2 components of shape are lat & lon, rest are iterated over
            #     id_variables = None
            #     if id_variable is not None:
            #         id_variables = id_variable.split(',')
            #         for index, name in enumerate(id_variables):
            #             if name:
            #                 assert data.shape[index] == ds.variables[name][:].shape[0]
            #
            #     ranges = []
            #     for dim in data.shape[:-2]:
            #         ranges.append(range(0, dim))
            #     for combined_index in product(*ranges):
            #         id_parts = []
            #         for index, dim_index in enumerate(combined_index):
            #             if id_variables is not None and index < len(id_variables) and id_variables[index]:
            #                 id = ds.variables[id_variables[index]][dim_index]
            #
            #                 if not isinstance(id, basestring):
            #                     if isinstance(id, Iterable):
            #                         id = '_'.join((str(i) for i in id))
            #                     else:
            #                         id = str(id)
            #
            #                 id_parts.append(id)
            #
            #             else:
            #                 id_parts.append(str(dim_index))
            #
            #         combined_id = '_'.join(id_parts)
            #         image_filename = os.path.join(output_directory, '{0}__{1}.{2}'.format(filename_root, combined_id, format))
            #         if reproject_kwargs:
            #             data = warp_array(data, **reproject_kwargs)  # NOTE: lack of index will break this
            #         render_image(renderer, data[combined_index], image_filename, scale, flip_y=flip_y, format=format)
            #
            #         local_filename = os.path.split(image_filename)[1]
            #         layers[os.path.splitext(local_filename)[0]] = local_filename


    if interactive_map:
        index_html = os.path.join(output_directory, 'index.html')
        with open(index_html, 'w') as out:
            template = Environment(loader=PackageLoader('trefoil.cli')).get_template('map.html')
            out.write(
                template.render(
                    layers=json.dumps(layers),
                    bounds=str(leaflet_anchors),
                    variable=variable
                )
            )

        webbrowser.open(index_html)
