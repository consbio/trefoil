import numpy
from trefoil.analysis.timeseries import linear_regression


def test_linear_regression():
    timesteps = numpy.arange(0, 3, dtype=numpy.uint8)
    # Randomly generated data in advance
    values = numpy.array([
        [[0.29669283, 0.0388028], [0.64656131, 0.37802995]],
        [[0.56178477, 0.38010095], [0.67501274, 0.72232721]],
        [[1.04133795, 0.56589527], [0.73599531, 0.50754688]]
    ])

    slopes, intercepts = linear_regression(timesteps, values)

    # Calculated in advance, at a time when this was checked against results from scipy
    expected_slopes = numpy.array([[0.37232256, 0.26354623], [0.044717, 0.06475847]])
    expected_intercepts = numpy.array([[0.26094929, 0.06472011],[0.64113945, 0.47120955]])

    assert numpy.allclose(slopes, expected_slopes)
    assert numpy.allclose(intercepts, expected_intercepts)


def test_linear_regression_full():
    # Requires scipy, which isn't always available.
    # Not good for coverage but scipy is hard to install correctly on travis-ci
    try:
        from scipy.stats import linregress

        timesteps = numpy.arange(0, 100, dtype=numpy.uint8)
        k = numpy.random.rand(100)
        b = numpy.random.rand(k.shape[0])
        # shape is (timesteps.shape, k.shape)
        values = numpy.outer(timesteps, k) + b + numpy.random.normal(
            size=(timesteps.shape[0], k.shape[0]), scale=0.1)
        values = values.reshape(
            (100, 10, 10))  # divide the second dimension into two parts

        slopes, intercepts, r2vals, pvals = linear_regression(timesteps, values,
                                                              full=True)

        s, i, r, p = linregress(timesteps, values[:, 0, 0])[:4]
        assert numpy.allclose((s, i, r ** 2, p),
                              (slopes[0, 0], intercepts[0, 0], r2vals[0, 0],
                               pvals[0, 0]))

        s, i, r, p = linregress(timesteps, values[:, 2, 0])[:4]
        assert numpy.allclose((s, i, r ** 2, p),
                              (slopes[2, 0], intercepts[2, 0], r2vals[2, 0],
                               pvals[2, 0]))

    except ImportError:
        print('WARNING: scipy not available for testing')
