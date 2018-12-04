import click
from netCDF4 import Dataset
from pyproj import Proj

from trefoil.netcdf import crs
from trefoil.cli import cli


@cli.command(short_help='Set spatial reference information for variables in an existing dataset')
@click.argument('filename', type=click.Path(exists=True))
@click.argument('proj4')
@click.option('--only', 'variables', default=None, help='Set CRS only for the specified variables')
def set_crs(filename, proj4, variables):
    try:
        proj = Proj(proj4)
    except RuntimeError:
        raise click.BadArgumentUsage('Invalid projection: ' + proj4)

    with Dataset(filename, 'a') as ds:
        if not variables:
            variables_li = [v for v in ds.variables if v not in ds.dimensions]
        else:
            variables_li = [x.strip() for x in variables.split(',')]
            bad_variables = set(variables_li).difference(ds.variables.keys())
            if bad_variables:
                raise click.BadArgumentUsage(
                    'The following variables do not exist in this dataset: ' + ', '.join(bad_variables)
                )

        for variable in variables_li:
            crs.set_crs(ds, variable, proj)

