import bisect
import colorsys
import numpy
import six

#TODO: cleanup usage
NUM_COLORS = 255

class Color(object):
    """
    convenience class that represents integer colors of 8, 16, 32 bits each
    """

    def __init__(self, red, green, blue, alpha=None, bits=8):
        assert isinstance(red, int) and isinstance(green, int) and isinstance(blue, int)
        assert bits in (8, 16, 32)
        if alpha is not None:
            assert isinstance(alpha, int)

        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha
        self._has_alpha = alpha is not None
        self.bits = 8

    def __repr__(self):
        return str(self)

    def __str__(self):
        return str(self.to_tuple())

    def to_tuple(self):
        values = [self.red, self.green, self.blue]
        if self._has_alpha:
            values.append(self.alpha)
        return tuple(values)

    def to_hex(self):
        s = ''.join('{:02x}'.format(x) for x in (self.red, self.green, self.blue))

        # Use short form if possible
        if all((s[i] == s[i+1] for i in (0, 2, 4))):
            s = ''.join((s[0], s[2], s[4]))

        return '#{0}'.format(s).upper()

    def to_float(self):
        factor = 1.0 / float(2**self.bits - 1)
        values = [getattr(self,x) * factor for x in ('red', 'green','blue')]
        if self._has_alpha:
            values.append(self.alpha * factor)
        return tuple(values)

    def to_hsv(self):
        """
        Calculate and return HSV values as integer values
        """

        h, s, v = colorsys.rgb_to_hsv(*self.to_float()[:3])
        values = [
            int(round(h * 360)),
            int(round(s * 100)),
            int(round(v * 100)),
        ]
        if self._has_alpha:
            values.append(self.alpha)
        return tuple(values)

    @classmethod
    def from_hsv(cls, hue, saturation, value, alpha=None, bits=8):
        """
        Construct new Color instance from HSV integers
        """

        assert isinstance(hue, int) and isinstance(saturation, int) and isinstance(value, int)
        assert bits in (8, 16, 32)
        if alpha is not None:
            assert isinstance(alpha, int)

        #Convert to and from float used by colorsys functions
        red, green, blue = [int(round(x * (2**bits - 1), 0)) for x
                            in colorsys.hsv_to_rgb(float(hue) / 360.0, float(saturation) / 100.0, float(value) / 100.0)]
        return Color(red, green, blue, alpha=alpha, bits=bits)

    @classmethod
    def from_hex(cls, value, alpha=None):
        try:
            if value[0] == '#':
                value = value[1:]
            if len(value) == 3:
                value = ''.join([c*2 for c in value])
            if len(value) == 6:
                value = "{0}{1:02X}".format(value, alpha if alpha is not None else 255)
            if len(value) != 8:
                raise ValueError

            color = []
            for i in range(0, 8, 2):
                color.append(int(value[i:i+2], 16))

            return cls(*color)

        except ValueError:
            raise ValueError("Invalid hex color: {}".format(value))



def rgb_to_hsv(colors):
    """
    Convert array of 8-bit unsigned RGB colors to floating point HSV.

    Expected input: [(r,g,b)...]

    Derived from matplotlib.colors::rgb_to_hsv
    """

    if not isinstance(colors, numpy.ndarray):
        colors = numpy.asarray(colors).astype(numpy.uint8)

    assert len(colors.shape) == 2 and colors.shape[-1] == 3
    assert colors.dtype == numpy.uint8

    colors = colors / 255.0
    hsv = numpy.zeros_like(colors)
    vmax = colors.max(-1)
    vrange = numpy.ptp(colors, axis=-1)
    vmax_ge_zero = vmax > 0
    s = numpy.zeros_like(vmax)
    s[vmax_ge_zero] = vrange[vmax_ge_zero] / vmax[vmax_ge_zero]

    vrange_ge_zero = vrange > 0
    # red is max
    idx = (colors[..., 0] == vmax) & vrange_ge_zero
    hsv[idx, 0] = (colors[idx, 1] - colors[idx, 2]) / vrange[idx]
    # green is max
    idx = (colors[..., 1] == vmax) & vrange_ge_zero
    hsv[idx, 0] = 2. + (colors[idx, 2] - colors[idx, 0]) / vrange[idx]
    # blue is max
    idx = (colors[..., 2] == vmax) & vrange_ge_zero
    hsv[idx, 0] = 4. + (colors[idx, 0] - colors[idx, 1]) / vrange[idx]

    hsv[..., 0] = (hsv[..., 0] / 6.0) % 1.0
    hsv[..., 1] = s
    hsv[..., 2] = vmax
    return hsv


