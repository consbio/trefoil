"""
Provides conversion functions between PROJ4 strings and CF Convention projection
parameters stored as attributes on a grid_mapping variable

Conversions are loosely based on OCGIS approach to CRS:
https://github.com/NCPP/ocgis/blob/master/src/ocgis/interface/base/crs.py
"""


import logging
import os
import re
from pyproj import Proj, pj_list, pj_ellps

from trefoil.netcdf.utilities import get_ncattrs, set_ncattrs
from rasterio.crs import CRS

# pyproj 2 drops `pyproj_datadir` in favor of `datadir.get_data_dir()`
try:
    from pyproj import pyproj_datadir
except ImportError:
    from pyproj import datadir
    pyproj_datadir = datadir.get_data_dir()


PROJ4_GEOGRAPHIC = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'

logger = logging.getLogger(__name__)


def invert_dict(dictionary):
    return {v: k for k, v in dictionary.items()}


def epsg_to_proj4(epsg_code):
    data = open(os.path.join(pyproj_datadir, 'epsg')).read()
    match = re.search('(?<=<{0}>).*(?=<>)'.format(epsg_code), data)
    if not match:
        raise ValueError('ERROR: EPSG {0} not found in proj4 data file'.format(epsg_code))

    return match.group().strip().replace('longlat', 'latlong')  # pyproj stores the longlat instead of latlong as used here


PROJ4_KEY = 'proj4'

PROJ4_CF_ELLIPSOID_MAP = {
    'a': 'semi_major_axis',
    'b': 'semi_minor_axis',
    'rf': 'inverse_flattening'
}

PROJ4_CF_NAMES = {
    'aea': 'albers_conical_equal_area',
    'latlong': 'latitude_longitude',
    'laea': 'lambert_azimuthal_equal_area',
    'lcc': 'lambert_conformal_conic',
    'stere': 'polar_stereographic',
    'tmerc': 'transverse_mercator',
    'utm': 'universal_transverse_mercator'
}

PROJ4_CF_PARAM_MAP = {
    'aea': {
        'lat_0': 'latitude_of_projection_origin',
        'lat_{0}': 'standard_parallel',
        'lon_0': 'longitude_of_central_meridian',
        'x_0': 'false_easting',
        'y_0': 'false_northing'
    },
    'latlong': {},  # No extra parameters for lat / long
    'laea': {
        'lat_0': 'latitude_of_projection_origin',
        'lon_0': 'longitude_of_projection_origin',
        'x_0': 'false_easting',
        'y_0': 'false_northing'
    },
    'lcc': {
        'lat_0': 'latitude_of_projection_origin',
        'lat_{0}': 'standard_parallel',
        'lon_0': 'longitude_of_central_meridian',
        'x_0': 'false_easting',
        'y_0': 'false_northing'
    },

    'stere': {
        'k_0': 'scale_factor',
        'lat_0': 'latitude_of_projection_origin',
        'lat_ts': 'standard_parallel',
        'lon_0': 'straight_vertical_longitude_from_pole',
        'x_0': 'false_easting',
        'y_0': 'false_northing'
    },
    'tmerc': {
        'k_0': 'scale_factor',
        'lat_0': 'latitude_of_projection_origin',
        'lon_0': 'longitude_of_central_meridian',
        'x_0': 'false_easting',
        'y_0': 'false_northing'
    },
    'utm': {
        'zone': 'utm_zone_number'
    }
}

# Build inverse maps
CF_PROJ4_ELLPSOID_MAP = invert_dict(PROJ4_CF_ELLIPSOID_MAP)
CF_PROJ4_NAMES = invert_dict(PROJ4_CF_NAMES)
CF_PROJ4_PARAM_MAP = {PROJ4_CF_NAMES[k]: invert_dict(PROJ4_CF_PARAM_MAP[k]) for k in PROJ4_CF_PARAM_MAP}


def get_crs(dataset, variable_name):
    """
    Return a PROJ4 projection string for a variable in a dataset.
    If non-standard 'proj4' attribute is found in attributes of dataset or
    variable, that is used instead.  Otherwise, the projection parameters are
    extracted from attributes in the grid_mapping variable in the dataset
    referenced from the data variable's attributes.

    :param dataset: open netCDF dataset
    :param variable_name: name of data variable to extract projection
    :return: PROJ4 projection string or None
    """

    ncatts = get_ncattrs(dataset.variables[variable_name])
    dsatts = get_ncattrs(dataset)

    # If dataset already includes proj4 string, just use it
    existing_proj4 = dsatts.get(PROJ4_KEY) or ncatts.get(PROJ4_KEY)
    if existing_proj4:
        return existing_proj4

    # Attempt to construct proj4 string based on CF convention parameters
    if 'grid_mapping' not in ncatts:
        logger.debug('grid_mapping attribute not found for variable {0}'.format(variable_name))
        return None

    if ncatts['grid_mapping'] not in dataset.variables:
        logger.debug('grid_mapping variable {0} not found in dataset'.format(ncatts['grid_mapping']))
        return None

    crs_variable = dataset.variables[ncatts['grid_mapping']]
    crs_atts = get_ncattrs(crs_variable)

    cf_crs_name = crs_atts.get('grid_mapping_name')
    if not (cf_crs_name and cf_crs_name in CF_PROJ4_PARAM_MAP):
        # Could not determine projection name
        logger.debug('No supported projection found for {0}'.format(cf_crs_name))
        return None

    param_map = CF_PROJ4_PARAM_MAP[cf_crs_name]

    proj4_params = {'proj': CF_PROJ4_NAMES[cf_crs_name]}

    expected_params = set(CF_PROJ4_PARAM_MAP[cf_crs_name].keys())
    if expected_params.difference(crs_atts):
        logger.debug('Missing expected parameters {0}'.format(expected_params.difference(crs_atts)))

    for param in expected_params.intersection(crs_atts):
        value = crs_atts[param]

        if param == 'standard_parallel' and '{' in param_map[param]:
            # Special case: variable number of standard parallels
            value = list(value)
            for index, val in enumerate(value, start=1):
                proj4_params[param_map[param].format(index)] = val
        else:
            proj4_params[param_map[param]] = value

    for param in set(CF_PROJ4_ELLPSOID_MAP.keys()).intersection(crs_atts):
        proj4_params[CF_PROJ4_ELLPSOID_MAP[param]] = crs_atts[param]

    try:
        return Proj(**CRS(proj4_params).to_dict()).srs

    except:
        # Could not create valid projection
        logger.debug('Could not create valid Proj4 projection from parameters')

    return None


