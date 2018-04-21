from PIL import Image
import numpy

from trefoil.utilities.format import PrecisionFormatter
from trefoil.render.renderers import RasterRenderer
from trefoil.render.renderers.legend import LegendElement

LEGEND_TICK_POSITION = 0.5  # center-aligned with legend image


class ClassifiedRenderer(RasterRenderer):
    def __init__(self, colormap, fill_value=None, background_color=None):
        """
        Maps class breaks to colors.  Values <= break (and greater than previous break) are assigned the color for that break

        :param colormap:
            [
                (break1, Color1),  # all values <= break1 get Color1
                (break2, Color2),  # all values > break1 and <= break2 get Color2
                ...
                (max, ColorN),  # max can be numpy.inf to apply the renderer to multiple value ranges
            ]
        """

        assert len(colormap) >= 2

        super(ClassifiedRenderer, self).__init__(colormap, fill_value, background_color)

    def get_legend(self, image_width=20, image_height=20, min_value=None, max_value=None):
        format_values = list(self.values)
        if min_value is not None:
            format_values.append(min_value)
        if numpy.inf in format_values:
            format_values.remove(numpy.inf)
        formatter = PrecisionFormatter(format_values)
        legend_elements = []
        num_breaks = len(self.values)

        for index in range(0, num_breaks):
            img = Image.new("RGBA", (image_width, image_height), tuple(self.palette[index]))
            if index == 0:
                if min_value is not None:
                    label = "%s - %s" % (formatter.format(min_value), formatter.format(self.values[0]))
                else:
                    label = "<= %s" % formatter.format(self.values[0])
            elif index == (num_breaks - 1):
                if max_value is not None:
                    label = "%s - %s" % (formatter.format(self.values[index-1]), formatter.format(max_value))
                else:
                    label = "> %s" % formatter.format(self.values[index-1])
            else:
                label = "%s - %s" % (formatter.format(self.values[index-1]), formatter.format(self.values[index]))
            legend_elements.append(LegendElement(
                img,
                [LEGEND_TICK_POSITION],
                [label]
            ))

        return legend_elements

    def render_image(self, data, row_major_order=True):
        values = self._mask_fill_value(data.ravel())
        classified = numpy.digitize(values, self.values).astype(numpy.uint8)
        image_data = numpy.ma.masked_array(classified, mask=values.mask)

        # have to invert dimensions because PIL thinks about this backwards
        size = data.shape[::-1] if row_major_order else data.shape[:2]
        return self._create_image(image_data, size)

    def _generate_palette(self):
        self.palette = numpy.asarray([entry[1].to_tuple() for entry in self.colormap]).astype(numpy.uint8)
