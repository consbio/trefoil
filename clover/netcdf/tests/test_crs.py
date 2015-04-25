import pytest
from netCDF4 import Dataset
from pyproj import Proj, pj_ellps
from clover.netcdf.crs import get_crs, set_crs
from clover.netcdf.utilities import get_ncattrs, set_ncattrs
from rasterio import crs as crs_utils

import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

def test_get_crs(tmpdir):
    """ Test reading proj4 string from CF convention parameters """

    ds = Dataset(str(tmpdir.join('test.nc')), 'w')
    data_var = ds.createVariable('data', 'S1')
    data_var.setncattr('grid_mapping', 'crs_Lambert')
    crs_var = ds.createVariable('crs_Lambert', 'S1')

    in_proj4 = '+proj=lcc +lat_1=30 +lat_2=60 +lat_0=47.5 +lon_0=-97 +x_0=3825000 +y_0=3200000'

    # These parameters match the above proj4 string
    ncatts = dict()
    ncatts['grid_mapping_name'] = 'lambert_conformal_conic'
    ncatts['latitude_of_projection_origin'] = 47.5
    ncatts['longitude_of_central_meridian'] = -97
    ncatts['standard_parallel'] = [30, 60]
    ncatts['false_northing'] = 3200000
    ncatts['false_easting'] = 3825000
    set_ncattrs(crs_var, ncatts)

    out_proj4 = get_crs(ds, 'data')
    assert out_proj4 is not None

    in_data = crs_utils.from_string(in_proj4)
    out_data = crs_utils.from_string(out_proj4)

    assert len(out_data) == 8  # There should be 8 parameters
    assert not set(in_data).difference(out_data)


    # Test WGS84 lat/long
    data_var = ds.createVariable('data2', 'S1')
    data_var.setncattr('grid_mapping', 'crs_latlong')
    crs_var = ds.createVariable('crs_latlong', 'S1')

    in_proj4 = '+proj=latlong +a={0} +rf={1}'.format(pj_ellps['WGS84']['a'], pj_ellps['WGS84']['rf'])

    # These parameters match the above proj4 string
    ncatts = dict()
    ncatts['grid_mapping_name'] = 'latitude_longitude'
    ncatts['semi_major_axis'] = 6378137.0
    ncatts['inverse_flattening'] = 298.257223563
    set_ncattrs(crs_var, ncatts)

    out_proj4 = get_crs(ds, 'data2')
    print(out_proj4)
    assert out_proj4 is not None

    in_data = crs_utils.from_string(in_proj4)
    out_data = crs_utils.from_string(out_proj4)

    assert len(out_data) == 4  # There should be 4 parameters
    assert not set(in_data).difference(out_data)


def test_set_crs(tmpdir):
    """ Test proper encoding of projection into CF Convention parameters """

    ds = Dataset(str(tmpdir.join('test.nc')), 'w')

    # Test polar stereographic
    proj4 = '+proj=stere +datum=WGS84 +lat_ts=60 +lat_0=90 +lon_0=263 +lat_1=60 +x_0=3475000 +y_0=7475000'
    data_var = ds.createVariable('data', 'S1')
    set_crs(ds, 'data', Proj(proj4))
    crs_var = ds.variables[get_ncattrs(data_var)['grid_mapping']]
    ncatts = get_ncattrs(crs_var)

    assert ncatts['grid_mapping_name'] == 'polar_stereographic'
    assert ncatts['inverse_flattening'] == 298.257223563
    assert ncatts['latitude_of_projection_origin'] == 90
    assert ncatts['straight_vertical_longitude_from_pole'] == 263
    assert ncatts['standard_parallel'] == 60
    assert ncatts['false_northing'] == 7475000
    assert ncatts['false_easting'] == 3475000

    # Test Lambert conformal conic
    proj4 = '+proj=lcc +lat_1=30 +lat_2=60 +lat_0=47.5 +lon_0=-97 +x_0=3825000 +y_0=3200000'
    data_var = ds.createVariable('data2', 'S1')
    set_crs(ds, 'data2', Proj(proj4))
    crs_var = ds.variables[get_ncattrs(data_var)['grid_mapping']]
    ncatts = get_ncattrs(crs_var)

    assert ncatts['grid_mapping_name'] == 'lambert_conformal_conic'
    assert ncatts['latitude_of_projection_origin'] == 47.5
    assert ncatts['longitude_of_central_meridian'] == -97
    assert ncatts['standard_parallel'] == [30, 60]
    assert ncatts['false_northing'] == 3200000
    assert ncatts['false_easting'] == 3825000

    # Unsupported projection should fail
    proj4 = '+proj=merc +lat_1=30 +lat_2=60 +lat_0=47.5 +lon_0=-97 +x_0=3825000 +y_0=3200000'
    data_var = ds.createVariable('data3', 'S1')
    with pytest.raises(ValueError):
        set_crs(ds, 'data3', Proj(proj4))


def test_symmetric_proj4(tmpdir):
    """ Test writing and reading proj4 string as attribute of variable """

    ds = Dataset(str(tmpdir.join('test.nc')), 'w')
    proj4 = '+proj=stere +datum=WGS84 +lat_ts=60 +lat_0=90 +lon_0=263 +lat_1=60 +x_0=3475000 +y_0=7475000'
    data_var = ds.createVariable('data', 'S1')
    set_crs(ds, 'data', Proj(proj4), set_proj4_att=True)
    out_proj4 = get_crs(ds, 'data')

    in_data = crs_utils.from_string(proj4)
    out_data = crs_utils.from_string(out_proj4)

    assert len(out_data) == 9  # There should be 9 parameters
    assert not set(in_data).difference(out_data)

