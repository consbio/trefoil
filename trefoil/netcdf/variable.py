from bisect import bisect_left, bisect_right

import numpy
from datetime import date, datetime
import pytz
from affine import Affine
from netCDF4 import num2date, date2num, Variable
from pyproj import Proj
import six

from trefoil.geometry.bbox import BBox
from trefoil.utilities.proj import is_latlong
from trefoil.utilities.window import Window
from trefoil.netcdf.utilities import get_ncattrs
from trefoil.netcdf.crs import PROJ4_GEOGRAPHIC


class CoordinateVariable(object):
    """
    Wraps a one-dimensional variable with the same name as a dimension
    (http://www.unidata.ucar.edu/software/netcdf/docs/BestPractices.html).
    """

    def __init__(self, input):
        """
        A Coordinate Variable can be created from a netCDF dataset variable or a numpy array.

        :param input: variable in a netCDF dataset or a numpy array
        """

        self._ncattrs = dict()

        if isinstance(input, Variable):
            self.values = input[:]
            for attr in input.ncattrs():
                if not attr == '_FillValue':
                    self._ncattrs[attr] = input.getncattr(attr)
        else:
            self.values = input[:].copy()

    def __len__(self):
        return self.values.shape[0]

    def is_ascending_order(self):
        return self.values[0] < self.values[1]

    def indices_for_range(self, start, stop):
        """
        Returns the indices in this variable for the start and stop values
        :param start: start value
        :param stop: stop value
        :return: start and stop indices
        """

        assert stop > start

        if start > self.values.max():
            return self.values.size - 1, self.values.size - 1
        elif stop < self.values.min():
            return 0, 0

        if self.is_ascending_order():
            start_index = min(self.values.searchsorted(start), self.values.size - 1)

            # Need to move 1 index to the left unless we matched an index closely (allowing for precision errors)
            if start_index > 0 and not numpy.isclose(start, self.values[start_index]):
                start_index -= 1

            stop_index = min(self.values.searchsorted(stop), self.values.size - 1)
            if not numpy.isclose(stop, self.values[stop_index]) and stop < self.values[stop_index]:
                stop_index -= 1

            return start_index, stop_index
        else:
            # If values are not ascending, they need to be reversed
            temp = self.values[::-1]
            start_index = min(temp.searchsorted(start), temp.size - 1)

            if start_index > 0 and not numpy.isclose(start, temp[start_index]):
                start_index -= 1

            stop_index = min(temp.searchsorted(stop), temp.size - 1)
            if not numpy.isclose(stop, temp[stop_index]) and stop < temp[stop_index]:
                stop_index -= 1

            size = self.values.size - 1
            return max(size - stop_index, 0), max(size - start_index, 0)

    def slice_by_range(self, start, stop):
        """
        Slices a subset of values between start and stop values.

        :param start: start value
        :param stop: stop value
        :return: sliced view of self.values.  Make sure to copy this before altering it!
        """
        assert stop > start
        if start >= self.values.max() or stop <= self.values.min():
            return numpy.array([])

        start_index, stop_index = self.indices_for_range(start, stop)
        return self.values[start_index:stop_index+1]

    def add_to_dataset(self, dataset, name, is_unlimited=False, **kwargs):
        """
        :param dataset: name of the dataset to add the dimension and variable to
        :param name: name of the dimension and variable
        :param is_unlimited: set the dimension as unlimited
        :param kwargs: creation options for output variable.  Should be limited to compression info.
        :return: the newly created variable
        """

        if name in dataset.variables:
            raise Exception("Variable already exists in dataset")

        if name in dataset.dimensions:
            dimension = dataset.dimensions[name]
            if is_unlimited != dimension.isunlimited() or len(self) != len(dimension):
                raise Exception("Dimension already exists in dataset, but has different size")
        else:
            dimension_length = None if is_unlimited else len(self)
            dataset.createDimension(name, dimension_length)

        if 'fill_value' not in kwargs:
            fill_value = getattr(self.values, 'fill_value', None)
            if fill_value is not None:
                kwargs['fill_value'] = fill_value

        if self.values.dtype.char == 'S':
            variable = dataset.createVariable(name, 'string', (name,), **kwargs)
            # Have to write each index at a time, and cast to string.  Not optimal but seems to be the only way allowed by netCDF4.
            for index, value in enumerate(self.values):
                variable[index] = str(value)
        else:
            variable = dataset.createVariable(name, self.values.dtype, (name,), **kwargs)
            variable[:] = self.values[:]

        for att, value in six.iteritems(self._ncattrs):
            variable.setncattr(att, value)

        return variable


