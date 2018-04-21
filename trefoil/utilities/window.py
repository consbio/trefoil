class Window(object):
    """
    Encapsulates a window representing the y_offset, y_max, x_offset, x_max of spatial coordinates
    from one dataset within another.
    Both are assumed to be in the same projection, and one is expected to be a subset of the other
    """

    def __init__(self, y_slice, x_slice):
        """
        :param y_slice: slice or tuple of y_offset to y_max + 1
        :param x_slice: slice or tuple of x_ffset to x_max + 1
        """

        if isinstance(y_slice, tuple):
            y_slice = slice(*y_slice)
        if isinstance(x_slice, tuple):
            x_slice = slice(*x_slice)

        self.y_slice = y_slice
        self.x_slice = x_slice

    def __str__(self):
        return 'y: %s, x: %s' % (self.y_slice, self.x_slice)

    @property
    def shape(self):
        return (self.y_slice.stop - self.y_slice.start,
                self.x_slice.stop - self.x_slice.start)

    def clip(self, values, slices=None):
        """
        Returns a subset view of values within domain represented by this instance.

        :param values: values to be clipped.  Last 2 dimensions must be row, col
        :param slices: list of indices
        :return: subset view of values clipped by self
        """

        if slices is None:
            slices = []
            if len(values.shape) > 2:
                for s in values.shape[:-2]:
                    slices.append(slice(0, s))

        elif isinstance(slices, (list, tuple)):
            slices = list(slices)
        else:
            slices = [slices]
        slices.append(self.y_slice)
        slices.append(self.x_slice)

        if len(slices) != len(values.shape):
            raise ValueError("Dimensions of input does not match number of slices")

        return values[slices]