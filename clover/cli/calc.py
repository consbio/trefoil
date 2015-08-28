import os
import glob
import numpy
import click
from netCDF4 import Dataset
from clover.netcdf.utilities import copy_variable_dimensions
from clover.cli import cli


def calculate_delta(baseline_data, comp_data, do_proportion=False):
    dif = comp_data - baseline_data
    if not do_proportion:
        return dif
    else:
        return dif / baseline_data  # TODO: fix cases of 0's in baseline data with very small value


@cli.command(short_help='Calculate delta values into new datasets based on a baseline')
@click.argument('baseline', type=click.Path(exists=True))
@click.argument('files')
@click.argument('variable')
@click.option('--bidx', type=click.INT, default=0, help='Index in baseline if 3D (default 0)')
@click.option('--proportion', is_flag=True, default=False, help='Use proportion instead of difference')
@click.option('--outdir', default='./', help='Output directory')
def delta(baseline, files, variable, bidx, proportion, outdir):
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    with Dataset(baseline) as baseline_ds:
        baseline_data = baseline_ds.variables[variable]
        if len(baseline_data.shape) == 3:
            baseline_data = baseline_data[bidx]

        filenames = glob.glob(files)
        if not filenames:
            raise click.BadParameter('No files found matching pattern: {0}'.format(files), param='files', param_hint='files')

        for filename in filenames:
            print('Calculating delta against', filename)
            with Dataset(filename) as comp_ds:
                with Dataset(os.path.join(outdir, filename.replace('.nc', '_delta.nc')), 'w') as out_ds:
                    comp_var = comp_ds.variables[variable]
                    copy_variable_dimensions(comp_ds, out_ds, variable)
                    comp_data = comp_var

                    out_var = out_ds.createVariable(variable + '_delta', numpy.float32, dimensions=comp_var.dimensions)

                    if len(comp_data.shape) == 3:
                        # Assumes 3rd dimension is first
                        for i in range(0, comp_data.shape[0]):
                            out_var[i] = calculate_delta(baseline_data, comp_data[i], proportion)

                    else:
                        out_var[:] = calculate_delta(baseline_data, comp_data, proportion)
