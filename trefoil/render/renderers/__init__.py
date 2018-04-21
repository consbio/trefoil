import json
from PIL import Image
import numpy

from trefoil.utilities.color import Color


LEGEND_ELEMENT_BORDER_COLOR = Color(150, 150, 150, 0)
LEGEND_ELEMENT_BORDER_WIDTH = 1

class RasterRenderer(object):
    def __init__(self, colormap, fill_value, background_color):
        """
        Construct a new renderer.

        :param colormap: [(value or class break, Color object)...]
        :param fill_value: value to fill with background color (if provided) or transparent
        :param background_color: the background color to apply to all areas not specifically handled by colormap, including
        areas with fill_value or masked out.
        """

        if background_color is not None:
            assert isinstance(background_color, Color)
        else:
            background_color = Color(0, 0, 0, 0)

        self.colormap = list(colormap)
        self.fill_value = fill_value
        self.background_color = background_color
        self.colormap.sort(key=lambda x: x[0])
        self.values = numpy.array([entry[0] for entry in self.colormap])
        self._generate_palette()

    @property
    def name(self):
        return self.__class__.__name__.lower().replace('renderer', '').replace('values', '')

    def get_legend(self, image_width=20, image_height=20):
        raise NotImplementedError("Must be provided by child class")

    def render_image(self, data, row_major_order=True):
        raise NotImplementedError("Must be provided by child class")

    def _generate_palette(self):
        """
        Create the palette used by this renderer.  Sets self.palette to a numpy array of colors
        """

        raise NotImplementedError("Must be provided by child class")

    def _mask_fill_value(self, data):
        """
        Mask out the fill value, if set.  Always return an instance of a masked array.
        """

        mask = False if self.fill_value is None else (data == self.fill_value)
        return numpy.ma.masked_array(data, mask=mask)

    def _create_image(self, image_data, size):
        """
        Creates image, setting background color into image and palette
        """
        background_index = self.palette.shape[0]
        if hasattr(image_data, 'mask'):
            image_data = image_data.filled(background_index)

        image = Image.frombuffer("P", size, image_data, "raw", "P", 0, 1)

        palette = self.palette[..., :3].flatten().tolist()
        # Append background color
        palette.extend(self.background_color.to_tuple()[:3])
        image.putpalette(palette, "RGB")

        if self.background_color.alpha == 0:
            image.info['transparency'] = background_index

        return image

    def serialize(self):
        """ Returns self as a dictionary """
        ret = {
            "type": self.name,
            "colors": [(entry[0], entry[1].to_hex()) for entry in self.colormap]
        }
        if self.fill_value is not None:
            ret['options'] = {'fill_value': self.fill_value}
        # TODO: background color

        return ret

    def to_json(self, indent=4):
        """ Returns self serialized to JSON """

        return json.dumps(self.serialize(), indent=indent)