import numpy
from pyproj import Proj
from trefoil.geometry.bbox import BBox
from rasterio.crs import CRS


TEST_COORDS = (-124.75, 48.625, -124.375, 49.0)
TEST_COORDS_PRJ = Proj(init="EPSG:4326")


def test_bbox():
    bbox = BBox(TEST_COORDS, TEST_COORDS_PRJ)
    assert bbox.xmin == TEST_COORDS[0]
    assert bbox.ymin == TEST_COORDS[1]
    assert bbox.xmax == TEST_COORDS[2]
    assert bbox.ymax == TEST_COORDS[3]
    assert bbox.projection.srs == TEST_COORDS_PRJ.srs


def test_bbox_local_projection():
    bbox = BBox(TEST_COORDS, TEST_COORDS_PRJ)
    out = CRS.from_string(bbox.get_local_albers_projection().srs)
    expected = CRS.from_string("+lon_0=-124.5625 +ellps=WGS84 +datum=WGS84 +y_0=0 +no_defs=True +proj=aea +x_0=0 +units=m +lat_2=48.9375 +lat_1=48.6875 +lat_0=0 ")
    assert expected == out


def test_projection():
    bbox = BBox(TEST_COORDS, TEST_COORDS_PRJ)
    proj_bbox = bbox.project(Proj(init="EPSG:3857"))
    # Calculated by running this previously under controlled conditions.  No validation against truth of projection values.
    assert numpy.allclose(
        proj_bbox.as_list(),
        [-13887106.476460878, 6211469.632719522, -13845361.6674134, 6274861.394006577]
    )
