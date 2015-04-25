import numpy
from clover.analysis.summary import statistic_by_interval


def test_sum_by_interval():
    monthly = numpy.random.randint(0, 4, (24, 1, 1))
    annual = statistic_by_interval(monthly, 12, 'sum')
    flat_monthly = monthly.flatten()
    midpoint = flat_monthly.shape[0] / 2
    assert numpy.array_equal(annual.flatten(), (flat_monthly[:midpoint].sum(), flat_monthly[midpoint:].sum()))





