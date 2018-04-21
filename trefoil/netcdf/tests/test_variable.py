import os
import numpy
from pyproj import Proj
from netCDF4 import Dataset
from trefoil.netcdf.variable import CoordinateVariable, BoundsCoordinateVariable
from trefoil.netcdf.variable import SpatialCoordinateVariable, SpatialCoordinateVariables
from trefoil.geometry.bbox import BBox


def test_coordinate_variable_length():
    data = numpy.arange(10)
    variable = CoordinateVariable(data)
    assert len(variable) == data.shape[0]


def test_range_functions():
    data = numpy.arange(10)
    variable = CoordinateVariable(data)
    value_range = (2, 5)
    indices = variable.indices_for_range(*value_range)
    assert indices == value_range
    assert numpy.array_equal(variable.slice_by_range(*value_range), data[2:6])

    # Test values in reverse order
    data = data[::-1]
    variable = CoordinateVariable(data)
    indices = variable.indices_for_range(*value_range)
    size = len(variable) - 1
    assert indices == (size - value_range[1], size - value_range[0])
    assert numpy.array_equal(variable.slice_by_range(*value_range), data[4:8])

    # Test value range much larger than data
    value_range = (-100, 100)
    variable = CoordinateVariable(numpy.arange(1, 11))
    indices = variable.indices_for_range(*value_range)
    assert indices == (0, len(variable) - 1)

    data = numpy.arange(20,40)
    variable = CoordinateVariable(data)
    # Test out of range
    assert variable.indices_for_range(0, 10) == (0, 0)
    assert numpy.array_equal(variable.slice_by_range(0, 10), numpy.array([]))

    #Test partial overlap
    assert numpy.array_equal(variable.slice_by_range(10, 30), numpy.arange(20, 31))

    assert variable.indices_for_range(40, 50) == (variable.values.size-1, variable.values.size-1)
    assert numpy.array_equal(variable.slice_by_range(40, 50), numpy.array([]))


def test_window_for_bbox():
    coords = SpatialCoordinateVariables.from_bbox(BBox([-124, 82, -122, 90], Proj(init='epsg:4326')), 20, 20)
    window = coords.get_window_for_bbox(BBox([-123.9, 82.4, -122.1, 89.6]))

    assert window.x_slice == slice(1, 19)
    assert window.y_slice == slice(1, 19)


def test_BoundsCoordinateVariable():
    bounds = numpy.array(((0, 1), (1, 2)))
    variable = BoundsCoordinateVariable(bounds)
    outvarname = 'test_bounds'
    outfilename = 'test.nc'
    try:
        with Dataset(outfilename, 'w') as target_ds:
            variable.add_to_dataset(target_ds, outvarname)
            assert '_bnds' in target_ds.dimensions
            assert outvarname in target_ds.dimensions
            assert outvarname in target_ds.variables
            assert numpy.array_equal(target_ds.variables[outvarname][:], bounds)
    finally:
        if os.path.exists(outfilename):
            os.remove(outfilename)


def test_SpatialCoordinateVariable():
    # Ascending
    variable = SpatialCoordinateVariable(numpy.arange(10))
    assert numpy.array_equal(variable.edges, numpy.arange(11) - 0.5)

    # Descending
    variable = SpatialCoordinateVariable(numpy.arange(9, -1, -1))
    assert numpy.array_equal(variable.edges, numpy.arange(10, -1, -1) - 0.5)

    outvarname = 'lat'
    outfilename = 'test.nc'

    try:
        with Dataset(outfilename, 'w') as target_ds:
            variable.add_to_dataset(target_ds, outvarname)
            assert outvarname in target_ds.dimensions
            assert outvarname in target_ds.variables
            assert numpy.array_equal(target_ds.variables[outvarname][:], variable.values)
    finally:
        if os.path.exists(outfilename):
            os.remove(outfilename)


def test_SpatialCoordinateVariables_bbox():
    proj = Proj(init='EPSG:4326')
    bbox = BBox((10.5, 5, 110.5, 55), projection=proj)
    coords = SpatialCoordinateVariables.from_bbox(bbox, 10, 5)
    assert coords.bbox.as_list() == bbox.as_list()


def test_SpatialCoordinateVariables_slice_by_bbox():
    lat = SpatialCoordinateVariable(numpy.arange(19, -1, -1))
    lon = SpatialCoordinateVariable(numpy.arange(10))
    proj = Proj(init='EPSG:4326')
    coords = SpatialCoordinateVariables(lon, lat, proj)

    subset = coords.slice_by_bbox(BBox((1.75, 3.7, 6.2, 16.7), proj))
    assert numpy.array_equal(subset.x.values, numpy.arange(2, 6))
    assert subset.x.values[0] == 2
    assert subset.x.values[-1] == 5
    assert subset.y.values[0] == 16
    assert subset.y.values[-1] == 4


def test_SpatialCoordinateVariables_add_to_dataset():
    lat = SpatialCoordinateVariable(numpy.arange(19, -1, -1))
    lon = SpatialCoordinateVariable(numpy.arange(10))
    coords = SpatialCoordinateVariables(lon, lat, Proj(init='EPSG:4326'))

    lat_varname = 'lat'
    lon_varname = 'lon'
    outfilename = 'test.nc'

    try:
        with Dataset(outfilename, 'w') as target_ds:
            coords.add_to_dataset(target_ds, lon_varname, lat_varname)

            assert lat_varname in target_ds.dimensions
            assert lat_varname in target_ds.variables
            assert len(target_ds.dimensions[lat_varname]) == lat.values.size
            assert numpy.array_equal(lat.values, target_ds.variables[lat_varname][:])

            assert lon_varname in target_ds.dimensions
            assert lon_varname in target_ds.variables
            assert len(target_ds.dimensions[lon_varname]) == lon.values.size
            assert numpy.array_equal(lon.values, target_ds.variables[lon_varname][:])
    finally:
        if os.path.exists(outfilename):
            os.remove(outfilename)


