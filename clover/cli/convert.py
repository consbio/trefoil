import glob
from netCDF4 import Dataset

import click
from pyproj import Proj
import rasterio
from rasterio import crs

from clover.cli import cli
from clover.netcdf.variable import SpatialCoordinateVariables
from clover.netcdf.crs import set_crs
from clover.netcdf.utilities import get_pack_atts
from clover.geometry.bbox import BBox


@cli.command(short_help='Convert rasters to NetCDF')
@click.argument('files')
@click.argument('output', type=click.Path())
@click.argument('variable', type=click.STRING)
@click.option('--dtype', type=click.Choice(['float32', 'float64', 'int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32']), default=None, help='Data type of output variable.  Will be inferred from input raster if not provided.')
@click.option('--src-crs', default=None, type=click.STRING, help='Source coordinate reference system (limited to EPSG codes, e.g., EPSG:4326).  Will be read from file if not provided.')
@click.option('--x', 'x_name', type=click.STRING, help='Name of x dimension and variable (default: lon or x)')
@click.option('--y', 'y_name', type=click.STRING, help='Name of y dimension and variable (default: lat or y)')
@click.option('--z', 'z_name', type=click.STRING, help='Name of z dimension and variable (e.g., year)')
@click.option('--netcdf3', is_flag=True, default=False, help='Output in NetCDF3 version instead of NetCDF4')
@click.option('--zip', is_flag=True, default=False, help='Use zlib compression of data and coordinate variables')
@click.option('--packed', is_flag=True, default=False, help='Pack floating point values into an integer (will lose precision)')
@click.option('--xy-dtype', type=click.Choice(['float32', 'float64']), default='float32', help='Data type of spatial coordinate variables.', show_default=True)
@click.option('--z-dtype', type=click.Choice(['float32', 'float64', 'int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32']), default=None, help='Data type of z variable.  Will be inferred from values if not provided.')
def to_netcdf(
        files,
        output,
        variable,
        dtype,
        src_crs,
        x_name,
        y_name,
        z_name,
        netcdf3,
        zip,
        packed,
        xy_dtype,
        z_dtype
):
    """
    Convert rasters to NetCDF and stack them according to a dimension.

    X and Y dimension names will be named according to the source projection (lon, lat if geographic projection, x, y
    otherwise) unless specified.

    Will overwrite an existing NetCDF file.
    """


    # TODO: add format string template to this to parse out components
    # Need to be able to sort things in the right order and stack them into the appropriate dimension
    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='files', param_hint='FILES')

    has_z = len(filenames) > 1

    if has_z and not z_name:
        raise click.BadParameter('Required when > 1 input file', param='--z', param_hint='--z')

    if src_crs:
        src_crs = crs.from_string(src_crs)

    with rasterio.open(filenames[0]) as src:
        src_crs = src.crs or src_crs

        if not src_crs:
            raise click.BadParameter('Required when no CRS information available in source files', param='--src-crs',
                                     param_hint='--src_crs')

        prj = Proj(**src_crs)
        coords = SpatialCoordinateVariables.from_bbox(BBox(src.bounds, prj), src.width, src.height, xy_dtype)
        dtype = dtype or src.dtypes[0]
        nodata = src.nodata


    x_name = x_name or ('lon' if crs.is_geographic_crs(src_crs) else 'x')
    y_name = y_name or ('lat' if crs.is_geographic_crs(src_crs) else 'y')

    var_kwargs = {
        'fill_value': nodata
    }

    format = 'NETCDF3_CLASSIC' if netcdf3 else 'NETCDF4'

    with Dataset(output, 'w', format=format) as out:
        coords.add_to_dataset(out, x_name, y_name, zlib=zip)

        var_dimensions = [y_name, x_name]
        shape = list(coords.shape)
        if has_z:
            shape.insert(len(filenames))
            out.createDimension(z_name, shape[0])
            var_dimensions.insert(0, z_name)
            # TODO: create variable.  What type??

        # click.echo('Creating {0}:{1} with shape {2}'.format(output, variable, shape))

        out_var = out.createVariable(variable, dtype, dimensions=var_dimensions,
                                     zlib=zip, **var_kwargs)
        set_crs(out, variable, prj, set_proj4_att=True)

        if packed:
            mins = []
            maxs = []

            click.echo('Collecting statistics for packing data...')
            with click.progressbar(enumerate(filenames)) as items:
                for index, filename in items:
                    with rasterio.open(filename) as src:
                        d = src.read(masked=True)
                        mins.append(d.min())
                        maxs.append(d.max())

            min_value = min(mins)
            max_value = max(maxs)

            scale, offset = get_pack_atts(dtype, min_value, max_value)
            out_var.setncattr('scale_factor', scale)
            out_var.setncattr('add_offset', offset)

        click.echo('Reading input files...')
        with click.progressbar(enumerate(filenames)) as items:
            for index, filename in items:
                with rasterio.open(filename) as src:
                    data = src.read(1, masked=True)

                    if has_z:
                        out_var[index, :] = data
                    else:
                        out_var[:] = data
