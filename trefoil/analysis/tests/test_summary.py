import numpy
from trefoil.analysis.summary import statistic_by_interval, calculate_zonal_statistics
from trefoil.analysis.summary import VALID_ZONAL_STATISTICS


def test_sum_by_interval():
    monthly = numpy.random.randint(0, 4, (24, 1, 1))
    annual = statistic_by_interval(monthly, 12, 'sum')
    flat_monthly = monthly.flatten()
    midpoint = int(flat_monthly.shape[0] / 2)
    assert numpy.array_equal(annual.flatten(), (flat_monthly[:midpoint].sum(), flat_monthly[midpoint:].sum()))


def test_calculate_zonal_stats_2d():
    zones = numpy.zeros((10, 10), dtype='uint8')
    zones[5:] = 1
    zone_values = numpy.array([0, 1])
    data = numpy.arange(1, 101, dtype='uint8').reshape((10, 10))

    statistics = list(VALID_ZONAL_STATISTICS)

    results = calculate_zonal_statistics(zones, zone_values, data, statistics)

    print(results)
    assert not set(zone_values).difference(results.keys())

    assert not set(statistics).difference(results[0].keys())
    assert not set(statistics).difference(results[1].keys())

    for zone in zone_values:
        result = results[zone]
        truth = numpy.arange(zone * 50 + 1, zone * 50 + 51)
        for statistic in statistics:
            if statistic == 'count':
                assert result[statistic] == truth.size
            else:
                assert result[statistic] == getattr(truth, statistic)()
