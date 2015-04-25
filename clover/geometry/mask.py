import numpy
import gdal, ogr, osr

#TODO: migrate this into raster IO instead
def mask_from_geometry(ndarray_shape, geometry, projection_wkt, transform, all_touched=False):
    """
    Create a boolean numpy mask from a Shapely geometry.  Data must be projected to match prior to calling this function.
    Areas are coded as 1 inside the geometry, and 0 outside.  Invert this to use as a numpy.ma mask.

    :param ndarray_shape: (rows, cols)
    :param geometry: Shapely geometry object
    :param projection_wkt: the projection of the geometry and target numpy array, as WKT
    :param transform: the GDAL transform object representing the spatial domain of the target numpy array
    :param all_touched: if true, any pixel that touches geometry will be included in mask.
    If false, only those with centroids within or selected by Brezenhams line algorithm will be included.
    See http://www.gdal.org/gdal__alg_8h.html#adfe5e5d287d6c184aab03acbfa567cb1 for more information.
    """

    assert len(ndarray_shape) == 2

    sr = osr.SpatialReference()
    sr.ImportFromWkt(projection_wkt)
    target_ds = gdal.GetDriverByName("MEM").Create("", ndarray_shape[1], ndarray_shape[0], gdal.GDT_Byte)
    target_ds.SetProjection(sr.ExportToWkt())
    target_ds.SetGeoTransform(transform)
    temp_features = ogr.GetDriverByName("Memory").CreateDataSource("")
    lyr = temp_features.CreateLayer("poly", srs=sr)
    feature = ogr.Feature(lyr.GetLayerDefn())
    feature.SetGeometryDirectly(ogr.Geometry(wkb = geometry.wkb))
    lyr.CreateFeature(feature)
    kwargs = {}
    if all_touched:
        kwargs['options'] = ["ALL_TOUCHED=TRUE"]
    gdal.RasterizeLayer(target_ds, [1], lyr, burn_values=[1], **kwargs)
    return target_ds.GetRasterBand(1).ReadAsArray(0, 0, ndarray_shape[1], ndarray_shape[0]).astype(numpy.bool)


#Notes for converting to cython
#given input as Fiona geojson object (via shapely.geometry.mapping(the_geom) ), can create python ogr object using ogr.CreateGeometryFromJson(json.dumps(fiona_obj))
#in Cython, probably should use the driver more directly
#look at this: http://svn.osgeo.org/gdal/trunk/autotest/ogr/ogr_geojson.py