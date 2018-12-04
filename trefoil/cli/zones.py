import csv
import glob
import os
import time
import json

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
from trefoil.analysis.summary import VALID_ZONAL_STATISTICS, calculate_zonal_statistics
from trefoil.netcdf.variable import SpatialCoordinateVariables
from trefoil.netcdf.crs import get_crs, is_geographic
from trefoil.netcdf.utilities import data_variables, get_fill_value


@cli.command(short_help='Create zones in a NetCDF from features in a shapefile')
@click.argument('input', type=click.Path(exists=True))
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
    from dimensions (e.g., lat / long).
    """

    with Dataset(like) as template_ds:
        template_varname = list(data_variables(template_ds).keys())[0]
        template_variable = template_ds.variables[template_varname]
        template_crs = get_crs(template_ds, template_varname)

        if template_crs:
            template_crs = CRS.from_string(template_crs)
        elif is_geographic(template_ds, template_varname):
            template_crs = CRS({'init': 'EPSG:4326'})
        else:
            raise click.UsageError('template dataset must have a valid projection defined')

        spatial_dimensions = template_variable.dimensions[-2:]
        out_shape = template_variable.shape[-2:]

        template_y_name, template_x_name = spatial_dimensions
        coords = SpatialCoordinateVariables.from_dataset(
            template_ds,
            x_name=template_x_name,
            y_name=template_y_name,
            projection=Proj(**template_crs.to_dict())
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

        transform_required = CRS(shp.crs) != template_crs
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
            raise click.UsageError('Too many features to rasterize: {0}, Exceptioning...'.format(num_geometries))

        fill_value = get_fill_value(dtype)

        click.echo('Rasterizing {0} features into zones'.format(num_geometries))

    with rasterio.Env():
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
        values_varname = '{0}_values'.format(variable)
        coords.add_to_dataset(out, template_x_name, template_y_name)
        out_var = out.createVariable(variable, out_dtype,
                                     dimensions=spatial_dimensions,
                                     zlib=zip,
                                     fill_value=get_fill_value(out_dtype))
        out_var.setncattr('values', values_varname)
        out_var[:] = zones

        out_values = numpy.array([values_lookup[k] for k in range(0, len(values_lookup))])
        if netcdf3 and out_values.dtype == numpy.int64:
            out_values = out_values.astype('int32')

        out.createDimension(values_varname, len(out_values))
        values_var = out.createVariable(values_varname, out_values.dtype,
                                        dimensions=(values_varname, ),
                                        zlib=zip)
        values_var[:] = out_values


@cli.command(short_help='Calculate zonal statistics for a series of NetCDF files')
@click.argument('zones', type=click.Path(exists=True))
@click.argument('filename_pattern')
@click.argument('output', type=click.Path())
@click.option('--variables',  type=click.STRING, default=None, help='Comma-separated list of variables (if not provided, will use all data variables)')
@click.option('--statistics', type=click.STRING, default='mean', help='Comma-separated list of statistics (available: mean,min,max,std,sum,count)', show_default=True)
# TODO: consider using shorthand notation for zones:zone_variable instead
@click.option('--zone_variable', type=click.STRING, default='zone', help='Name of output zones variable', show_default=True)
# TODO: precision
def zonal_stats(
    zones,
    filename_pattern,
    output,
    variables,
    statistics,
    zone_variable):

    """
    Calculate zonal statistics for a series of NetCDF files.

    Zones must be created using the 'zones' command.

    The output file can either be a CSV (recommended) or JSON format file, which
    is automatically determined from the file extension of the output filename.

    See docs/cli.md for more information about output format.
    """

    start = time.time()

    if variables:
        variables = variables.split(',')

    statistics = statistics.split(',')
    if set(statistics).difference(VALID_ZONAL_STATISTICS):
        raise click.BadParameter(
            'One or more statistics is not supported {0}'.format(statistics),
             param='--statistics', param_hint='--statistics'
        )

    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter(
            'No files found matching that pattern',
             param='filename_pattern', param_hint='FILENAME_PATTERN'
        )

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
        if variables is not None:
            if set(variables).difference(ds.variables.keys()):
                raise click.BadParameter(
                    'One or more variables were not found in {0}'.format(filenames[0]),
                     param='--variables', param_hint='--variables'
                )
            first_variable = variables[0]

        else:
            first_variable = list(data_variables(ds).keys())[0]

        var_obj = ds.variables[first_variable]
        dimensions = var_obj.dimensions
        shape = var_obj.shape
        num_dimensions = len(shape)
        if not var_obj.shape[-2:] == zones.shape:
            raise click.UsageError(
                'All datasets must have same shape for last 2 dimensions as zones')
        if num_dimensions > 3:
            raise click.UsageError('This does not handle > 3 dimensions')
        elif num_dimensions == 3:
            z_values = ds.variables[dimensions[0]][:]

    results = {}
    for filename in filenames:
        with Dataset(filename) as ds:
            filename_root = os.path.split(filename)[1].replace('.nc', '')

            click.echo('Processing {0}'.format(filename))

            if variables is not None and set(variables).difference(ds.variables.keys()):
                raise click.BadParameter(
                    'One or more variables were not found in {0}'.format(filenames[0]),
                     param='--variables', param_hint='--variables'
                )

            results[filename_root] = dict()
            for variable in (variables or list(data_variables(ds).keys())):
                var_obj = ds.variables[variable]

                if not var_obj.dimensions[:] == dimensions:
                    raise click.UsageError(
                        'All datasets must have the same dimensions for {0}'.format(variable))

                if num_dimensions == 3:
                    results[filename_root][variable] = dict()

                    for z_idx in range(shape[0]):
                        z_value = z_values[z_idx].item()  # TODO: actually need to resolve z_idx to a time value in time variable!
                        data = numpy.ma.masked_array(var_obj[z_idx])
                        results[filename_root][variable][z_value] = calculate_zonal_statistics(zones, zone_values, data, statistics)

                    # this way works too, but may run out of memory
                    # output below would need to be updated to use this though
                    # data = numpy.ma.masked_array(var_obj[:])
                    # results[filename_root][variable] = calculate_zonal_statistics(zones, zone_values, data, statistics)

                else:
                    data = numpy.ma.masked_array(var_obj[:])
                    results[filename_root][variable] = calculate_zonal_statistics(zones, zone_values, data, statistics)

    with open(output, 'wb') as outfile:
        if os.path.splitext(output)[1] == '.json':
            outfile.write(json.dumps(results, indent=2))
        else:
            writer = csv.writer(outfile)
            header = ['filename', 'variable']
            if num_dimensions == 3:
                header += [dimensions[0]]
            header += ['zone'] + statistics
            writer.writerow(header)

            rows = []

            for filename in results:
                for variable in results[filename]:
                    if num_dimensions == 3:
                        for z_value in results[filename][variable]:
                            for zone in results[filename][variable][z_value]:
                                result = results[filename][variable][z_value][zone]
                                rows.append([filename, variable, z_value, zone] + [result[stat] for stat in statistics])
                    else:
                        for zone in results[filename][variable]:
                            result = results[filename][variable][zone]
                            rows.append([filename, variable, zone] + [result[stat] for stat in statistics])

            for row in rows:
                writer.writerow(row)

    click.echo('Elapsed: {0:.2f}'.format(time.time() - start))
