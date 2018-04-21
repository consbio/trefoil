import os
import tempfile
import json
import webbrowser
from netCDF4 import Dataset
import click
from pyproj import Proj
from rasterio.crs import CRS
from rasterio.warp import calculate_default_transform
from rasterio.enums import Resampling
from jinja2 import Environment, PackageLoader

from trefoil.netcdf.variable import SpatialCoordinateVariables
from trefoil.geometry.bbox import BBox
from trefoil.netcdf.warp import warp_array
from trefoil.netcdf.crs import get_crs, is_geographic
from trefoil.cli import cli
from trefoil.cli.utilities import render_image, palette_to_stretched_renderer, get_leaflet_anchors


# Requires EEMS installed from: https://github.com/MikeTheReader/EEMS
# TWSAndExplorer branch, v2.0.1
# imported inline below



# Common defaults for usability wins
DEFAULT_PALETTES = {
    'fuzzy': 'colorbrewer.diverging.Spectral_5',
    'raw': 'colorbrewer.sequential.Greys_5'
}


@cli.command(short_help="Render a NetCDF EEMS model to a web map")
@click.argument('EEMS_FILE', type=click.Path(exists=True))
# @click.argument('output_directory', type=click.Path())  # TODO: temp file instead?
@click.option('--scale', default=1.0, help='Scale factor for data pixel to screen pixel size')
@click.option('--format', default='png', type=click.Choice(['png', 'jpg', 'webp']), show_default=True)
# Projection related options
@click.option('--src-crs', '--src_crs', default=None, type=click.STRING, help='Source coordinate reference system (limited to EPSG codes, e.g., EPSG:4326).  Will be read from file if not provided.')
@click.option('--resampling', default='nearest', type=click.Choice(('nearest', 'cubic', 'lanczos', 'mode')), help='Resampling method for reprojection (default: nearest')
def map_eems(
        eems_file,
        # output_directory,
        scale,
        format,
        src_crs,
        resampling):
    """
    Render a NetCDF EEMS model to a web map.
    """

    from EEMSBasePackage import EEMSCmd, EEMSProgram


    model = EEMSProgram(eems_file)

    # For each data producing command, store the netcdf file that contains it
    file_vars = dict()
    raw_variables = set()
    for cmd in model.orderedCmds:  # This is bottom up, may want to invert
        filename = None
        variable = None
        if cmd.HasResultName():
            filename = cmd.GetParam('OutFileName')
            variable = cmd.GetResultName()
        elif cmd.IsReadCmd():
            filename = cmd.GetParam('OutFileName')
            variable = cmd.GetParam('NewFieldName')
            raw_variables.add(variable)

        if filename and variable:
            if not filename in file_vars:
                file_vars[filename] = []
            file_vars[filename].append(variable)


    filenames =file_vars.keys()
    for filename in filenames:
        if not os.path.exists(filename):
            raise click.ClickException('Could not find data file from EEMS model: {0}'.format(filename))


    dst_crs = 'EPSG:3857'

    output_directory = tempfile.mkdtemp()
    click.echo('Using temp directory: {0}'.format(output_directory))
    # if not os.path.exists(output_directory):
    #     os.makedirs(output_directory)

    # Since fuzzy renderer is hardcoded, we can output it now
    fuzzy_renderer = palette_to_stretched_renderer(DEFAULT_PALETTES['fuzzy'], '1,-1')
    fuzzy_renderer.get_legend(image_height=150)[0].to_image().save(os.path.join(output_directory, 'fuzzy_legend.png'))

    template_filename = filenames[0]
    template_var = file_vars[template_filename][0]
    with Dataset(template_filename) as ds:
        var_obj = ds.variables[template_var]
        dimensions = var_obj.dimensions
        shape = var_obj.shape
        num_dimensions = len(shape)
        if num_dimensions != 2:
            raise click.ClickException('Only 2 dimensions are allowed on data variables for now')

        ds_crs = get_crs(ds, template_var)
        if not ds_crs and is_geographic(ds, template_var):
            ds_crs = 'EPSG:4326'  # Assume all geographic data is WGS84

        src_crs = CRS.from_string(ds_crs) if ds_crs else CRS({'init': src_crs}) if src_crs else None

        # get transforms, assume last 2 dimensions on variable are spatial in row, col order
        y_dim, x_dim = dimensions[-2:]
        coords = SpatialCoordinateVariables.from_dataset(
            ds, x_dim, y_dim, projection=Proj(src_crs) if src_crs else None
        )
    #
    #     if mask is not None and not mask.shape == shape[-2:]:
    #         # Will likely break before this if collecting statistics
    #         raise click.BadParameter(
    #             'mask variable shape does not match shape of input spatial dimensions',
    #             param='--mask', param_hint='--mask'
    #         )
    #
        if not src_crs:
            raise click.BadParameter('must provide src_crs to reproject',
                                     param='--src-crs',
                                     param_hint='--src-crs')

        dst_crs = CRS.from_string(dst_crs)

        src_height, src_width = coords.shape
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs, dst_crs, src_width, src_height,
            *coords.bbox.as_list()
        )

        reproject_kwargs = {
            'src_crs': src_crs,
            'src_transform': coords.affine,
            'dst_crs': dst_crs,
            'dst_transform': dst_transform,
            'resampling': getattr(Resampling, resampling),
            'dst_shape': (dst_height, dst_width)
        }

        if not (dst_crs or src_crs):
            raise click.BadParameter('must provide valid src_crs to get interactive map',
                                     param='--src-crs', param_hint='--src-crs')

        leaflet_anchors = get_leaflet_anchors(BBox.from_affine(dst_transform, dst_width, dst_height,
                                                       projection=Proj(dst_crs) if dst_crs else None))


    layers = {}
    for filename in filenames:
        with Dataset(filename) as ds:
            click.echo('Processing dataset {0}'.format(filename))

            for variable in file_vars[filename]:
                click.echo('Processing variable {0}'.format(variable))

                if not variable in ds.variables:
                    raise click.ClickException('variable {0} was not found in file: {1}'.format(variable, filename))

                var_obj = ds.variables[variable]
                if not var_obj.dimensions == dimensions:
                    raise click.ClickException('All datasets must have the same dimensions for {0}'.format(variable))

                data = var_obj[:]
                # if mask is not None:
                #     data = numpy.ma.masked_array(data, mask=mask)


                if variable in raw_variables:
                    palette = DEFAULT_PALETTES['raw']
                    palette_stretch = '{0},{1}'.format(data.max(), data.min())

                    renderer = palette_to_stretched_renderer(palette, palette_stretch)
                    renderer.get_legend(image_height=150, max_precision=2)[0].to_image().save(os.path.join(output_directory, '{0}_legend.png'.format(variable)))
                else:
                    renderer = fuzzy_renderer

                image_filename = os.path.join(output_directory, '{0}.{1}'.format(variable, format))
                data = warp_array(data, **reproject_kwargs)
                render_image(renderer, data, image_filename, scale=scale, format=format)

                local_filename = os.path.split(image_filename)[1]
                layers[variable] = local_filename


    index_html = os.path.join(output_directory, 'index.html')
    with open(index_html, 'w') as out:
        template = Environment(loader=PackageLoader('trefoil.cli')).get_template('eems_map.html')
        out.write(
            template.render(
                layers=json.dumps(layers),
                bounds=str(leaflet_anchors),
                tree=[[cmd, depth] for (cmd, depth) in model.GetCmdTree()],
                raw_variables=list(raw_variables)
            )
        )

    webbrowser.open(index_html)
