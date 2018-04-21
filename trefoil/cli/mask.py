import click
from pyproj import Proj
from netCDF4 import Dataset
import numpy
import fiona
import rasterio
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from rasterio.rio.options import file_in_arg, file_out_arg

from trefoil.cli import cli
from trefoil.netcdf.variable import SpatialCoordinateVariables
from trefoil.netcdf.crs import get_crs, is_geographic
from trefoil.netcdf.utilities import data_variables, get_fill_value


@cli.command(short_help='Create a NetCDF mask from a shapefile')
@file_in_arg
@file_out_arg
@click.option('--variable', type=click.STRING, default='mask', help='Name of output mask variable', show_default=True)
@click.option('--like', help='Template NetCDF dataset', type=click.Path(exists=True), required=True)
@click.option('--netcdf3', is_flag=True, default=False, help='Output in NetCDF3 version instead of NetCDF4')
@click.option('--all-touched', is_flag=True, default=False, help='Turn all touched pixels into mask (otherwise only pixels with centroid in features)')
@click.option('--invert', is_flag=True, default=False, help='Create inverted mask (opposite of numpy mask, True where there are features)')
@click.option('--zip', is_flag=True, default=False, help='Use zlib compression of data and coordinate variables')
# TODO: add option to create a mask for each feature
def mask(
    input,
    output,
    variable,
    like,
    netcdf3,
    all_touched,
    invert,
    zip):

    """
    Create a NetCDF mask from a shapefile.

    Values are equivalent to a numpy mask: 0 for unmasked areas, and 1 for masked areas.

    Template NetCDF dataset must have a valid projection defined or be inferred from dimensions (e.g., lat / long)
    """

    with Dataset(like) as template_ds:
        template_varname = data_variables(template_ds).keys()[0]
        template_variable = template_ds.variables[template_varname]
        template_crs = get_crs(template_ds, template_varname)

        if template_crs:
            template_crs = CRS.from_string(template_crs)
        elif is_geographic(template_ds, template_varname):
            template_crs = CRS({'init': 'EPSG:4326'})
        else:
            raise click.UsageError('template dataset must have a valid projection defined')

        spatial_dimensions = template_variable.dimensions[-2:]
        mask_shape = template_variable.shape[-2:]

        template_y_name, template_x_name = spatial_dimensions
        coords = SpatialCoordinateVariables.from_dataset(
            template_ds,
            x_name=template_x_name,
            y_name=template_y_name,
            projection=Proj(**template_crs.to_dict())
        )


    with fiona.open(input, 'r') as shp:
        transform_required = CRS(shp.crs) != template_crs

        # Project bbox for filtering
        bbox = coords.bbox
        if transform_required:
            bbox = bbox.project(Proj(**shp.crs), edge_points=21)

        geometries = []
        for f in shp.filter(bbox=bbox.as_list()):
            geom = f['geometry']
            if transform_required:
                geom = transform_geom(shp.crs, template_crs, geom)

            geometries.append(geom)

    click.echo('Converting {0} features to mask'.format(len(geometries)))

    if invert:
        fill_value = 0
        default_value = 1
    else:
        fill_value = 1
        default_value = 0

    with rasterio.Env():
        # Rasterize features to 0, leaving background as 1
        mask = rasterize(
            geometries,
            out_shape=mask_shape,
            transform=coords.affine,
            all_touched=all_touched,
            fill=fill_value,
            default_value=default_value,
            dtype=numpy.uint8
        )

    format = 'NETCDF3_CLASSIC' if netcdf3 else 'NETCDF4'
    dtype = 'int8' if netcdf3 else 'uint8'

    with Dataset(output, 'w', format=format) as out:
        coords.add_to_dataset(out, template_x_name, template_y_name)
        out_var = out.createVariable(variable, dtype, dimensions=spatial_dimensions, zlib=zip,
                                     fill_value=get_fill_value(dtype))
        out_var[:] = mask