def set_crs(dataset, variable_name, projection, set_proj4_att=False):
    """
    Set the projection information into a grid_mapping variable and reference it
    from the data variable.

    :param dataset: dataset open in write or append mode
    :param variable_name: name of data variable to attach projection to
    :param projection: pyproj.Proj projection object
    :param set_proj4_att: if True, set the 'proj4' attribute on the variable
    """

    if not isinstance(projection, Proj):
        raise ValueError('Projection must be instance of pyproj.Proj')

    variable = dataset.variables[variable_name]

    if 'epsg:' in projection.srs:
        proj_string = epsg_to_proj4(re.search('(?<=epsg:)\d+', projection.srs).group())
    else:
        proj_string = projection.srs

    if set_proj4_att:
        variable.setncattr(PROJ4_KEY, proj_string)

    proj = CRS.from_string(proj_string)
    proj_data = proj.to_dict()
    proj_key = 'latlong' if not proj.is_projected else proj_data['proj']
    if not proj_key in PROJ4_CF_PARAM_MAP.keys():
        raise ValueError('CF Convention mapping is not yet available for projection {0}'.format(proj_key))

    crs_variable_name = 'crs_{0}'.format(pj_list[proj_key].replace(' ', '_').replace('/', ''))
    if not crs_variable_name in dataset.variables:
        crs_variable = dataset.createVariable(crs_variable_name, 'S1')

        ncatts = {'grid_mapping_name': PROJ4_CF_NAMES[proj_key]}

        out_proj_params = PROJ4_CF_PARAM_MAP[proj_key]
        for param in out_proj_params:
            if param.count('{'):
                # Special case - standard parallel
                keys = [param.format(i) for i in (1, 2)]
                values = [proj_data[key] for key in keys if key in proj_data]
                if values:
                    if len(values) == 1:
                        values = values[0]
                    ncatts[out_proj_params[param]] = values

            elif param in proj_data:
                ncatts[out_proj_params[param]] = proj_data[param]

        if 'datum' in proj_data and not 'ellps' in proj_data:
            # Not all datums link to available pj_ellps keys, some had to be added manually here
            if proj_data['datum'] in pj_ellps:
                proj_data['ellps'] = proj_data['datum']
            elif proj_data['datum'] == 'NAD83':
                proj_data['ellps'] = 'GRS80'
            elif proj_data['datum'] == 'NAD27':
                proj_data['ellps'] = 'clrk66'
            else:
                raise ValueError('projection ellipsoid must be specified, datum {0}'
                                 'does not match a known ellipsoid'.format(proj_data['datum']))

        # Extract out parameters of known ellipsoids
        if 'ellps' in proj_data:
            if not proj_data['ellps'] in pj_ellps:
                raise ValueError('projection ellipsoid does not match a known ellipsoid')

            ellipsoid_params = pj_ellps[proj_data['ellps']]
            for param in set(PROJ4_CF_ELLIPSOID_MAP.keys()).intersection(ellipsoid_params):
                proj_data[param] = ellipsoid_params[param]

        for param in set(PROJ4_CF_ELLIPSOID_MAP.keys()).intersection(proj_data):
            ncatts[PROJ4_CF_ELLIPSOID_MAP[param]] = proj_data[param]

        set_ncattrs(crs_variable, ncatts)

    variable.setncattr('grid_mapping', crs_variable_name)



def is_geographic(dataset, variable_name):
    """
    Try to determine if dataset appears to be geographic.  This is a fallback if a true CRS cannot be obtained using other
    functions.  Currently limited to checking names of spatial dimensions.

    :param dataset: open netCDF dataset
    :param variable_name: name of data variable
    :returns: True if variable appears to be in geographic coordinates
    """

    options = (
        {'lat', 'lon'},
        {'lat', 'long'},
        {'latitude', 'longitude'}
    )

    variable = dataset.variables[variable_name]
    dim_names = set([d.lower() for d in variable.dimensions[-2:]])

    for option in options:
        if not option.difference(dim_names):
            return True

    return False


