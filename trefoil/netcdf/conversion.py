from netCDF4 import Dataset
import os
import time

import rasterio
import pyproj
from six import string_types

from trefoil.netcdf.crs import set_crs
from trefoil.netcdf.variable import SpatialCoordinateVariables
from trefoil.geometry.bbox import BBox
from trefoil.netcdf.crs import get_crs
from trefoil.utilities.conversion import array_to_raster
from trefoil.utilities.proj import is_latlong


def raster_to_netcdf(filename_or_raster, outfilename=None, variable_name='data', format='NETCDF4', **kwargs):
    """
    Parameters
    ----------
    filename_or_raster: name of file to open with rasterio, or opened rasterio raster dataset
    outfilename: name of output file.  If blank, will be same name as input with *.nc extension added
    variable_name: output format for netCDF file: NETCDF3_CLASSIC, NETCDF3_64BIT, NETCDF4_CLASSIC, NETCDF4
    format
    kwargs: arguments passed to variable creation: zlib

    Note: only rasters with descending y coordinates are currently supported
    """

    start = time.time()

    if isinstance(filename_or_raster, string_types):
        if not os.path.exists(filename_or_raster):
            raise ValueError('File does not exist: {0}'.format(filename_or_raster))

        src = rasterio.open(filename_or_raster)
        managed_raster = True
    else:
        src = filename_or_raster
        managed_raster = False

    if not src.count == 1:
        raise NotImplementedError('ERROR: multi-band rasters not yet supported for this operation')

    prj = pyproj.Proj(**src.crs)

    outfilename = outfilename or src.name + '.nc'
    with Dataset(outfilename, 'w', format=format) as target:
        if is_latlong(prj):
            x_varname = 'longitude'
            y_varname = 'latitude'
        else:
            x_varname = 'x'
            y_varname = 'y'

        # TODO: may need to do this in blocks if source is big
        data = src.read(1, masked=True)

        coords = SpatialCoordinateVariables.from_bbox(BBox(src.bounds, prj), src.width, src.height)
        coords.add_to_dataset(target, x_varname, y_varname, **kwargs)

        out_var = target.createVariable(variable_name, data.dtype, dimensions=(y_varname, x_varname), **kwargs)
        out_var[:] = data
        set_crs(target, variable_name, prj, set_proj4_att=False)

    if managed_raster:
        src.close()

    print('Elapsed {0:.3f} seconds'.format(time.time() - start))


def netcdf_to_raster(
        path_or_dataset,
        variable_name,
        outfilename,
        index=0,
        projection=None):
    """
    Exports a 2D slice from a netcdf file to a raster file.
    Only GeoTiffs are supported at this time.


    Parameters
    ----------
    path_or_dataset: path to NetCDF file or open Dataset
    variable_name: name of data variable to export from dataset
    outfilename: output filename
    index: index within 3rd dimension (in first position) or 0
    projection: pyproj.Proj object.  Automatically determined from file if possible
    """

    if isinstance(path_or_dataset, string_types):
        dataset = Dataset(path_or_dataset)
    else:
        dataset = path_or_dataset

    projection = projection or get_crs(dataset, variable_name)
    if not projection:
        raise ValueError('Projection must be provided; '
                         'no projection information can be determined from file')

    # TODO figure out cleaner way to get affine or coords
    y_name, x_name = dataset.variables[variable_name].dimensions[:2]
    coords = SpatialCoordinateVariables.from_dataset(
        dataset, x_name, y_name, projection=projection)
    affine = coords.affine

    if outfilename.lower().endswith('.tif'):
        format = 'GTiff'
    else:
        raise ValueError('Only GeoTiff outputs supported, filename must have .tif extension')

    variable = dataset.variables[variable_name]
    ndims = len(variable.shape)
    if ndims == 2:
        if index != 0:
            raise ValueError('Index out of range, must be 0')
        data = variable[:]
    elif ndims == 3:
        # Assumes that time dimension is first
        if index < 0 or index >= variable.shape[0]:
            raise ValueError('Index out of range, '
                             'must be between 0 and {0}'.variable.shape[0])
        data = variable[index]

    else:
        raise ValueError(
            'Unsupported number of dimensions {0} for variable {1}, '
            'must be 2 or 3'.format(ndims, variable_name))

    array_to_raster(
        data,
        outfilename,
        format=format,
        projection=projection,
        affine=affine)
