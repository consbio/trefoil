import numpy

MAX_PRECISION = 6

class PrecisionFormatter(object):
    """
    Utility class to provide cleaner handling of decimal precision for string outputs
    """

    def __init__(self, values, max_precision=6):
        """
        Extract the maximum precision required to represent the precision of values.  Must be <= 6 (python truncates
        beyond this point), and less than max_precision.
        If input is an instance of a numpy array, uses numpy methods instead for better efficiency.
        """

        assert max_precision <= 6

        self._precision = 0
        decimal_strs = set(["{:g}".format(float(x) - int(round(x))) for x in values])
        if '0' in decimal_strs:
            decimal_strs.remove('0')
        if decimal_strs:
            self._precision = max([len(x) for x in decimal_strs]) - 2
        if max_precision is not None:
            self._precision = min(self._precision, max_precision)
        self._precision = min(self._precision, MAX_PRECISION)

    def format(self, value):
        if self._precision == 0:
            return str(int(round(float(value), 0)))
        else:
            return ("{:.%if}" % self._precision).format(float(value)).rstrip('0').rstrip('.')
