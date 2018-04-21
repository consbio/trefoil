import os
import glob
import click
from netCDF4 import Dataset
from trefoil.netcdf.describe import describe as describe_netcdf
from trefoil.netcdf.utilities import collect_statistics, get_dtype_string
from trefoil.cli import cli
from trefoil.cli.utilities import get_mask


def print_dict(d, depth=0):
    space = '  '
    keys = sorted(d.keys())
    for key in keys:
        value = d[key]
        if isinstance(value, dict) and len(value) > 1:
            click.echo('{0}{1}:'.format(space * depth, key))
            print_dict(value, depth=depth+1)
            click.echo('')
        else:
            if isinstance(value, float):
                click.echo('{0}{1}: {2:g}'.format(space * depth, key, value))
            else:
                click.echo('{0}{1}: {2}'.format(space * depth, key, value))


@cli.command(short_help='Describe netCDF files')
@click.argument('files')
def describe(files):
    """Describe netCDF datasets"""

    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='files', param_hint='FILES')

    for filename in filenames:
        click.echo('# {0} #'.format(filename))
        results = describe_netcdf(filename)
        click.echo('## Attributes ##')
        print_dict(results['attributes'])
        click.echo('\n## Dimensions ##')
        print_dict(results['dimensions'])
        click.echo('\n## Variables ##')
        print_dict(results['variables'])
        click.echo('')


@cli.command(short_help='List variables in netCDF file')
@click.argument('filename', type=click.Path(exists=True))
def variables(filename):
    ds = Dataset(filename)
    
    click.echo('## Data Variables ##')
    variables = [v for v in ds.variables if v not in ds.dimensions]
    variables.sort()
    for varname in variables:
        variable = ds.variables[varname]
        click.echo('{0}: dimensions{1}  dtype:{2}'.format(varname, tuple([str(d) for d in variable.dimensions]), get_dtype_string(variable)))

    click.echo('\n## Dimension Variables ##')
    variables = [v for v in ds.variables if v in ds.dimensions]
    variables.sort()
    for varname in variables:
        variable = ds.variables[varname]
        click.echo('{0}({1})  dtype:{2}'.format(varname, len(ds.dimensions[varname]), get_dtype_string(variable)))


@cli.command(short_help='Display statistics for variables within netCDF files')
@click.argument('files')
@click.argument('variables')
@click.option('--mask', 'mask_path', default=None, help='Mask dataset:variable (e.g., mask.nc:mask).  Mask variable assumed to be named "mask" unless otherwise provided')
def stats(files, variables, mask_path):
    """Calculate statistics for each variable across all files"""

    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='files', param_hint='FILES')

    mask = get_mask(mask_path) if mask_path is not None else None

    click.echo('Collecting statistics from {0} files'.format(len(filenames)))

    variables = variables.split(',')

    statistics = collect_statistics(filenames, variables, mask=mask)
    for variable in variables:
        click.echo('## {0} ##'.format(variable))
        print_dict(statistics[variable])
        click.echo('')
