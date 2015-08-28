from functools import partial

from shapely.geometry import mapping, Polygon
from shapely.ops import transform
import fiona
import fiona.crs
import numpy
import numpy.ma
from rtree import index
import pyproj
import time

from clover.netcdf.variable import SpatialCoordinateVariables


class Fishnet(object):
    """
    Encapsulates fishnet polygons and their associated spatial index
    """

    def __init__(self, coordinates, target_projection):
        """
        Create simple fishnet polygon based on x and y coords in target projection
        TODO: consider densifying polygon edges to better handle projection issues
        """

        self.projection = target_projection
        self.features = []
        self._index = index.Index()
        self.total_areas = numpy.zeros((len(coordinates.y), len(coordinates.x)))

        assert isinstance(coordinates, SpatialCoordinateVariables)
        #Note: per common convention, y is decreasing.  May not actually break the code, but block in case it does
        assert coordinates.y.values[0] > coordinates.y.values[-1]

        print("Creating fishnet...")

        x_edges = coordinates.x.edges
        y_edges = coordinates.y.edges

        #project top coordinates
        top_edges_x, top_edges_y = pyproj.transform(coordinates.projection, target_projection, x_edges, [y_edges[0]] * x_edges.size)
        for row in range(0, y_edges.size - 1):
            fishnet_row = []
            bottom_edges_x, bottom_edges_y = pyproj.transform(coordinates.projection, target_projection, x_edges, [y_edges[row+1]] * x_edges.size)
            for col in range(0, x_edges.size - 1):
                poly = Polygon([
                        (bottom_edges_x[col+1], bottom_edges_y[col+1]),
                        (top_edges_x[col+1], top_edges_y[col+1]),
                        (top_edges_x[col], top_edges_y[col]),
                        (bottom_edges_x[col], bottom_edges_y[col]),
                        (bottom_edges_x[col+1], bottom_edges_y[col+1])
                    ])
                fishnet_row.append(poly)
                self._index.insert(row * col + col, poly.bounds, obj=(row, col))
                self.total_areas[row][col] = poly.area
            self.features.append(fishnet_row)
            top_edges_x = bottom_edges_x
            top_edges_y = bottom_edges_y


    def calculate_intersection(self, aoi_geometry, aoi_projection):
        """
        Create and return a numpy array representing the intersection areas between the area of interest and
        the fishnet.  Areas are calculated using the projection of the fishnet.
        """

        intersection_areas = numpy.zeros(self.total_areas.shape)
        project_aoi_to_local_albers = partial(pyproj.transform, aoi_projection, self.projection)

        ##TODO: deal with other types than polygons
        assert aoi_geometry.geom_type in ("MultiPolygon", "Polygon")

        if aoi_geometry.geom_type == "Polygon":
            self._intersect(transform(project_aoi_to_local_albers, aoi_geometry), intersection_areas)
        elif aoi_geometry.geom_type == "MultiPolygon":
            for geometry in aoi_geometry.geoms:
                self._intersect(transform(project_aoi_to_local_albers, geometry), intersection_areas)
        else:
            raise NotImplementedError("Other geometry types not yet supported in fishnet analysis")

        return intersection_areas


    def _intersect(self, geometry, intersection_areas):
        """
        For each intersection between fishnet and geometry, update intersection_areas
        Geometry, fishnet, and spatial index must all be in same projection
        """
        print('Processing intersection')
        start = time.time()
        try:
            hits = list(self._index.intersection(geometry.bounds, objects='raw'))

            for hit in hits:
                row,col = hit
                poly = self.features[row][col]

                if (geometry.contains(poly)):
                    intersection_areas[row][col] += self.total_areas[row][col]

                elif geometry.intersects(poly):
                    intersection_areas[row][col] += geometry.intersection(poly).area
        finally:
            print('elapsed %.2f' % (time.time()-start))

    def write_shapefile(self, filename, intersection_areas=None):
        """
        Write the fishnet and total areas, with intersection areas (if provided) to a shapefile
        """

        print("Writing shapefile...")
        property_defs = [('row','int'), ('col','int'), ('total_area','float')]
        if intersection_areas is not None:
            assert intersection_areas.shape == self.total_areas.shape
            property_defs.append(('int_area','float'))
        with fiona.collection(filename,'w',
                        crs=fiona.crs.from_string(self.projection.srs),
                        driver="ESRI Shapefile",
                        schema={'geometry': 'Polygon', 'properties':property_defs}) as out_shp:

            for row, fishnet_row in enumerate(self.features):
                for col, poly in enumerate(fishnet_row):
                    properties = {'row': row, 'col': col, 'total_area': self.total_areas[row][col]}
                    if intersection_areas is not None:
                        properties['int_area'] = intersection_areas[row][col]
                    out_shp.write({'id': row * col + col,'geometry':mapping(poly),'properties':properties})


