from PIL import Image
import numpy

from trefoil.render.renderers import RasterRenderer
from trefoil.render.renderers.legend import LegendElement
from trefoil.utilities.format import PrecisionFormatter


LEGEND_TICK_POSITION = 0.5


class UniqueValuesRenderer(RasterRenderer):
    def __init__(self, colormap, fill_value=None, background_color=None, labels=None):
        """
        Maps unique values to colors.  Any color not mapped is set to transparent or background_color.

        :param colormap: list of value, Color instances: [(value, Color)...]
        """

        assert len(colormap) > 0

        super(UniqueValuesRenderer, self).__init__(colormap, fill_value, background_color)
        if labels:
            assert len(colormap) == len(labels)
            self.labels = labels
        else:
            self.labels = []

    def get_legend(self, image_width=20, image_height=20):
        legend_elements = []
        if self.labels:
            labels = self.labels
        else:
            formatter = PrecisionFormatter(self.values)
            labels = [formatter.format(x) for x in self.values]

        for index, value in enumerate(self.values):
            legend_elements.append(LegendElement(
                Image.new("RGBA", (image_width, image_height), tuple(self.palette[index])),
                [LEGEND_TICK_POSITION],
                [labels[index]]
            ))
        return legend_elements

    def render_image(self, data, row_major_order=True):
        values = self._mask_fill_value(data.ravel())

        max_value = max(values.max(), self.values.max())
        if values.dtype.kind == 'u' and max_value < 65536:
            palette_indices = numpy.zeros(max_value + 1, dtype=numpy.uint8)
            palette_indices.fill(self.values.shape[0])
            for index, value in enumerate(self.values):
                palette_indices.itemset(value, index)
            image_data = palette_indices[values].astype(numpy.uint8)
        else:
            image_data = numpy.zeros(values.shape, dtype=numpy.uint8)
            image_data.fill(self.values.shape[0])
            for index, value in enumerate(self.values):
                image_data[values == value] = index

         # have to invert dimensions because PIL thinks about this backwards
        size = data.shape[::-1] if row_major_order else data.shape[:2]
        return self._create_image(image_data, size)

    def _generate_palette(self):
        self.palette = numpy.asarray([entry[1].to_tuple() for entry in self.colormap]).astype(numpy.uint8)

    def serialize(self):
        ret = super(UniqueValuesRenderer, self).serialize()
        if self.labels:
            if 'options' in ret:
                ret['options']['labels'] = self.labels
            else:
                ret['options'] = {'labels': self.labels}

        return ret