from netCDF4 import Dataset
import os
import time

import rasterio
import pyproj
import six

from clover.netcdf.crs import set_crs
from clover.netcdf.variable import SpatialCoordinateVariables
from clover.geometry.bbox import BBox


def raster_to_netcdf(filename_or_raster, outfilename=None, variable_name='data', format='NETCDF4', **kwargs):
    """

    :param filename_or_raster: name of file to open with rasterio, or opened rasterio raster dataset
    :param outfilename: name of output file.  If blank, will be same name as input with *.nc extension added
    :param format: output format for netCDF file: NETCDF3_CLASSIC, NETCDF3_64BIT, NETCDF4_CLASSIC, NETCDF4
    :param kwargs: arguments passed to variable creation: zlib

    Note: only rasters with descending y coordinates are currently supported
    """

    start = time.time()

    if isinstance(filename_or_raster, six.string_types):
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
        if prj.is_latlong():
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