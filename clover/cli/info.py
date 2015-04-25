import os
import glob
import click
from netCDF4 import Dataset
from clover.netcdf.describe import describe as describe_netcdf
from clover.netcdf.utilities import collect_statistics, get_dtype_string


def print_dict(d, precision=2, depth=0):
    space = '  '
    keys = d.keys()
    keys.sort()
    for key in keys:
        value = d[key]
        if isinstance(value, dict) and len(value) > 1:
            print('{0}{1}:'.format(space * depth, key))
            print_dict(value, depth=depth+1)
            print('')
        else:
            if isinstance(value, float):
                value = round(value, precision)
            print('{0}{1}: {2}'.format(space * depth, key, value))


@click.group()
def info():
    pass


@info.command()
@click.argument('files')
def describe(files):
    """Describe netCDF datasets"""

    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='files', param_hint='FILES')

    for filename in filenames:
        print('# {0} #'.format(filename))
        results = describe_netcdf(filename)
        print('## Attributes ##')
        print_dict(results['attributes'])
        print('\n## Dimensions ##')
        print_dict(results['dimensions'])
        print('\n## Variables ##')
        print_dict(results['variables'])
        print('')


@info.command()
@click.argument('filename', type=click.Path(exists=True))
def variables(filename):
    ds = Dataset(filename)
    
    print('## Data Variables ##')
    variables = [v for v in ds.variables if v not in ds.dimensions]
    variables.sort()
    for varname in variables:
        variable = ds.variables[varname]
        print('{0}: dimensions{1}  dtype:{2}'.format(varname, tuple([str(d) for d in variable.dimensions]), get_dtype_string(variable)))

    print('\n## Dimension Variables ##')
    variables = [v for v in ds.variables if v in ds.dimensions]
    variables.sort()
    for varname in variables:
        variable = ds.variables[varname]
        print('{0}({1})  dtype:{2}'.format(varname, len(ds.dimensions[varname]), get_dtype_string(variable)))


@info.command()
@click.argument('files')
@click.argument('variables')
def stats(files, variables):
    """Calculate statistics for each variable across all files"""

    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='files', param_hint='FILES')

    print('Collecting statistics from {0} files'.format(len(filenames)))

    variables = variables.split(',')

    statistics = collect_statistics(filenames, variables)
    for variable in variables:
        print('## {0} ##'.format(variable))
        print_dict(statistics[variable])
        print('')


if __name__ == '__main__':
    info()
