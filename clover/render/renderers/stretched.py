from PIL import Image
import numpy

from clover.utilities.format import PrecisionFormatter
from clover.utilities.color import interpolate_linear
from clover.render.renderers import RasterRenderer
from clover.render.renderers.legend import LegendElement


def getRendererClass():
    return StretchedRenderer

class StretchedRenderer(RasterRenderer):
    def __init__(self, colormap, fill_value=None, background_color=None, method="linear", colorspace="hsv"):
        """
        Maps a stretched color palette against the data range according to a particular method
        (e.g., linear from min to max value).

        :param linear: apply a linear stretch between min and max values
        :param colorspace: the colorspace in which to do color interpolation
        """

        assert len(colormap) >= 2

        self.method = method
        self.colorspace = colorspace
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

            for value in tick_values:
                tick_positions.append((value - self.min_value) / value_range)
                labels.append(formatter.format(value))

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

    def render_image(self, data, row_major_order=True):
        num_colors = self.palette.shape[0]
        factor = float(num_colors) / float(self.max_value - self.min_value)
        img_size = data.shape[::-1] if row_major_order else data.shape[:2] # have to invert because PIL thinks about this backwards
        values = self._mask_fill_value(data.ravel())

        #derive palette index, and clip to [0,num_colors]
        image_data = ((values - self.min_value) * factor).astype(numpy.int).clip(0, num_colors-1).astype(numpy.uint8)

        if self.background_color:
            image_data[values.mask] = num_colors

        img = Image.frombuffer("P", img_size, image_data, "raw", "P", 0, 1)
        self._set_image_palette(img)

        if self.background_color is None and values.mask.shape:
            img = self._apply_transparency_mask_to_image(img, (values.mask == False))

        return img

    def _generate_palette(self):
        self.min_value = self.colormap[0][0]
        self.max_value = self.colormap[len(self.colormap)-1][0]
        colors = numpy.asarray([entry[1].to_tuple() for entry in self.colormap]).astype(numpy.uint8)

        if self.method == "linear":
            palette_size = 128  # visually indistinguishable from 255 value palette, with smaller file size
            if len(self.colormap) > 20:
                palette_size = 255
            self.palette = interpolate_linear(colors, self.values, palette_size, colorspace=self.colorspace)
        else:
            raise NotImplementedError("Other stretched render methods not built!")

    def serialize(self):
        ret = super(StretchedRenderer, self).serialize()

        if 'options' in ret:
            ret['options']['color_space'] = self.colorspace
        else:
            ret['options'] = {'color_space': self.colorspace}

        return ret