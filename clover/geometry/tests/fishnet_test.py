import os

from shapely.geometry import Polygon
from pyproj import Proj
import numpy

from clover.geometry.fishnet import Fishnet
from clover.netcdf.variable import SpatialCoordinateVariable, SpatialCoordinateVariables


TEST_COORDINATES = SpatialCoordinateVariables(
    SpatialCoordinateVariable(numpy.array([-124.75, -124.70834, -124.66666, -124.625, -124.58334, -124.54166, -124.5, -124.45834, -124.41666, -124.375])),
    SpatialCoordinateVariable(numpy.array([49.0, 48.958332, 48.916668, 48.875, 48.833332, 48.791668, 48.75, 48.708332, 48.666668, 48.625])),
    Proj(init="EPSG:4326"))

TEST_AOI = Polygon([
    (-124.70834, 49.0),
    (-124.75, 48.833332),
    (-124.58334, 48.666668),
    (-124.54166, 48.958332),
    (-124.70834, 49.0)
])

TEST_AOI_PRJ = Proj(init="EPSG:4326")

TEST_DIR = "c:/temp"


def test_fishnet_create():
    target_projection = TEST_COORDINATES.bbox.get_local_albers_projection()
    fishnet = Fishnet(TEST_COORDINATES, target_projection)
    assert len(fishnet.features) == TEST_COORDINATES.y.size
    assert len(fishnet.features[0]) == TEST_COORDINATES.x.size
    assert fishnet.total_areas[0][0] == 14125649.050313622
    assert fishnet.total_areas[TEST_COORDINATES.y.size-1][TEST_COORDINATES.x.size-1] == 14232280.6731924

def test_fishnet_intersect_aoi():
    target_projection = TEST_COORDINATES.bbox.get_local_albers_projection()
    fishnet = Fishnet(TEST_COORDINATES, target_projection)
    intersection_areas = fishnet.calculate_intersection(TEST_AOI, TEST_AOI_PRJ)
    assert round(intersection_areas[3][2], 4) == round(fishnet.total_areas[3][2], 4)
    assert intersection_areas[0][0] == 0
    #fishnet.write_shapefile(os.path.join(TEST_DIR, "test_intersection.shp"), intersection_areas)

def test_fishnet_write_shapefile():
    target_projection = TEST_COORDINATES.bbox.get_local_albers_projection()
    fishnet = Fishnet(TEST_COORDINATES, target_projection)
    filename = os.path.join(TEST_DIR, "test_fishnet.shp")
    fishnet.write_shapefile(filename)
    assert os.path.exists(filename)
    os.remove(filename)