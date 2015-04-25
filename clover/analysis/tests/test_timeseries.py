import numpy
from clover.analysis.timeseries import linear_regression


def test_linear_regression():
    timesteps = numpy.arange(0,100, dtype=numpy.uint8)
    k = numpy.random.rand(100)
    b = numpy.random.rand(100)
    values = numpy.outer(timesteps, k) + b + numpy.random.normal(size=(100, 100), scale=0.1)
    values = values.reshape((100, 10, 10))

    slopes, intercepts, r2vals, pvals = linear_regression(timesteps, values, full=True)


    # Validate against singular linear regression
    from scipy.stats import linregress

    s,i,r,p = linregress(timesteps, values[:,0,0])[:4]
    assert numpy.allclose((s, i, r**2, p),
                          (slopes[0,0], intercepts[0,0], r2vals[0,0], pvals[0,0]))

    s,i,r,p = linregress(timesteps, values[:,2,0])[:4]
    assert numpy.allclose((s, i, r**2, p),
                          (slopes[2,0], intercepts[2,0], r2vals[2,0], pvals[2,0]))