class BoundsCoordinateVariable(CoordinateVariable):
    """
    Wraps a two-dimensional variable representing bounds.  Shape is always (N, 2).

    Useful for representing time ranges, etc.

    Example: http://www.cgd.ucar.edu/cms/eaton/netcdf/CF-20010629.htm#grid_ex4
    """

    def is_ascending_order(self):
        return self.values[0][0] < self.values[1][0]

    def indices_for_range(self, start, stop):
        raise NotImplementedError("Not yet implemented")

    def add_to_dataset(self, dataset, name, is_unlimited=False, **kwargs):
        """
        :param dataset: name of the dataset to add the dimension and variable to
        :param name: name of the dimension and variable.  Note: a new dimension for the bounds '_bnds' will be created.
        :param is_unlimited: set the dimension as unlimited
        :param kwargs: creation options for output variable.  Should be limited to compression info.
        :return: the newly created variable
        """

        if name in dataset.variables:
            raise Exception("Variable already exists in dataset")

        bounds_dimension_name = '_bnds'
        if bounds_dimension_name in dataset.dimensions:
            if len(dataset.dimensions[bounds_dimension_name]) != 2:
                raise ValueError('Bounds dimension _bnds is already present in dataset and not of size 2')
        else:
            dataset.createDimension(bounds_dimension_name, 2)

        if name in dataset.dimensions:
            dimension = dataset.dimensions[name]
            if is_unlimited != dimension.isunlimited() or len(self) != len(dimension):
                raise Exception("Dimension already exists in dataset, but has different size")
        else:
            dimension_length = None if is_unlimited else len(self)
            dataset.createDimension(name, dimension_length)

        fill_value = getattr(self.values, 'fill_value', None)
        if fill_value is not None:
            kwargs['fill_value'] = fill_value

        variable = dataset.createVariable(name, self.values.dtype, (name,bounds_dimension_name), **kwargs)
        variable[:] = self.values[:]

        for att, value in six.iteritems(self._ncattrs):
            variable.setncattr(att, value)

        return variable


class SpatialCoordinateVariable(CoordinateVariable):
    """
    Abstracts properties for a given spatial dimension (e.g., longitude).
    Assumes that pixels follow a regular grid, and that dimension values represent centroids
    """

    @property
    def min(self):
        return self.values.min()

    @property
    def max(self):
        return self.values.max()

    @property
    def pixel_size(self):
        return float(abs(self.values[1] - self.values[0]))

    @property
    def edges(self):
        """
        Return coordinates of pixel edges from the min to the max
        """

        pixel_size = self.pixel_size

        if self.is_ascending_order():
            temp = numpy.append(self.values, self.values[-1] + pixel_size)
        else:
            temp = numpy.append(self.values[0] + pixel_size, self.values)
        return temp - (pixel_size / 2.0)

    def get_offset_for_subset(self, coordinate_variable):
        """
        Find the offset index of coordinate_variable within this coordinate variable.
        This assumes that coordinate_variable is a subset of this one, and that coordinates and projections match.
        """

        assert len(coordinate_variable) <= self.values.shape[0]
        #TODO: make this a fuzzy match within a certain decimal precision
        return list(self.values).index(coordinate_variable.values[0])


