import numpy

from trefoil.analysis.summary import summarize_areas_by_category, calculate_weighted_statistics
from trefoil.utilities.window import Window

# Days per month from Tim, starting with January.  Useful for weighting statistics when rolling months up to year.
# Assumes 365 day calendar with no leap years
DAYS_PER_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
MONTH_LABELS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def extract_categorical_timeseries_by_area(values, areas, timestep_indicies, window=None):
    """
    Extract a timeseries array for each category found within the values of variable, using the areas occupied by
    each category within each pixel.

    :param values: the values for a given variable from the netcdf file.  Must be organized on only 3 dimensions: time, row, col
    :param areas: the areas of each pixel to count toward total area of given category in each timestep
    :param timestep_indicies: the indices over which to extract the time series from the values of variable
    #:param row_offset: the offset from the starting row coordinate of values to the starting row coordinate of areas
    #:param col_offset: the offset from the starting column coordinate of values to the starting column coordinate of areas
    :param window: the subdomain coordinates of areas within values.  Must
    :return: a dictionary of the categorical values found, each with a full timeseries
    """

    assert len(values.shape) == 3

    if window is not None:
        assert isinstance(window, Window)

    results = dict()
    num_timesteps = len(timestep_indicies)
    for index in timestep_indicies:
        if window is not None:
            data = window.clip(values, index).ravel()
        else:
            data = values[index].ravel()
        data = numpy.ma.masked_array(data, mask=areas.mask)
        category_summary = summarize_areas_by_category(data.astype("i"), areas)
        for category in category_summary:
            if not category in results:
                results[category] = numpy.zeros(num_timesteps)
            results[category][index] = category_summary[category]
    return results


def extract_statistics_timeseries_by_weight(values, weights, statistics, window=None):
    """
    Extract weighted time series statistics,
    :param values: the values for a given variable from the netcdf file.  Must be organized on only 3 dimensions: time, row, col
    :param weights: the weight of each pixel for the statistic
    :param statistics: a tuple indicating the statistics to be calculated, e.g., ("MEAN", "STD").  Note: statistics
    do not account for different weights between time periods (e.g., months of different durations).
    :param window: the subdomain coordinates of areas within values.
    :return: a dictionary of statistic name to time series array
    """

    assert len(values.shape) == 3

    if window is not None:
        assert isinstance(window, Window)

    results = dict()
    for statistic in statistics:
        results[statistic] = numpy.zeros(values.shape[0])

    for index in xrange(values.shape[0]):
        if window is not None:
            data = window.clip(values, index).ravel()
        else:
            data = values[index].ravel()
        data = numpy.ma.masked_array(data, mask=weights.mask)
        statistics_results = calculate_weighted_statistics(data, weights, statistics)
        for stat_index, statistic in enumerate(statistics):
            results[statistic][index] = statistics_results[stat_index]
    return results


def linear_regression(timesteps, values, full=False):
    """Perform linear regression using linear algebra operators

    Note: does not account for missing data within time series.

    :param timesteps: 1D array of timesteps to use for x value of linear regression
    :param values: 3D array of data to use for y value of linear regression, assumes timestep is first axis
    :param full: return full statistics or just slopes & intercepts.  Default is False.  If True, requires scipy.
    :returns: (slopes, intercepts) or (slopes, intercepts, r-squared, p-value) if full is True
    """

    # ideas from:
    # http://stackoverflow.com/questions/20343500/efficient-1d-linear-regression-for-each-element-of-3d-numpy-array
    # http://stackoverflow.com/questions/3054191/converting-numpy-lstsq-residual-value-to-r2
    # p-value calculation derived from scipy: https://github.com/scipy/scipy/blob/master/scipy/stats/stats.py

    assert len(values.shape) == 3
    assert values.shape[0] == timesteps.shape[0]

    shape = values.shape

    y = values.reshape((shape[0], shape[1] * shape[2]))
    fit, residuals = numpy.linalg.lstsq(numpy.c_[timesteps, numpy.ones_like(timesteps)], y)[:2]
    slopes = fit[0].reshape((shape[1], shape[2]))
    intercepts = fit[1].reshape((shape[1], shape[2]))

    mask = None
    if hasattr(values, 'mask'):
        mask = values.mask[0]
        slopes = numpy.ma.masked_array(slopes, mask=mask)
        intercepts = numpy.ma.masked_array(intercepts, mask=mask)

    if not full:
        return slopes, intercepts


    # T-distribution used for p-value requires scipy
    from scipy.stats.distributions import t as t_dist

    # Calculate R2 value
    r2 = (1 - residuals / (y.shape[0] * y.var(axis=0)))
    r = numpy.sqrt(r2)
    r2 = r2.reshape((shape[1], shape[2]))

    # Calculate p-value
    tiny = 1.0e-20
    df = timesteps.shape[0] - 2
    t = r * numpy.sqrt(df / ((1.0 - r + tiny)*(1.0 + r + tiny)))
    p = (2 * t_dist.sf(numpy.abs(t), df)).reshape(shape[1], shape[2])

    if mask is not None:
        r2 = numpy.ma.masked_array(r2, mask=mask)
        p = numpy.ma.masked_array(p, mask=mask)

    return slopes, intercepts, r2, p