def hsv_to_rgb(colors):
    """
    Convert array of floating point HSV to 8-bit unsigned RGB colors.

    Expected input [(h,s,v)...]

    Derived from matplotlib.colors::hsv_to_rgb
    """

    if not isinstance(colors, numpy.ndarray):
        colors = numpy.asarray(colors)

    assert len(colors.shape) == 2 and colors.shape[-1] == 3
    assert colors.dtype.kind == 'f'

    h, s, v = colors.T
    rgb = numpy.zeros_like(colors)
    r, g, b = rgb.T

    i = (h * 6.0).astype(int)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    idx = i % 6 == 0
    r[idx] = v[idx]
    g[idx] = t[idx]
    b[idx] = p[idx]

    idx = i == 1
    r[idx] = q[idx]
    g[idx] = v[idx]
    b[idx] = p[idx]

    idx = i == 2
    r[idx] = p[idx]
    g[idx] = v[idx]
    b[idx] = t[idx]

    idx = i == 3
    r[idx] = p[idx]
    g[idx] = q[idx]
    b[idx] = v[idx]

    idx = i == 4
    r[idx] = t[idx]
    g[idx] = p[idx]
    b[idx] = v[idx]

    idx = i == 5
    r[idx] = v[idx]
    g[idx] = p[idx]
    b[idx] = q[idx]

    idx = s == 0
    r[idx] = v[idx]
    g[idx] = v[idx]
    b[idx] = v[idx]

    return (rgb * 255).astype(numpy.uint8)


def interpolate_linear(colors, values, num_colors, colorspace="hsv"):
    """
    Interpolates colors based on the positions of values.

    :param colors: the numpy array (must be uint8) of colors to interpolate between.
    :param values: the values that correspond to the colors (order must match).  Used to determine the position of each color w/in interpolation.
    :param num_colors: number of new colors to create.
    :param colorspace: hsv or rgb, determines the colorspace of the interpolation method
    """

    if not isinstance(colors, numpy.ndarray):
        colors = numpy.asarray(colors).astype(numpy.uint8)

    assert len(colors.shape) == 2
    assert colors.shape[0] > 1
    assert len(colors) == len(values)
    assert colors.dtype == numpy.uint8

    min_value = min(values)
    value_range = max(values) - min_value
    if value_range == 0:
        factor = 1.0
    else:
        factor = float(num_colors-1) / value_range

    target_x = numpy.arange(0, num_colors)
    x = []
    for value in values:
        x.append((value - min_value) * factor)

    if colorspace == "rgb":
        src_colors = colors.T
        target_colors = numpy.zeros((src_colors.shape[0], num_colors))
        for i in range(0, target_colors.shape[0]):
            target_colors[i] = numpy.interp(target_x, x, src_colors[i])
        return target_colors.T.astype(numpy.uint8)
    else:
        hsv = rgb_to_hsv(colors[..., :3]).T

        target_hsv = numpy.zeros((hsv.shape[0], num_colors))

        # Interpolate saturation and value
        for i in range(1, target_hsv.shape[0]):
            target_hsv[i] = numpy.interp(target_x, x, hsv[i])

        # Interpolate hue separately, since it has some special conditions
        for i in six.moves.range(1, len(hsv[0])):
            lo_h = hsv[0][i-1]
            hi_h = hsv[0][i]
            lo_s = hsv[1][i-1]
            hi_s = hsv[1][1]
            lo_x = x[i-1]
            hi_x = x[i]
            lo_idx = bisect.bisect_left(target_x, lo_x)
            hi_idx = bisect.bisect_left(target_x, hi_x)

            # Make sure we interpolate through the last position in palette
            if hi_idx == len(target_x) - 1:
                hi_idx = len(target_x)

            # Avoid moving through other colors when ramping from or to a shade of grey.
            if lo_s == 0:
                lo_h = hi_h
            elif hi_s == 0:
                hi_h = lo_h

            target_hsv[0][lo_idx:hi_idx] = numpy.interp(target_x[lo_idx:hi_idx], [lo_x, hi_x], [lo_h, hi_h])

        if colors.shape[1] == 4:
            r, g, b = hsv_to_rgb(target_hsv.T).T
            a = numpy.interp(target_x, x, colors[..., 3].T).astype(numpy.uint8)
            return numpy.vstack((r, g, b, a)).T.astype(numpy.uint8)
        else:
            return hsv_to_rgb(target_hsv.T).astype(numpy.uint8)
