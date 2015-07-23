from PIL import Image
import numpy

from clover.render.renderers import RasterRenderer
from clover.render.renderers.legend import LegendElement
from clover.utilities.format import PrecisionFormatter


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
        img_size = data.shape[::-1] if row_major_order else data.shape[:2] # have to invert because PIL thinks about this backwards
        values = self._mask_fill_value(data.ravel())
        mask = values.mask

        max_value = max(values.max(), self.values.max())
        if values.dtype.kind == 'u' and max_value < 65536:
            palette_indices = numpy.zeros(max_value + 1)
            palette_indices.fill(-1)
            for index, value in enumerate(self.values):
                palette_indices.itemset(value, index)
            palette_indices = numpy.ma.masked_array(palette_indices, mask=palette_indices == -1).astype(numpy.uint16)
            image_data = palette_indices[values].astype(numpy.uint8)
            mask = numpy.logical_or(mask, image_data.mask)
        else:
            image_data = numpy.zeros(values.shape).astype(numpy.int)
            image_data.fill(-1)
            for index, value in enumerate(self.values):
                image_data[values == value] = index
            mask = numpy.logical_or(mask, image_data == -1)
            image_data = image_data.astype(numpy.uint8)

        if self.background_color:
            image_data[values.mask] = self.palette.shape[0]

        img = Image.frombuffer("P", img_size, image_data, "raw", "P", 0, 1)
        self._set_image_palette(img)
        if self.background_color is None and mask.shape:
            img = self._apply_transparency_mask_to_image(img, (mask == False))

        return img


    def _generate_palette(self):
        self.palette = numpy.asarray([entry[1].to_tuple() for entry in self.colormap]).astype(numpy.uint8)

    def serialize(self):
        ret = super(UniqueValuesRenderer, self).serialize()
        if self.labels:
            ret['labels'] = self.labels

        return ret