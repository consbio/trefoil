from PIL import Image
import numpy

from trefoil.utilities.format import PrecisionFormatter
from trefoil.utilities.color import interpolate_linear
from trefoil.render.renderers import RasterRenderer
from trefoil.render.renderers.legend import LegendElement


def getRendererClass():
    return StretchedRenderer


# TODO: params for palette size and optimization

class StretchedRenderer(RasterRenderer):
    def __init__(self,
                 colormap,
                 fill_value=None,
                 background_color=None,
                 method="linear",
                 colorspace="hsv",
                 palette_size=None):
        """
        Maps a stretched color palette against the data range according to a particular method
        (e.g., linear from min to max value).

        :param linear: apply a linear stretch between min and max values
        :param colorspace: the colorspace in which to do color interpolation
        :param palette_size: if provided, will be used as palette size.  Otherwise will default to 255 if > 20 colors in colormap, otherwise 90
        """

        assert len(colormap) >= 2

        self.method = method
        self.colorspace = colorspace

        if palette_size is not None:
            assert palette_size <= 255
            self.palette_size = palette_size
        elif len(colormap) > 20:
            self.palette_size = 255
        else:
            self.palette_size = 90

        super(StretchedRenderer, self).__init__(colormap, fill_value, background_color)

    def get_legend(self, image_width=20, image_height=100, ticks=None, breaks=None, max_precision=6, discrete_images=False):
        """
        Image is always rendered high to low.

        :param ticks: tick positions in dataset value range
        :param breaks: number of breaks between min and max to show on legend
        """

        if self.method == "linear":
            formatter = PrecisionFormatter(self.values, max_precision)

            if ticks is not None:
                if not len(ticks) >= 2:
                    raise ValueError('Must provide at least 2 ticks')
                tick_values = ticks
            elif breaks is not None:
                tick_values = numpy.linspace(self.min_value, self.max_value, breaks + 2)
            else:
                tick_values = self.values.copy()

            tick_values.sort()
            value_range = self.max_value - self.min_value

            tick_positions = []
            labels = []

            if abs(value_range) > 0:
                for value in tick_values:
                    tick_positions.append((value - self.min_value) / value_range)
                    labels.append(formatter.format(value))
            else:
                tick_positions = [0, 1.0]
                labels = [formatter.format(tick_values[0])] * 2

            if discrete_images:
                colors = numpy.asarray([entry[1].to_tuple() for entry in self.colormap]).astype(numpy.uint8)
                return [
                    LegendElement(
                        Image.new("RGBA", (image_width, image_height), tuple(colors[index])),
                        [0.5],
                        [labels[index]]
                    )
                    for index, value in enumerate(tick_values)
                ]

            else:
                legend_values = numpy.linspace(self.min_value, self.max_value, image_height)
                return [LegendElement(
                    self.render_image(numpy.array([legend_values,]).T[::-1]).resize((image_width, image_height), Image.ANTIALIAS),
                    tick_positions,
                    labels
                )]

        else:
            raise NotImplementedError("Legends not built for other stretched renderer methods")

    # TODO: handle cropping of stretched values properly (truncate above and below and set to background value?)
    def render_image(self, data, row_major_order=True):
        num_colors = self.palette.shape[0]
        if self.min_value == self.max_value:
            factor = 1.0
        else:
            factor = float(num_colors - 1) / float(self.max_value - self.min_value)

        values = self._mask_fill_value(data.ravel())

        # derive palette index, and clip to [0, num_colors - 1]
        stretched = ((values - self.min_value) * factor).astype(int)
        image_data = stretched.clip(0, num_colors - 1).astype(numpy.uint8)

        # have to invert dimensions because PIL thinks about this backwards
        size = data.shape[::-1] if row_major_order else data.shape[:2]
        return self._create_image(image_data, size)

    def _generate_palette(self):
        self.min_value = self.colormap[0][0]
        self.max_value = self.colormap[len(self.colormap)-1][0]
        colors = numpy.asarray([c[1].to_tuple() for c in self.colormap]).astype(numpy.uint8)

        if self.method == "linear":
            self.palette = interpolate_linear(colors, self.values, self.palette_size, colorspace=self.colorspace)
        else:
            raise NotImplementedError("Other stretched render methods not built!")

    def serialize(self):
        ret = super(StretchedRenderer, self).serialize()

        if 'options' in ret:
            ret['options']['color_space'] = self.colorspace
        else:
            ret['options'] = {'color_space': self.colorspace}

        return ret