"""
Render a set of NetCDF files to images.

Stretched renderers may have one of the following colormap values:
1.0 (absolute)
max (calculate max across datasets)
0.5*max (calculate max across datasets, and multiply by value)
"""

import os
import glob
from itertools import product
from collections import Iterable
import json
from netCDF4 import Dataset

import click
from pyproj import Proj
from rasterio import crs
from rasterio.warp import RESAMPLING, calculate_default_transform
from jinja2 import Environment, PackageLoader
import webbrowser

from clover.render.renderers.utilities import renderer_from_dict
from clover.netcdf.variable import SpatialCoordinateVariables
from clover.geometry.bbox import BBox
from clover.netcdf.warp import warp_array
from clover.netcdf.crs import get_crs, is_geographic
from clover.cli import cli
from clover.cli.utilities import render_image, collect_statistics, colormap_to_stretched_renderer, palette_to_stretched_renderer
from clover.cli.utilities import get_leaflet_anchors


@cli.command(short_help="Render netcdf files to images")
@click.argument('filename_pattern')
@click.argument('variable')
@click.argument('output_directory', type=click.Path())
@click.option('--renderer_file', help='File containing renderer JSON', type=click.Path())
@click.option('--save', default=False, is_flag=True, help='Save renderer to renderer_file')
@click.option('--renderer_type', default='stretched', help='Name of renderer [default: stretched].  (other types not yet implemented)')
@click.option('--colormap', default='min:#000000,max:#FFFFFF', help='Provide colormap as comma-separated lookup of value to hex color code.  (Example: -1:#FF0000,1:#0000FF) [default: min:#000000,max:#FFFFFF]')
@click.option('--colorspace', default='hsv', type=click.Choice(['hsv', 'rgb']), help='Color interpolation colorspace')
@click.option('--palette', default=None, help='Palettable color palette (Example: colorbrewer.sequential.Blues_3)')
@click.option('--scale', default=1.0, help='Scale factor for data pixel to screen pixel size')
@click.option('--id_variable', help='ID variable used to provide IDs during image generation.  Must be of same dimensionality as first dimension of variable (example: time)')
@click.option('--lh', default=150, help='Height of the legend in pixels [default: 150]')
@click.option('--legend_breaks', default=None, type=click.INT, help='Number of breaks to show on legend for stretched renderer')
@click.option('--legend_ticks', default=None, type=click.STRING, help='Legend tick values for stretched renderer')
# Projection related options
@click.option('--src-crs', '--src_crs', default=None, type=click.STRING, help='Source coordinate reference system (limited to EPSG codes, e.g., EPSG:4326).  Will be read from file if not provided.')
@click.option('--dst-crs', '--dst_crs', default=None, type=click.STRING, help='Destination coordinate reference system')
@click.option('--res', default=None, type=click.FLOAT, help='Destination pixel resolution in destination coordinate system units' )
@click.option('--resampling', default='nearest', type=click.Choice(('nearest', 'cubic', 'lanczos', 'mode')), help='Resampling method for reprojection (default: nearest')
@click.option('--anchors', default=False, is_flag=True, help='Print anchor coordinates for use in Leaflet ImageOverlay')
@click.option('--map', 'interactive_map', default=False, is_flag=True, help='Open in interactive map')
def render_netcdf(
        filename_pattern,
        variable,
        output_directory,
        renderer_file,
        save,
        renderer_type,
        colormap,
        colorspace,
        palette,
        scale,
        id_variable,
        lh,
        legend_breaks,
        legend_ticks,
        src_crs,
        dst_crs,
        res,
        resampling,
        anchors,
        interactive_map):
    """
    Render netcdf files to images.

    colormap is ignored if renderer_file is provided

    --dst-crs is ignored if using --map option (always uses EPSG:3857
    """

    # Parameter overrides
    if interactive_map:
        dst_crs = 'EPSG:3857'


    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='filename_pattern', param_hint='FILENAME_PATTERN')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if renderer_file is not None and not save:
        if not os.path.exists(renderer_file):
            raise click.BadParameter('does not exist', param='renderer_file', param_hint='renderer_file')

        # see https://bitbucket.org/databasin/ncdjango/wiki/Home for format
        renderer_dict = json.loads(open(renderer_file).read())

        if variable in renderer_dict and not 'colors' in renderer_dict:
            renderer_dict = renderer_dict[variable]

        if renderer_dict['type'] == 'stretched':
            colors = ','.join([str(c[0]) for c in renderer_dict['colors']])
            if 'min' in colors or 'max' in colors or 'mean' in colors:
                statistics = collect_statistics(filenames, (variable,))[variable]
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
                renderer = palette_to_stretched_renderer(palette, 'min,max', filenames, variable)

            else:
                renderer = colormap_to_stretched_renderer(colormap, colorspace, filenames, variable)
        else:
            raise NotImplementedError('other renderers not yet built')

    if save:
        if not renderer_file:
            raise click.BadParameter('must be provided to save', param='renderer_file', param_hint='renderer_file')

        if os.path.exists(renderer_file):
            with open(renderer_file, 'r+') as output_file:
                data = json.loads(output_file.read())
                output_file.seek(0)
                output_file.truncate()
                data[variable] = renderer.serialize()
                output_file.write(json.dumps(data, indent=4))
        else:
            with open(renderer_file, 'w') as output_file:
                output_file.write(json.dumps({variable: renderer.serialize()}))

    if legend_ticks is not None and not legend_breaks:
        legend_ticks = [float(v) for v in legend_ticks.split(',')]

    legend = renderer.get_legend(image_height=lh, breaks=legend_breaks, ticks=legend_ticks, max_precision=2)[0].to_image()
    legend.save(os.path.join(output_directory, '{0}_legend.png'.format(variable)))

    layers = {}
    for filename in filenames:
        with Dataset(filename) as ds:
            print('Processing',filename)
            filename_root = os.path.split(filename)[1].replace('.nc', '')

            if not variable in ds.variables:
                raise click.BadParameter('variable {0} was not found in file: {1}'.format(variable, filename),
                                         param='variable', param_hint='VARIABLE')

            ds_crs = get_crs(ds, variable)
            if not ds_crs and is_geographic(ds, variable):
                ds_crs = 'EPSG:4326'  # Assume all geographic data is WGS84

            src_crs = crs.from_string(ds_crs) if ds_crs else {'init': src_crs} if src_crs else None

            data = ds.variables[variable][:]
            num_dimensions = len(data.shape)

            # get transforms, assume last 2 dimensions on variable are spatial in row, col order
            y_dim, x_dim = ds.variables[variable].dimensions[-2:]
            coords = SpatialCoordinateVariables.from_dataset(ds, x_dim, y_dim,
                                                             projection=Proj(src_crs) if src_crs else None)

            flip_y = False
            reproject_kwargs = None
            if dst_crs is not None:
                if not src_crs:
                    raise click.BadParameter('must provide src_crs to reproject', param='--src-crs',
                                             param_hint='--src-crs')

                dst_crs = crs.from_string(dst_crs)

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
                    'resampling': getattr(RESAMPLING, resampling),
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
                    print('Anchors: {0}'.format(leaflet_anchors))


            if num_dimensions == 2:
                image_filename = os.path.join(output_directory, '{0}.png'.format(filename_root))
                if reproject_kwargs:
                    data = warp_array(data, **reproject_kwargs)
                render_image(renderer, data, image_filename, scale, flip_y=flip_y)

                local_filename = os.path.split(image_filename)[1]
                layers[local_filename.replace('.png', '')] = local_filename

            elif num_dimensions == 3:
                if id_variable is not None:
                    assert data.shape[0] == ds.variables[id_variable][:].shape[0]

                for index in range(data.shape[0]):
                    id = ds.variables[id_variable][index] if id_variable is not None else index
                    image_filename = os.path.join(output_directory, '{0}__{1}.png'.format(filename_root, id))
                    if reproject_kwargs:
                        data = warp_array(data, **reproject_kwargs)
                    render_image(renderer, data[index], image_filename, scale, flip_y=flip_y)

                local_filename = os.path.split(image_filename)[1]
                layers[local_filename.replace('.png', '')] = local_filename

            else:
                # Assume last 2 components of shape are lat & lon, rest are iterated over
                id_variables = None
                if id_variable is not None:
                    id_variables = id_variable.split(',')
                    for index, name in enumerate(id_variables):
                        if name:
                            assert data.shape[index] == ds.variables[name][:].shape[0]

                ranges = []
                for dim in data.shape[:-2]:
                    ranges.append(range(0, dim))
                for combined_index in product(*ranges):
                    id_parts = []
                    for index, dim_index in enumerate(combined_index):
                        if id_variables is not None and index < len(id_variables) and id_variables[index]:
                            id = ds.variables[id_variables[index]][dim_index]

                            if not isinstance(id, basestring):
                                if isinstance(id, Iterable):
                                    id = '_'.join((str(i) for i in id))
                                else:
                                    id = str(id)

                            id_parts.append(id)

                        else:
                            id_parts.append(str(dim_index))

                    combined_id = '_'.join(id_parts)
                    image_filename = os.path.join(output_directory, '{0}__{1}.png'.format(filename_root, combined_id))
                    if reproject_kwargs:
                        data = warp_array(data, **reproject_kwargs)
                    render_image(renderer, data[combined_index], image_filename, scale, flip_y=flip_y)

                    local_filename = os.path.split(image_filename)[1]
                    layers[local_filename.replace('.png', '')] = local_filename


    if interactive_map:
        index_html = os.path.join(output_directory, 'index.html')
        with open(index_html, 'w') as out:
            template = Environment(loader=PackageLoader('clover.cli')).get_template('map.html')
            out.write(
                template.render(
                    layers=json.dumps(layers),
                    bounds=str(leaflet_anchors),
                    variable=variable
                )
            )

        webbrowser.open(index_html)