class SpatialCoordinateVariables(object):
    """
    Encapsulates x and y coordinates with projection information
    """

    def __init__(self, x, y, projection):
        assert isinstance(x, SpatialCoordinateVariable)
        assert isinstance(y, SpatialCoordinateVariable)
        if projection is not None:
            assert isinstance(projection, Proj)

        self.x = x
        self.y = y
        self.projection = projection

    @property
    def shape(self):
        return (len(self.y), len(self.x))

    @property
    def bbox(self):

        half_x_pixel_size = self.x.pixel_size / 2.0
        half_y_pixel_size = self.y.pixel_size / 2.0

        return BBox(
            (
                self.x.min - half_x_pixel_size,
                self.y.min - half_y_pixel_size,
                self.x.max + half_x_pixel_size,
                self.y.max + half_y_pixel_size
            ),
            self.projection
        )

    @property
    def affine(self):
        bbox = self.bbox

        return Affine(
            self.x.pixel_size,
            0,  # Not used
            bbox.xmin,
            0,  # Not used
            self.y.values[1] - self.y.values[0],  # Negative if y is descending
            bbox.ymin if self.y.is_ascending_order() else bbox.ymax
        )

    @classmethod
    def from_dataset(cls, dataset, x_name='longitude', y_name='latitude', projection=None):
        """
        Return a SpatialCoordinateVariables object for a dataset

        :param dataset: netCDF dataset
        :param x_varname: name of the x dimension
        :param y_varname: name of the y dimension
        :param projection: pyproj Proj object
        :return: CoordinateVariables instance
        """

        #TODO: detect x and y names, and projection
        if projection is None and x_name == 'longitude':
            projection = Proj(PROJ4_GEOGRAPHIC)


        return cls(
            SpatialCoordinateVariable(dataset.variables[x_name]),
            SpatialCoordinateVariable(dataset.variables[y_name]),
            projection
        )

    @staticmethod
    def from_bbox(bbox, x_size, y_size, dtype='float32', y_ascending=False):
        """
        Return a SpatialCoordinateVariables object from BBox and dimensions

        :param bbox: instance of a BBox, must have a projection
        :param x_size: number of pixels in x dimension (width or number of columns)
        :param y_size: number of pixels in y dimension (height or number of rows)
        :param dtype: data type (string or numpy dtype object) of values
        :param y_ascending: by default, y values are anchored from top left and are descending; if True, this inverts that order
        :return: CoordinateVariables instance, assuming that rows are ordered in decreasing value
        """

        assert isinstance(bbox, BBox)
        if not bbox.projection:
            raise ValueError('bbox projection must be defined')

        x_pixel_size = (bbox.xmax - bbox.xmin) / float(x_size)
        y_pixel_size = (bbox.ymax - bbox.ymin) / float(y_size)

        x_arr = numpy.arange(x_size, dtype=dtype)
        x_arr *= x_pixel_size
        x_arr += (bbox.xmin + x_pixel_size / 2.0)

        if y_ascending:
            y_arr = numpy.arange(y_size, dtype=dtype)
            y_arr *= y_pixel_size
            y_arr += (bbox.ymin + y_pixel_size / 2.0)

        else:
            y_arr = numpy.arange(0, -y_size, -1, dtype=dtype)
            y_arr *= y_pixel_size
            y_arr += (bbox.ymax - y_pixel_size / 2.0)

        x = SpatialCoordinateVariable(x_arr)
        y = SpatialCoordinateVariable(y_arr)

        return SpatialCoordinateVariables(x, y, bbox.projection)

    def add_to_dataset(self, dataset, x_name, y_name, **kwargs):
        x_var = self.x.add_to_dataset(dataset, x_name, **kwargs)
        y_var = self.y.add_to_dataset(dataset, y_name, **kwargs)

        x_var.setncattr('axis', 'X')
        y_var.setncattr('axis', 'Y')

        if self.projection:
            if is_latlong(self.projection):
                x_var.setncattr('standard_name', 'longitude')
                x_var.setncattr('long_name', 'longitude')
                x_var.setncattr('units', 'degrees_east')
                y_var.setncattr('standard_name', 'latitude')
                y_var.setncattr('long_name', 'latitude')
                y_var.setncattr('units', 'degrees_north')

            else:
                x_var.setncattr('standard_name', 'projection_x_coordinate')
                x_var.setncattr('long_name', 'x coordinate of projection')
                y_var.setncattr('standard_name', 'projection_y_coordinate')
                y_var.setncattr('long_name', 'y coordinate of projection')


    def slice_by_bbox(self, bbox):
        assert isinstance(bbox, BBox)

        x_half_pixel_size = float(self.x.pixel_size)/2
        y_half_pixel_size = float(self.y.pixel_size)/2

        # Note: this is very sensitive to decimal precision.
        x = SpatialCoordinateVariable(
            self.x.slice_by_range(bbox.xmin + x_half_pixel_size, bbox.xmax - x_half_pixel_size)
        )
        y = SpatialCoordinateVariable(
            self.y.slice_by_range(bbox.ymin + y_half_pixel_size, bbox.ymax - y_half_pixel_size)
        )
        return SpatialCoordinateVariables(x, y, self.projection)

    def slice_by_window(self, window):
        assert isinstance(window, Window)

        x = SpatialCoordinateVariable(self.x.values[window.x_slice])
        y = SpatialCoordinateVariable(self.y.values[window.y_slice])
        return SpatialCoordinateVariables(x, y, self.projection)

    def get_window_for_subset(self, subset_coordinates):
        """
        return a Window representing offsets of subset_coordinates self within subset_coordinates.
        Assumed to be in same projection, etc.

        :param subset_coordinates: the coordinates of the subset within self
        """

        assert isinstance(subset_coordinates, SpatialCoordinateVariables)

        y_offset = self.y.get_offset_for_subset(subset_coordinates.y)
        x_offset = self.x.get_offset_for_subset(subset_coordinates.x)
        return Window((y_offset, len(subset_coordinates.y) + y_offset),
                      (x_offset, len(subset_coordinates.x) + x_offset))

    def get_window_for_bbox(self, bbox):
        """
        return a Window representing offsets of bbox within self
        :param bbox: instance of bounding box representing coordinates to use for Window
        :return: Window instance to extract data from within coordinate range of self
        """

        assert isinstance(bbox, BBox)

        y_half_pixel_size = float(self.y.pixel_size)/2
        x_half_pixel_size = float(self.x.pixel_size)/2

        y_offset, y_max = self.y.indices_for_range(bbox.ymin + y_half_pixel_size, bbox.ymax - y_half_pixel_size)
        x_offset, x_max =  self.x.indices_for_range(bbox.xmin + x_half_pixel_size, bbox.xmax - x_half_pixel_size)
        return Window((y_offset, y_max + 1), (x_offset, x_max + 1))


