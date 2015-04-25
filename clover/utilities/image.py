from PIL import ImageDraw

from clover.utilities.color import Color


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