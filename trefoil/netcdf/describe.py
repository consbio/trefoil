import numpy
from six import string_types
from netCDF4 import Dataset
from pyproj import Proj

from trefoil.netcdf.crs import get_crs, is_geographic, PROJ4_GEOGRAPHIC
from trefoil.netcdf.utilities import get_ncattrs
from trefoil.netcdf.variable import SpatialCoordinateVariable, SpatialCoordinateVariables, DateVariable


X_DIMENSION_STANDARD_NAMES = ('longitude', 'grid_longitude', 'projection_x_coordinate')
X_DIMENSION_COMMON_NAMES = ('longitude', 'lon', 'long', 'x')
Y_DIMENSION_STANDARD_NAMES = ('latitude', 'grid_latitude', 'projection_y_coordinate')
Y_DIMENSION_COMMON_NAMES = ('latitude', 'lat', 'y')
TIME_DIMENSION_STANDARD_NAMES = ('time',)
TIME_DIMENSION_COMMON_NAMES = ('time', 'year', 'years')  # TODO: months?


def get_interval(data):
    if data.shape[0] > 1:
        unique_intervals = numpy.unique(data[1:] - data[:-1])
        if unique_intervals.shape[0] == 1:
            return numpy.abs(unique_intervals[0]).item()

    # Not equal interval, interval doesn't apply
    return None


def describe(path_or_dataset):
    if isinstance(path_or_dataset, string_types):
        dataset = Dataset(path_or_dataset)
    else:
        dataset = path_or_dataset

    description = {
        'dimensions': {},
        'variables': {},
        'attributes': get_ncattrs(dataset)
    }

    for dimension_name in dataset.dimensions:
        dimension = dataset.dimensions[dimension_name]
        description['dimensions'][dimension_name] = {
            'length': len(dimension)
        }

    for variable_name in dataset.variables:
        variable = dataset.variables[variable_name]

        if not variable.dimensions:
            # Do not collect info about dimensionless variables (e.g., CRS variable)
            continue

        dtype = str(variable.dtype)
        if "'" in dtype:
            dtype = dtype.split("'")[1]

        attributes = get_ncattrs(variable)
        variable_info = {
            'attributes': attributes,
            'dimensions': variable.dimensions,
            'data_type': dtype,
            'name': attributes.get('long_name') or attributes.get('standard_name') or variable_name
        }

        if dtype not in ('str', ):
            if len(variable.shape) > 2:
                # Avoid loading the entire array into memory by iterating along the first index (usually time)
                variable_info.update({
                    'min': min(variable[i, :].min().item() for i in range(variable.shape[0])),
                    'max': max(variable[i, :].max().item() for i in range(variable.shape[0]))
                })
            else:
                data = variable[:]
                variable_info.update({
                    'min': data.min().item(),
                    'max': data.max().item()
                })

        if variable_name in dataset.dimensions and dtype not in ('str', ):
            dimension_variable = dataset.variables[variable_name]
            if len(dimension_variable.dimensions) == 1:  # range dimensions don't make sense for interval
                interval = get_interval(dimension_variable)
                if interval:
                    variable_info['interval'] = interval

        else:
            # Data variable
            proj4 = get_crs(dataset, variable_name)

            #extent
            if len(variable.dimensions) >= 2:
                x_variable_name = None
                y_variable_name = None
                time_variable_name = None
                for dimension_name in (x for x in variable.dimensions if x in dataset.variables):
                    attributes = get_ncattrs(dataset.variables[dimension_name])
                    standard_name = attributes.get('standard_name', None)
                    if standard_name in X_DIMENSION_STANDARD_NAMES or dimension_name in X_DIMENSION_COMMON_NAMES:
                        x_variable_name = dimension_name
                    elif standard_name in Y_DIMENSION_STANDARD_NAMES or dimension_name in Y_DIMENSION_COMMON_NAMES:
                        y_variable_name = dimension_name
                    elif standard_name in TIME_DIMENSION_STANDARD_NAMES or dimension_name in TIME_DIMENSION_COMMON_NAMES:
                        if len(dataset.dimensions[dimension_name]) > 1:
                            time_variable_name = dimension_name
                if x_variable_name and y_variable_name:
                    if proj4 is None and is_geographic(dataset, variable_name):
                        # Assume WGS84
                        proj4 = PROJ4_GEOGRAPHIC

                    coordinates = SpatialCoordinateVariables(
                        SpatialCoordinateVariable(dataset.variables[x_variable_name]),
                        SpatialCoordinateVariable(dataset.variables[y_variable_name]),
                        Proj(str(proj4)) if proj4 else None
                    )

                    variable_info['spatial_grid'] = {
                        'extent': coordinates.bbox.as_dict(),
                        'x_dimension': x_variable_name,
                        'x_resolution': coordinates.x.pixel_size,
                        'y_dimension': y_variable_name,
                        'y_resolution': coordinates.y.pixel_size
                    }
                if time_variable_name:
                    time_variable = dataset.variables[time_variable_name]

                    time_info = {
                        'dimension': time_variable_name,
                    }

                    try:
                        date_variable = DateVariable(time_variable)
                        values = date_variable.datetimes
                        time_info['extent'] = [values.min().isoformat(), values.max().isoformat()]
                        time_info['interval_unit'] = date_variable.unit
                        interval = get_interval(time_variable)
                        if interval is not None:
                            time_info['interval'] = interval

                    except ValueError:
                        pass

                    variable_info['time'] = time_info

            if proj4:
                variable_info['proj4'] = proj4

        description['variables'][variable_name] = variable_info

    return description
