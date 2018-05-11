import click
from netCDF4 import Dataset
from pyproj import Proj

from trefoil.netcdf import crs
from trefoil.cli import cli


@cli.command(short_help='Set spatial reference information for a variable in an existing dataset')
@click.argument('filename', type=click.Path(exists=True))
@click.argument('proj4')
@click.argument('variables', required=False)
@click.option('--all', 'all_variables', is_flag=True, default=False, help='Set CRS for all variables in the dataset')
def set_crs(filename, proj4, variables, all_variables):
    if not variables and not all_variables:
        raise click.BadArgumentUsage('No variables specified')

    try:
        proj = Proj(proj4)
    except RuntimeError:
        raise click.BadArgumentUsage('Invalid projection: ' + proj4)

    with Dataset(filename, 'a') as ds:
        variables_li = []
        if all_variables:
            variables_li = list(ds.variables.keys())
        elif variables:
            variables_li = [x.strip() for x in variables.split(',')]
            bad_variables = set(variables_li).difference(ds.variables.keys())
            if bad_variables:
                raise click.BadArgumentUsage(
                    'The following variables do not exist in this dataset: ' + ', '.join(bad_variables)
                )

        for variable in variables_li:
            crs.set_crs(ds, variable, proj)