class DateVariable(CoordinateVariable):
    """
    Provides utility wrapper of a date variable, especially when stored according to CF convention.
    If variable conforms to CF convention pattern (has units with 'since' in label and calendar) then
    dates are extracted and converted to python date objects.

    Dates are assumed to be sorted in ascending order.
    """

    def __init__(self, input, units_start_date=date(2000, 1, 1), calendar='360_day'):
        """
        Create from a variable with CF Convention units and calendar, or
        an array of years.

        If created from years, values are recorded on the first day of the month
        for each year, and are exported using units of days (years not allowed
        by CF convention.  Lame).
        """

        assert calendar in ('360_day', 'gregorian', 'standard', 'julian', '360', 'noleap')

        super(DateVariable, self).__init__(input)

        if isinstance(input, Variable):
            attributes = get_ncattrs(input)
            self.units = attributes.get('units', '').lower()
            self.calendar = attributes.get('calendar', '').lower()
            if self.units and self.calendar and 'since' in self.units.lower():
                self.dates = num2date(self.values, self.units, self.calendar)
            elif (self.units and 'year' in self.units) or 'year' in input._name.lower():
                self.dates = numpy.array([datetime(y, 1, 1, tzinfo=pytz.UTC) for y in self.values.astype('int')])
            else:
                raise ValueError('Variable is missing required attributes: units, calendar')
        else:
            self.units = 'year' if self.unit == 'year' else '{0}s since {1}'.format(self.unit, str(units_start_date))
            self.calendar = calendar

            if self.values.dtype.kind in ('i', 'u', 'f'):
                self.dates = numpy.array([datetime(y, 1, 1) for y in self.values])
            elif isinstance(self.values[0], datetime):
                self.dates = self.values.copy()

            if self.unit == 'year':
                self.values = numpy.array([x.year for x in self.values], dtype='int32')
            else:
                self.values = numpy.array(
                    date2num(self.dates, units=self.units, calendar=self.calendar), dtype=numpy.int32
                )

    @property
    def datetimes(self):
        """
        Convert to python datetimes if not done automatically (calendar not compatible with python datetimes).
        Use with caution
        """

        if isinstance(self.dates[0], datetime):
            return self.dates
        else:
            return numpy.array([datetime(*d.timetuple()[:6], tzinfo=pytz.UTC) for d in self.dates])

    @property
    def unit(self):
        def varies_by_year(x, y):
            if y.year == x.year or (y - x).seconds != 0 or x.month != y.month or x.day != y.day:
                return False

            return True

        def varies_by_month(x, y):
            if x.month == y.month or (y - x).seconds != 0 or x.day != y.day:
                return False

            return True

        datetimes = self.datetimes if not self.values.dtype == datetime else self.values

        if all(varies_by_year(datetimes[i], datetimes[i-1]) for i in range(1, len(datetimes))):
            return 'year'
        elif all(varies_by_month(datetimes[i], datetimes[i-1]) for i in range(1, len(datetimes))):
            return 'month'

        deltas = datetimes[1:] - datetimes[:-1]

        for unit, seconds in (('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1)):
            if any(x.seconds % seconds != 0 for x in deltas):
                continue
            break

        return unit

    def add_to_dataset(self, dataset, name, **kwargs):
        variable = super(DateVariable, self).add_to_dataset(dataset, name, **kwargs)
        for att in ('units', 'calendar'):
            variable.setncattr(att, getattr(self, att))

    def indices_for_range(self, start, stop):
        """
        Returns the indices in this variable for the start and stop values.  Data must be in ascending order
        :param start: start value.  Can be a date object or a year.
        :param stop: stop value.  Can be a date object or a year.
        :return: start and stop indices
        """

        if not self.is_ascending_order():
            raise ValueError("Dates must be in ascending order")

        if not isinstance(start, date):
            start = date(start, 1, 1)

        if not isinstance(stop, date):
            stop = date(stop, 12, 31)

        return numpy.searchsorted(self.dates, start), numpy.searchsorted(self.dates, stop)
