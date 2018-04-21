import numpy
from pyproj import Proj
import click
import rasterio
from rasterio.crs import CRS
from rasterio.warp import reproject
from rasterio.enums import Resampling

from trefoil.netcdf.crs import get_crs
from trefoil.netcdf.utilities import copy_variable, copy_dimension, get_fill_value
from trefoil.netcdf.variable import SpatialCoordinateVariables


def warp_array(
    arr,
    src_crs,
    src_transform,
    dst_crs,
    dst_transform,
    dst_shape,
    resampling=Resampling.nearest):

    """
    Warp a 2D array using rasterio, always returning a masked array.

    A fill_value will be chosen from the array's data type if the input is not a masked array (beware conflicts with
    valid values!)

    All nodata values are filled in prior to warping, and masked back out later if necessary.

    :param dst_shape: shape of destination array

    All other parameters are the same as for rasterio.warp.reproject
    """

    with rasterio.Env():
        orig_dtype = arr.dtype
        if arr.dtype == numpy.int8:
            # Have to upcast for rasterio
            arr = arr.astype('int16')

        out = numpy.empty(shape=dst_shape, dtype=arr.dtype)

        fill = get_fill_value(arr.dtype)
        if hasattr(arr, 'fill_value'):
            fill = arr.fill_value
            arr = numpy.ma.filled(arr, arr.fill_value)

        reproject(
            arr,
            out,
            src_crs=src_crs,
            src_transform=src_transform,
            dst_crs=dst_crs,
            dst_transform=dst_transform,
            resampling=resampling,
            src_nodata=fill,
            dst_nodata=fill
        )

        if out.dtype != orig_dtype:
            out = out.astype(orig_dtype)

        out = numpy.ma.masked_array(out, mask=out == fill)

        return out



def warp_like(ds, ds_projection, variables, out_ds, template_ds, template_varname, resampling=Resampling.nearest):
    """
    Warp one or more variables in a NetCDF file based on the coordinate reference system and
    spatial domain of a template NetCDF file.
    :param ds: source dataset
    :param ds_projection: source dataset coordiante reference system, proj4 string or EPSG:NNNN code
    :param variables: list of variable names in source dataset to warp
    :param out_ds: output dataset.  Must be opened in write or append mode.
    :param template_ds: template dataset
    :param template_varname: variable name for template data variable in template dataset
    :param resampling: resampling method.  See rasterio.enums.Resampling for options
    """

    template_variable = template_ds.variables[template_varname]
    template_prj = Proj(get_crs(template_ds, template_varname))
    template_mask = template_variable[:].mask

    template_y_name, template_x_name = template_variable.dimensions[-2:]
    template_coords = SpatialCoordinateVariables.from_dataset(
        template_ds,
        x_name=template_x_name,
        y_name=template_y_name,
        projection=template_prj
    )
    # template_geo_bbox = template_coords.bbox.project(ds_prj, edge_points=21)  # TODO: add when needing to subset

    ds_y_name, ds_x_name = ds.variables[variables[0]].dimensions[-2:]
    proj = Proj(init=ds_projection) if 'EPSG:' in ds_projection.upper() else Proj(str(ds_projection))
    ds_coords = SpatialCoordinateVariables.from_dataset(ds, x_name=ds_x_name, y_name=ds_y_name, projection=proj)

    with rasterio.Env():
        # Copy dimensions for variable across to output
        for dim_name in template_variable.dimensions:
            if not dim_name in out_ds.dimensions:
                if dim_name in template_ds.variables and not dim_name in out_ds.variables:
                    copy_variable(template_ds, out_ds, dim_name)
                else:
                    copy_dimension(template_ds, out_ds, dim_name)

        for variable_name in variables:
            click.echo('Processing: {0}'.format(variable_name))

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
                'src_crs': CRS.from_string(ds_projection),
                'dst_transform': template_coords.affine,
                'dst_crs': template_prj.srs,
                'resampling': resampling,
                'src_nodata': fill_value,
                'dst_nodata': fill_value,
                'threads': 4
            }

            # TODO: may only need to select out what is in window

            if len(variable.shape) == 3:
                idxs = range(variable.shape[0])
                with click.progressbar(idxs) as bar:
                    for i in bar:
                        # print('processing slice: {0}'.format(i))

                        data = variable[i, :]
                        out = numpy.ma.empty(template_coords.shape, dtype=data.dtype)
                        out.mask = template_mask
                        out.fill(fill_value)
                        reproject(data, out, **reproject_kwargs)
                        out_var[i, :] = out

            else:
                data = variable[:]
                out = numpy.ma.empty(template_coords.shape, dtype=data.dtype)
                out.mask = template_mask
                out.fill(fill_value)
                reproject(data, out, **reproject_kwargs)
                out_var[:] = out
