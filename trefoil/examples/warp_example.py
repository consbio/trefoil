from netCDF4 import Dataset

from pyproj import Proj
from rasterio.enums import Resampling

from trefoil.netcdf.utilities import data_variables
from trefoil.netcdf.warp import warp_like

template_ds = Dataset('../test_data/ca_ru_1km.nc')
template_variable_name = 'data'

# ds = Dataset('../test_data/tmin.nc')
ds = Dataset('c:/temp/lc_800m_lu_nbp.nc')
variables = data_variables(ds).keys()  # ['tmin']


with Dataset('c:/temp/out.nc', 'w') as out_ds:
    warp_like(
        ds,
        ds_projection='EPSG:4326',  # source data are in geographic w/ WGS84 datum
        variables=variables,
        out_ds=out_ds,
        template_ds=template_ds,
        template_varname=template_variable_name,
        resampling=Resampling.cubic  # could also be Resampling.nearest
    )










