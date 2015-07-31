import numpy
from pyproj import Proj
import rasterio
from rasterio import crs
from rasterio.warp import reproject, RESAMPLING

from clover.netcdf.crs import get_crs
from clover.netcdf.utilities import copy_variable_dimensions, copy_variable, copy_dimension
from clover.netcdf.variable import SpatialCoordinateVariables


def warp_like(ds, ds_projection, variables, out_ds, template_ds, template_varname, resampling=RESAMPLING.nearest):
    """
    Warp one or more variables in a NetCDF file based on the coordinate reference system and
    spatial domain of a template NetCDF file.
    :param ds: source dataset
    :param ds_projection: source dataset coordiante reference system, as a pyproj.Proj object
    :param variables: list of variable names in source dataset to warp
    :param out_ds: output dataset.  Must be opened in write or append mode.
    :param template_ds: template dataset
    :param template_varname: variable name for template data variable in template dataset
    :param resampling: resampling method.  See rasterio.warp.RESAMPLING for options
    """

    template_variable = template_ds.variables[template_varname]
    template_prj = Proj(get_crs(template_ds, template_varname))
    template_mask = template_variable[:].mask

    template_coords = SpatialCoordinateVariables.from_dataset(template_ds, x_name='x', y_name='y', projection=template_prj)
    # template_geo_bbox = template_coords.bbox.project(ds_prj, edge_points=21)  # TODO: add when needing to subset

    ds_coords = SpatialCoordinateVariables.from_dataset(ds, x_name='lon', y_name='lat', projection=ds_projection)


    with rasterio.drivers():
        # Copy dimensions for variable across to output
        for dim_name in template_variable.dimensions:
            if not dim_name in out_ds.dimensions:
                copy_dimension(template_ds, out_ds, dim_name)

        for variable_name in variables:
            print('Processing: {0}'.format(variable_name))

            variable = ds.variables[variable_name]
            fill_value = getattr(variable, '_FillValue', variable[0, 0].fill_value)

            for dim_name in variable.dimensions[:-2]:
                if not dim_name in out_ds.dimensions:
                    if dim_name in ds.variables:
                        copy_variable(ds, out_ds, dim_name)
                    else:
                        copy_dimension(ds, out_ds, dim_name)

            out_var = out_ds.createVariable(
                variable_name,
                variable.dtype,
                dimensions=variable.dimensions[:-2] + template_variable.dimensions,
                fill_value=fill_value
            )

            reproject_kwargs = {
                'src_transform': ds_coords.affine,
                'src_crs': crs.from_string(ds_projection.srs),
                'dst_transform': template_coords.affine,
                'dst_crs': template_prj.srs,
                'resampling': resampling,
                'threads': 4
            }

            # TODO: may only need to select out what is in window

            if len(variable.shape) == 3:
                for i in range(0, variable.shape[0]):
                    print('processing slice: {0}'.format(i))

                    data = variable[i, :]
                    out = numpy.ma.empty(template_coords.shape, dtype=data.dtype)
                    out.mask = template_mask
                    out.fill(data.fill_value)
                    reproject(data, out, **reproject_kwargs)
                    out_var[i, :] = out

            else:
                data = variable[:]
                out = numpy.ma.empty(template_coords.shape, dtype=data.dtype)
                out.mask = template_mask
                out.fill(data.fill_value)
                reproject(data, out, **reproject_kwargs)
                out_var[:] = out
