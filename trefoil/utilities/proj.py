def is_latlong(p):
    """ Returns True if the projection uses a lat/long coordinate system """

    # `.is_latlong` was removed in pyproj 2.2
    try:
        return p.is_latlong()
    except AttributeError:
        return p.crs.is_geographic
