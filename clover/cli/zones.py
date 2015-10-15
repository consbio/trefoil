import click
from pyproj import Proj
from netCDF4 import Dataset
import numpy
import fiona
import rasterio
from rasterio.crs import is_same_crs, from_string
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from rasterio.rio.options import file_in_arg, file_out_arg

from clover.cli import cli
from clover.netcdf.variable import SpatialCoordinateVariables
from clover.netcdf.crs import get_crs, is_geographic
from clover.netcdf.utilities import data_variables, get_fill_value


# TODO: handle string values via a lookup
@cli.command(short_help='Create zones in a NetCDF from features in a shapefile')
@file_in_arg
@file_out_arg
@click.option('--variable', type=click.STRING, default='zones', help='Name of output zones variable', show_default=True)
@click.option('--attribute', type=click.STRING, default=None, help='Name of attribute in shapefile to use for zones (default: feature ID)')
@click.option('--like', help='Template NetCDF dataset', type=click.Path(exists=True), required=True)
@click.option('--netcdf3', is_flag=True, default=False, help='Output in NetCDF3 version instead of NetCDF4')
# @click.option('--all-touched', is_flag=True, default=False, help='Turn all touched pixels into mask (otherwise only pixels with centroid in features)')
@click.option('--zip', is_flag=True, default=False, help='Use zlib compression of data and coordinate variables')
def zones(
    input,
    output,
    variable,
    attribute,
    like,
    netcdf3,
    # all_touched,
    zip):

    """
    Create zones in a NetCDF from features in a shapefile.

    Only handles < 65,536 features for now.

    If --attribute is provided, any features that do not have this will not be assigned to zones.  Text attributes not currently handled correctly.

    Template NetCDF dataset must have a valid projection defined or be inferred from dimensions (e.g., lat / long)
    """

    with Dataset(like) as template_ds:
        template_varname = data_variables(template_ds).keys()[0]
        template_variable = template_ds.variables[template_varname]
        template_crs = get_crs(template_ds, template_varname)

        if template_crs:
            template_crs = from_string(template_crs)
        elif is_geographic(template_ds, template_varname):
            template_crs = {'init': 'EPSG:4326'}
        else:
            raise click.UsageError('template dataset must have a valid projection defined')

        spatial_dimensions = template_variable.dimensions[-2:]
        out_shape = template_variable.shape[-2:]

        template_y_name, template_x_name = spatial_dimensions
        coords = SpatialCoordinateVariables.from_dataset(
            template_ds,
            x_name=template_x_name,
            y_name=template_y_name,
            projection=Proj(**template_crs)
        )


    with fiona.open(input, 'r') as shp:
        if attribute:
            if not attribute in shp.meta['schema']['properties']:
                raise click.BadParameter('{0} not found in dataset'.format(attribute),
                                         param='--attribute', param_hint='--attribute')

            att_dtype = shp.meta['schema']['properties'][attribute].split(':')[0]
            if not att_dtype == 'int':
                raise click.BadParameter('integer attribute required'.format(attribute),
                                         param='--attribute', param_hint='--attribute')

        # TODO: set dtype dynamically!
        dtype = numpy.dtype('uint16')
        fill_value = get_fill_value(dtype)
        transform_required = not is_same_crs(shp.crs, template_crs)
        geometries = []
        values = []

        # Project bbox for filtering
        bbox = coords.bbox
        if transform_required:
            bbox = bbox.project(Proj(**shp.crs), edge_points=21)

        for f in shp.filter(bbox=bbox.as_list()):  # TODO: apply this to mask
            value = f['properties'].get(attribute) if attribute else int(f['id'])
            if value is not None:
                geom = f['geometry']
                if transform_required:
                    geom = transform_geom(shp.crs, template_crs, geom)

                values.append(value)
                geometries.append((geom, value))
            # Otherwise, these will not be rasterized

        click.echo('Rasterizing {0} features into zones'.format(len(geometries)))

        # TODO: data type range checks!

    with rasterio.drivers():
        zones = rasterize(
            geometries,
            out_shape=out_shape,
            transform=coords.affine,
            all_touched=False,  #TODO: revisit this
            fill=fill_value,
            dtype=dtype
        )
        # TODO: convert fill value to mask!

        zones = numpy.ma.masked_array(zones, mask=(zones == fill_value))

    format = 'NETCDF3_CLASSIC' if netcdf3 else 'NETCDF4'
    out_dtype = dtype
    if netcdf3:
        if dtype == numpy.uint16:
            out_dtype = numpy.dtype('int32')
        elif dtype == numpy.uint8:
          out_dtype = numpy.dtype('int16')

    with Dataset(output, 'w', format=format) as out:
        coords.add_to_dataset(out, template_x_name, template_y_name)
        out_var = out.createVariable(variable, out_dtype,
                                     dimensions=spatial_dimensions,
                                     zlib=zip,
                                     fill_value=get_fill_value(out_dtype))
        out_var[:] = zones
