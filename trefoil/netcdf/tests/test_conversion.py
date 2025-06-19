import os
from netCDF4 import Dataset
from pyproj import Proj
import numpy
import rasterio
from trefoil.netcdf.crs import PROJ4_GEOGRAPHIC
from trefoil.netcdf.conversion import netcdf_to_raster


# TODO: need 3d test file
# TODO: need better test fixtures to fabricate data

def test_netcdf_to_raster(tmpdir):
    outfilename = str(tmpdir.join('test.tif'))

    dataset = Dataset('trefoil/test_data/tmin.nc')
    varname = 'tmin'
    y_name, x_name = dataset.variables[varname].dimensions[:2]

    netcdf_to_raster(
        dataset,
        varname,
        outfilename,
        projection=Proj(PROJ4_GEOGRAPHIC)
    )

    assert os.path.exists(outfilename)

    variable = dataset.variables[varname]
    height, width = variable.shape[:2]
    data = variable[:]

    with rasterio.open(outfilename, 'r') as src:
        assert src.count == 1
        assert src.width == width
        assert src.height == height
        assert src.crs.to_string() == 'EPSG:4326'
        assert src.dtypes[0] == data.dtype
        assert numpy.array_equal(data, src.read(1))
