import numpy
import time

def summarize_count_by_category(values):
    """
    Tallys the pixel counts for each unique value found in values.

    All masking must be done prior to calling this function.

    :param values:  pixel values.
    :return: dictionary mapping value to count
    """

    #TODO: make sure this has areas of unique_value = 0
    flat_values = values.ravel()
    weights = None
    if isinstance(values, numpy.ma.masked_array):
        weights = flat_values.mask == False  # make sure all areas that are in mask are given a weight of 0, and not counted
    bincounts = numpy.bincount(flat_values, weights=weights)
    nonzero_indices = numpy.flatnonzero(bincounts)
    results = dict(numpy.vstack((nonzero_indices, bincounts[nonzero_indices])).T.astype(numpy.uint64))
    return results

    #alternative method, will work for non-integer values
    # flat_values = values.ravel()
    # results = dict()
    # for value in numpy.ma.unique(flat_values):
    #     if not isinstance(value, numpy.ma.core.MaskedConstant):
    #         results[value] = numpy.ma.count(numpy.ma.masked_array(flat_values, mask=flat_values != value))
    # return results


def summarize_areas_by_category(values, areas):
    """
    Tallys the areas for each unique value found in values based on the amount within each pixel.

    All masking must be done prior to calling this function.

    :param values:  pixel values.  Assumes that this has already been masked where areas==0
    :param areas: areas measured for each pixel (typically area of intersection of a feature w/in pixel)
    :return: dictionary mapping value to total area
    """

    flat_values = values.ravel()
    flat_areas = areas.ravel()
    results = dict()
    for value in numpy.ma.unique(flat_values):
        if not isinstance(value, numpy.ma.core.MaskedConstant):
            results[value] =  numpy.ma.masked_array(flat_areas, mask=flat_values != value).sum()
    return results


# TODO: see numpy.ma.average, which does weighted statistics: http://docs.scipy.org/doc/numpy/reference/generated/numpy.ma.average.html#numpy.ma.average
# In simple tests, it produces same results, but faster!
def calculate_weighted_statistics(values, weights, statistics):
    """
    Calculates weighted statistics

    :param values: pixel values
    :params weights: weight of each pixel, where 0 > weight >= 1  (areas of 0 weight should be masked out first).  Weights
    can be thought of as the proportion of each pixel occupied by some feature of interest.
    :param statistics: list of statistics to be calculated.  Currently supports: MEAN, STD
    :return: a list with each of the results, in the order the original statistic was requested
    """

    supported_statistics = {"MEAN", "STD"}
    unsupported_statistics = set(statistics).difference(supported_statistics)
    if unsupported_statistics:
        raise ValueError("Unsupported statistics: %s" % unsupported_statistics)

    results = []
    weighted_values = values * weights
    for statistic in statistics:
        if statistic == "MEAN":
            #must account for the mask of both values and weights in calculating sum
            results.append(weighted_values.sum() / numpy.ma.masked_array(weights, mask=weights.mask + values.mask).sum())
        elif statistic == "STD":
            results.append(weighted_values.std())

    return results


def statistic_by_interval(values, interval, statistic='mean'):
    """
    Calculates statistics from values across an interval.

    For example, to sum monthly data up to annual data: statistic_by_interval(monthy_values, 12, 'sum') => one entry per year

    :param values: values (must have 3 dimensions)
    :param interval: interval over which to sum  (e.g., 12 for summing months to year)
    :param statistic: one of 'mean', 'sum'
    :return: a numpy array with shape (values.shape[0] / interval, values.shape[1], values.shape[2])
    """

    if not statistic in ('mean', 'sum'):
        raise ValueError('Unsupported statistic {0}'.format(statistic))

    assert len(values.shape) == 3  # Anything else is not handled correctly right now
    assert values.shape[0] % interval == 0

    num_intervals = values.shape[0] / interval
    # Reshape to groups of intervals, intervals, then remaining shape of values
    temp = values.reshape(num_intervals, interval, values.shape[1], values.shape[2])

    if statistic == 'mean':
        return temp[:, :interval, :, :].mean(axis=1)
    elif statistic == 'sum':
        return temp[:, :interval, :, :].sum(axis=1)
