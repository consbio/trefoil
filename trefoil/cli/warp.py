import os
import glob
from netCDF4 import Dataset

import click
from rasterio.enums import Resampling

from trefoil.cli import cli
from trefoil.netcdf.warp import warp_like
from trefoil.netcdf.crs import get_crs
from trefoil.netcdf.utilities import data_variables


@cli.command(short_help="Warp NetCDF files to match a template")
@click.argument('filename_pattern')
@click.argument('output_directory', type=click.Path())
@click.option('--variables', help='comma-delimited list of variables to warp.  Default: all data variables', default=None)
@click.option('--src-crs', help='Source Coordinate Reference System (only used if none found in source dataset)',
              default='EPSG:4326', show_default=True)
@click.option('--like', help='Template dataset', type=click.Path(exists=True), required=True)  # Required for now
@click.option('--resampling', default='nearest',
              type=click.Choice(('nearest', 'cubic', 'lanczos', 'mode')),
              help='Resampling method for reprojection', show_default=True)
def warp(
    filename_pattern,
    output_directory,
    variables,
    src_crs,
    like,
    resampling):

    if variables:
        variables = variables.strip().split(',')

    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='filename_pattern', param_hint='FILENAME_PATTERN')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # For now, template dataset is required
    template_ds = Dataset(like)
    template_varname = data_variables(template_ds).keys()[0]

    for filename in filenames:
        with Dataset(filename) as ds:
            if not variables:
                ds_variables = data_variables(ds).keys()
            else:
                # filter to only variables present in this dataset
                ds_variables = [v for v in variables if v in ds.variables]

            ds_crs = get_crs(ds, ds_variables[0]) or src_crs

            with Dataset(os.path.join(output_directory, os.path.split(filename)[1]), 'w') as out_ds:
                click.echo('Processing: {0}'.format(filename))

                warp_like(
                    ds,
                    ds_projection=ds_crs,
                    variables=ds_variables,
                    out_ds=out_ds,
                    template_ds=template_ds,
                    template_varname=template_varname,
                    resampling=getattr(Resampling, resampling)
                )
