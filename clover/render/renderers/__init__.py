from PIL import Image
import numpy

from clover.utilities.color import Color


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

        self.colormap = list(colormap)
        self.fill_value = fill_value
        self.background_color = background_color
        self.colormap.sort(key=lambda x: x[0])
        self.values = numpy.array([entry[0] for entry in self.colormap])
        self._generate_palette()


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

        if self.fill_value is not None:
            return numpy.ma.masked_array(data, mask=data == self.fill_value)
        else:
            return numpy.ma.masked_array(data)

    def _set_image_palette(self, image):
        """
        Set palette into PIL image.  Only RGB values are used.
        TODO: figure out how to simply add transparency to palette
        """

        palette = self.palette[..., :3].flatten().tolist()
        if self.background_color is not None:
            assert isinstance(self.background_color, Color)
            palette.extend(self.background_color.to_tuple()[:3])
        image.putpalette(palette, "RGB")

    def _apply_transparency_mask_to_image(self, image, mask):
        """
        Apply mask as transparency layer in image.  Convert it to RGBA if necessary.
        :param mask: boolean numpy array, where True indicates pixels to set as transparent
        """

        if not image.mode == "RGBA":
            image = image.convert("RGBA")
        image.putalpha(Image.frombuffer("L", image.size, (mask * 255).astype(numpy.uint8), "raw", "L", 0, 1))
        return image

#
# class RendererManager:
#     '''Class to manage available renderers.'''
#
#     @staticmethod
#     def getRendererHash(rendererId, args):
#         '''Get a unique hash for the given rendering information.
#
#         Useful for caching without loading the named renderer.
#
#         Arguments:
#         rendererId -- The renderer id.
#         args -- A dictionary of keyword arguments to be given to the renderer.
#         '''
#
#         m = hashlib.md5()
#
#         m.update(rendererId)
#         for key in args:
#             m.update(key + "=")
#             m.update(str(args[key]))
#
#         return m.hexdigest()
#
#     def __init__(self):
#         '''Constructor. Loads a list of available renderers.'''
#
#         self.renderers = { }
#
#         path = os.path.join(os.path.dirname(__file__), "renderers")
#         for name in os.listdir(path):
#             if len(name) > 3 and name[-3:].lower() == ".py" and not os.path.isdir(name) and name.lower() != "__init__.py":
#                 module = __import__("ncserve.base.renderers", fromlist=[name[:-3]]).__dict__[name[:-3]]
#                 renderer = module.getRendererClass()
#                 self.renderers[renderer.id] = renderer
