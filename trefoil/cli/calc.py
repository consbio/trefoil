import os
import glob
import numpy
import click
from netCDF4 import Dataset
from trefoil.netcdf.utilities import copy_variable_dimensions, copy_variable, get_fill_value, copy_attributes
from trefoil.cli import cli


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


#All files must have the same dimensions, and variable must have 3 dimensions with the first being time
@cli.command(short_help='Bin time series data by interval')
@click.argument('files')
@click.argument('variable')
@click.option('--outdir', default='./', help='Output directory')
@click.option('--statistic', type=click.Choice(['mean', 'sum']), default='mean', help='Statistic for aggregating data', show_default=True)
@click.option('--interval', type=click.INT, default=1, help='Interval in number of time steps for aggregating data', show_default=True)
@click.option('--zip', 'zlib', is_flag=True, default=False, help='Use zlib compression of data and coordinate variables')
def bin_ts(files, variable, outdir, statistic, interval, zlib):
    """
    Bin time series data by an interval, according to a statistic.


    """

    if not interval > 0:
        raise click.BadParameter('must be > 0', param='--interval', param_hint='--interval')

    if not os.path.exists(outdir):
        os.makedirs(outdir)

    filenames = glob.glob(files)
    if not filenames:
        raise click.BadParameter('No files found matching pattern: {0}'.format(files), param='files', param_hint='files')

    for filename in filenames:
        click.echo('Aggregating data for {0}'.format(filename))

        with Dataset(filename) as ds:
            if not variable in ds.variables:
                raise click.BadParameter('variable {0} was not found in file: {1}'.format(variable, filename),
                                         param='variable', param_hint='VARIABLE')
            var_obj = ds.variables[variable]

            if not len(var_obj.dimensions) == 3:
                raise click.BadParameter('variable {0} must have 3 dimensions: {1}'.format(variable, filename),
                                         param='variable', param_hint='VARIABLE')

            spatial_dims = var_obj.dimensions[-2:]
            z_dim = var_obj.dimensions[0]
            num_intervals = var_obj.shape[0] // interval

            if var_obj.shape[0] % interval != 0:
                click.echo('WARNING: Anything beyond the last full interval will be dropped')

            with Dataset(os.path.join(outdir, filename.replace('.nc', '_bin.nc')), 'w') as out_ds:
                for dim in spatial_dims:
                    copy_variable(ds, out_ds, dim, zlib=zlib)

                out_ds.createDimension(z_dim, num_intervals)
                if z_dim in ds.variables:
                    z_var = ds.variables[z_dim]
                    out_z_var = out_ds.createVariable(
                        z_dim, z_var.dtype, dimensions=(z_dim,), fill_value=get_fill_value(z_var.dtype), zlib=zlib
                    )
                    copy_attributes(z_var, out_z_var, z_var.ncattrs())
                    out_z_var[:] = z_var[:num_intervals*interval:interval]

                out_var = out_ds.createVariable(
                    variable, var_obj.dtype, dimensions=var_obj.dimensions,
                    fill_value=get_fill_value(var_obj.dtype), zlib=zlib
                )
                copy_attributes(var_obj, out_var, var_obj.ncattrs())

                # Due to memory issues, we have to do this more carefully than existing method in analysis.summary.statistic_by_interval
                # TODO: pick appropriate approach based on total size of array
                for i in range(num_intervals):
                    subset = var_obj[i*interval:(i+1)*interval]

                    if statistic == 'mean':
                        out_var[i] = subset.mean(axis=0)
                    elif statistic == 'sum':
                        out_var[i] = subset.sum(axis=0)
