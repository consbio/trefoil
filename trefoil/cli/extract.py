import os
import glob
import click
from netCDF4 import Dataset
from trefoil.netcdf.utilities import copy_variable
from trefoil.cli import cli


@cli.command(short_help='Extract variables from files into new datasets in a new directory')
@click.argument('files')
@click.argument('variables')
@click.argument('outdir')
@click.option('--compress', is_flag=True, default=False, help='compress the variable (least_significant_digit=3)')
#TODO: add ability to subset by slices
def extract(files, variables, outdir, compress):
    """Extracts variables from files into new datasets.  Files will be named the same, and placed in outdir"""

    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='files', param_hint='FILES')

    variables = variables.split(',')

    if not os.path.exists(outdir):
        os.makedirs(outdir)

    kwargs = {}
    if compress:
        kwargs.update({
            'zlib': True,
            'least_significant_digit': 3
        })

    for filename in filenames:
        print('Extracting from {0}'.format(filename))
        with Dataset(filename) as infile:
            with Dataset(os.path.join(outdir, os.path.split(filename)[1]), 'w') as outfile:
                for variable in variables:
                    copy_variable(infile, outfile, variable, **kwargs)
