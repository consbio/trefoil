from . import *
from clover.utilities.format import PrecisionFormatter
from clover.render.renderers.legend import LegendElement

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
        img_size = data.shape[::-1] if row_major_order else data.shape[:2] # have to invert because PIL thinks about this backwards
        values = self._mask_fill_value(data.ravel())

        image_data = numpy.digitize(values, self.values).astype(numpy.uint8)
        if self.background_color:
            image_data[values.mask] = self.palette.shape[0]

        img = Image.frombuffer("P", img_size, image_data, "raw", "P", 0, 1)
        self._set_image_palette(img)
        if self.background_color is None and values.mask.shape:
            img = self._apply_transparency_mask_to_image(img, (values.mask == False))

        return img


    def _generate_palette(self):
        self.palette = numpy.asarray([entry[1].to_tuple() for entry in self.colormap]).astype(numpy.uint8)
