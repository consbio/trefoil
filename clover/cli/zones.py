import csv
import glob
import os
import time

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


@cli.command(short_help='Create zones in a NetCDF from features in a shapefile')
@file_in_arg
@file_out_arg
@click.option('--variable', type=click.STRING, default='zone', help='Name of output zones variable', show_default=True)
@click.option('--attribute', type=click.STRING, default=None, help='Name of attribute in shapefile to use for zones (default: feature ID)')
@click.option('--like', help='Template NetCDF dataset', type=click.Path(exists=True), required=True)
@click.option('--netcdf3', is_flag=True, default=False, help='Output in NetCDF3 version instead of NetCDF4')
@click.option('--zip', is_flag=True, default=False, help='Use zlib compression of data and coordinate variables')
def zones(
    input,
    output,
    variable,
    attribute,
    like,
    netcdf3,
    zip):

    """
    Create zones in a NetCDF from features in a shapefile.  This is intended
    to be used as input to zonal statistics functions; it is not intended
    as a direct replacement for rasterizing geometries into NetCDF.

    Only handles < 65,535 features for now.

    If --attribute is provided, any features that do not have this will not be
    assigned to zones.

    A values lookup will be used to store values.  The zones are indices of
    the unique values encountered when extracting features.
    The original values are stored in an additional variable with the name of
    the zones variable plus '_values'.

    Template NetCDF dataset must have a valid projection defined or be inferred
    from dimensions (e.g., lat / long)
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
            if not att_dtype in ('int', 'str'):
                raise click.BadParameter('integer or string attribute required'.format(attribute),
                                         param='--attribute', param_hint='--attribute')

        transform_required = not is_same_crs(shp.crs, template_crs)
        geometries = []
        values = set()
        values_lookup = {}

        # Project bbox for filtering
        bbox = coords.bbox
        if transform_required:
            bbox = bbox.project(Proj(**shp.crs), edge_points=21)

        index = 0
        for f in shp.filter(bbox=bbox.as_list()):
            value = f['properties'].get(attribute) if attribute else int(f['id'])
            if value is not None:
                geom = f['geometry']
                if transform_required:
                    geom = transform_geom(shp.crs, template_crs, geom)

                geometries.append((geom, index))

                if not value in values:
                    values.add(value)
                    values_lookup[index] = value
                    index += 1

            # Otherwise, these will not be rasterized

        num_geometries = len(geometries)
        # Save a slot at the end for nodata
        if num_geometries < 255:
            dtype = numpy.dtype('uint8')
        elif num_geometries < 65535:
            dtype = numpy.dtype('uint16')
        else:
            raise click.Abort('Too many features to rasterize: {0}, aborting...'.format(num_geometries))

        fill_value = get_fill_value(dtype)

        click.echo('Rasterizing {0} features into zones'.format(num_geometries))

    with rasterio.drivers():
        zones = rasterize(
            geometries,
            out_shape=out_shape,
            transform=coords.affine,
            all_touched=False, # True produces undesirable results for adjacent polygons
            fill=fill_value,
            dtype=dtype
        )

    format = 'NETCDF4'
    out_dtype = dtype
    if netcdf3:
        format = 'NETCDF3_CLASSIC'
        if dtype == numpy.uint8:
            out_dtype = numpy.dtype('int16')
        elif dtype == numpy.uint16:
            out_dtype = numpy.dtype('int32')

        # Have to convert fill_value to mask since we changed data type
        zones = numpy.ma.masked_array(zones, mask=(zones == fill_value))


    with Dataset(output, 'w', format=format) as out:
        coords.add_to_dataset(out, template_x_name, template_y_name)
        out_var = out.createVariable(variable, out_dtype,
                                     dimensions=spatial_dimensions,
                                     zlib=zip,
                                     fill_value=get_fill_value(out_dtype))
        out_var[:] = zones

        out_values = numpy.array([values_lookup[k] for k in range(0, len(values_lookup))])
        values_varname = '{0}_values'.format(variable)
        out.createDimension(values_varname, len(out_values))
        values_var = out.createVariable(values_varname, out_values.dtype,
                                        dimensions=(values_varname, ),
                                        zlib=zip)
        values_var[:] = out_values



@cli.command(short_help='Calculate zonal statistics')
@click.argument('zones', type=click.Path(exists=True))
@click.argument('filename_pattern')
@click.argument('output', type=click.Path())
@click.option('--variables',  type=click.STRING, default=None, help='Comma-separated list of variables (if not provided, will use all data variables)')
@click.option('--statistics', type=click.STRING, default='avg', help='Comma-separated list of statistics (one of: avg,min,max)', show_default=True)
# TODO: consider using shorthand notation for zones:zone_variable instead
@click.option('--zone_variable', type=click.STRING, default='zone', help='Name of output zones variable', show_default=True)
# TODO: output format?  CSV vs JSON?  Can infer from filename
# TODO: precision
def zonal_stats(
    zones,
    filename_pattern,
    output,
    variables,
    statistics,
    zone_variable):

    start = time.time()

    statistics = statistics.split(',')  # TODO: validate


    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='filename_pattern', param_hint='FILENAME_PATTERN')

    with Dataset(zones) as zones_ds:
        if not zone_variable in zones_ds.variables:
            raise click.BadParameter(
                'zone variable not found: {0}'.format(zone_variable),
                 param='--zone_variable', param_hint='--zone_variable'
            )

        values_variable = '{0}_values'.format(zone_variable)
        if not values_variable in zones_ds.variables:
            raise click.BadParameter(
                'zone values variable not found: {0}_values'.format(zone_variable),
                 param='--zone_variable', param_hint='--zone_variable'
            )

        zones = zones_ds.variables[zone_variable][:]
        zone_values = zones_ds.variables[values_variable][:]

    with Dataset(filenames[0]) as ds:
        variables = variables.split(',') if variables is not None else list(data_variables(ds).keys())
        if set(variables).difference(ds.variables.keys()):
            raise click.BadParameter('One or more variables were not found in {0}'.format(filenames[0]),
                                     param='--variables', param_hint='--variables')

        var_obj = ds.variables[variables[0]]
        dimensions = var_obj.dimensions
        shape = var_obj.shape
        num_dimensions = len(shape)
        if not var_obj.shape[-2:] == zones.shape:
            raise click.Abort('All datasets must have same shape for last 2 dimensions as zones')
        if num_dimensions > 3:
            raise click.Abort('This does not handle > 3 dimensions')
        elif num_dimensions == 3:
            z_values = ds.variables[dimensions[0]][:]

    with open(output, 'wb') as outfile:
        writer = csv.writer(outfile)
        header = ['filename', 'variable']
        if num_dimensions == 3:
            header += [dimensions[0]]
        header += ['zone'] + statistics
        writer.writerow(header)

        for filename in filenames:
            with Dataset(filename) as ds:
                click.echo('Processing {0}'.format(filename))

                if set(variables).difference(ds.variables.keys()):
                    raise click.BadParameter('One or more variables were not found in {0}'.format(filename),
                                             param='--variables', param_hint='--variables')

                for variable in variables:
                    var_obj = ds.variables[variable]

                    if not var_obj.dimensions[:] == dimensions:
                        raise click.Abort('All datasets must have the same dimensions for {0}'.format(variable))

                    filename_root = os.path.split(filename)[1].replace('.nc', '')

                    if num_dimensions == 3:
                        for z_idx in range(shape[0]):
                            # TODO: actually need to resolve z_idx to a time value in time variable!
                            z_value = z_values[z_idx]  # TODO: may need to convert time to better units!

                            data = numpy.ma.masked_array(var_obj[z_idx])
                            for zone_idx in range(0, zone_values.shape[0]):
                                masked = numpy.ma.masked_array(data, mask=data.mask | (zones==zone_idx))

                                # skip if all pixels are masked
                                if masked.mask.min() == True:
                                    continue

                                row = [filename_root, variable, z_value, zone_values[zone_idx]]
                                for stat in statistics:
                                    result = ''
                                    if stat == 'avg':
                                        result = masked.mean().item()
                                    elif stat == 'min':
                                        result = masked.min().item()
                                    elif stat == 'max':
                                        result = masked.max().item()
                                    row.append(result)

                                writer.writerow(row)


                            # Alternative using axis, may run out of memory!  Was slower!
                            # data = numpy.ma.masked_array(var_obj[:])
                            # data = data.reshape(data.shape[0], numpy.product(data.shape[1:]))
                            # flat_zones = zones.flat
                            # for zone_idx in range(0, zone_values.shape[0]):
                            #     masked = numpy.ma.masked_array(data, mask=data.mask | (flat_zones == zone_idx))
                            #     means = masked.mean(axis=1)
                                # TODO
                                # row = [filename_root, variable, z_idx, zone_values[zone_idx]]
                                # for stat in statistics:
                                #     result = ''
                                #     if stat == 'avg':
                                #         result = masked.mean()
                                #     elif stat == 'min':
                                #         result = masked.min()
                                #     elif stat == 'max':
                                #         result = masked.max()
                                #     row.append(result)

                                # writer.writerow(row)

                    else:
                        raise NotImplementedError('TODO')

    click.echo('Elapsed: {0:.2f}'.format(time.time() - start))