from PIL import Image, ImageDraw, ImageChops

from trefoil.utilities.color import Color


def add_border(image, width, color):
    if isinstance(color, Color):
        color = color.to_tuple()
    color=color[:3]

    image_width, image_height = image.size
    canvas = ImageDraw.Draw(image)
    offset = int(round(width/2.0))
    canvas.line(((0, 0), (0, image_height)), fill=color, width=width)
    canvas.line(((0, 0), (image_width, 0)), fill=color, width=width)
    canvas.line(((0, image_height-offset), (image_width, image_height-offset)), fill=color, width=width)
    canvas.line(((image_width-offset, 0), (image_width-offset, image_height)), fill=color, width=width)


def autocrop(image, background=None):
    """
    Automatically crop to the bounds of non-background pixels.
    """

    # Derived from: http://stackoverflow.com/questions/10615901/trim-whitespace-using-pil

    assert image.mode == 'RGBA'

    if not background:
        background = (255, 255, 255, 0)

    background_img = Image.new("RGBA", image.size, color=background)
    diff = ImageChops.difference(image, background_img)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return image.crop(bbox)

    return image