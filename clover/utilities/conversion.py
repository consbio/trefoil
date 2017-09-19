import rasterio
from affine import Affine


def array_to_raster(data, outfilename=None, format='GTiff', affine=Affine.identity(), projection=None):
    """
    Only GTiff driver supported at present.

    Will implicitly overwrite existing output.
    prj must be a pyproj.Proj object
    """

    if format != 'GTiff':
        raise NotImplementedError('Formats besides GTiff not yet supported')

    meta = {
        'width': data.shape[1],
        'height': data.shape[0],
        'dtype': data.dtype.name, # rasterio uses strings, not dtypes
        'transform': affine,
        'count': 1,
        'crs': projection.srs
    }

    with rasterio.Env():
        with rasterio.open(outfilename, 'w', driver=format, **meta) as out:
            out.write(data, 1)
