from base64 import b64encode
from PIL import Image, ImageDraw, ImageFont
from six import BytesIO
from trefoil.utilities.image import autocrop


class LegendElement(object):
    def __init__(self, image, ticks, labels):
        """
        :param image: PIL image
        :param ticks: the normalized offsets from the bottom (0) to the top (1) of the image (floating point)
        :param labels: the labels that correspond to the ticks at the same position
        """

        assert len(ticks) == len(labels)

        self.image = image
        self.ticks = ticks
        self.labels = labels

    @property
    def image_base64(self):
        if self.image:
            out = BytesIO()
            self.image.save(out, "PNG")
            return b64encode(out.getvalue()).decode('utf-8')
        return None

    def to_image(self):
        """render entire legend with labels to a new image"""

        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()

        text_width = max([font.getsize(l)[0] for l in self.labels]) + 20
        text_height = font.getsize(self.labels[0])[1]
        half_text_height = int(round(text_height / 2.0))
        label_x_padding = 10

        width = self.image.size[0] + text_width
        height = self.image.size[1]

        img = Image.new("RGBA", (width, height + 2 * text_height), color=(255,255,255,0))
        img.paste(self.image, (0, text_height))

        canvas = ImageDraw.Draw(img)

        for index, label in enumerate(self.labels):
            label_x = self.image.size[0] + label_x_padding
            label_y = int(round(float(1 - self.ticks[index]) * height - half_text_height)) + text_height
            line_x = self.image.size[0] + 2
            line_y = label_y + half_text_height
            canvas.line((line_x, line_y, line_x + label_x_padding - 6, line_y), fill=(150,150,150,255), width=1)
            canvas.text((label_x, label_y), label, font=font, fill=(0,0,0,255))

        return img


def composite_elements(elements, padding=0):
    """
    Return a new image created from compositing elements together, starting from
    the top of the image.
    """

    images = [autocrop(e.to_image()) for e in elements]
    widths = [i.size[0] for i in images]
    heights = [i.size[1] for i in images]

    img = Image.new("RGBA", (max(widths), sum(heights) + len(heights) * padding),
                    color=(255, 255, 255, 0))

    offset = 0
    for index, element_image in enumerate(images):
        img.paste(element_image, (0, offset))
        offset += element_image.size[1] + padding

    return img