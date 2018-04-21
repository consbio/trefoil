import six
from trefoil.render.renderers.classified import ClassifiedRenderer
from trefoil.render.renderers.stretched import StretchedRenderer
from trefoil.render.renderers.unique import UniqueValuesRenderer
from trefoil.utilities.color import Color


AVAILABLE_RENDERERS = {
    "classified": ClassifiedRenderer,
    "stretched": StretchedRenderer,
    "unique": UniqueValuesRenderer
}


def get_renderer_by_name(name):
    return AVAILABLE_RENDERERS[name]


def get_renderer_name(renderer):
    if isinstance(renderer, ClassifiedRenderer):
        return "classified"
    elif isinstance(renderer, StretchedRenderer):
        return "stretched"
    elif isinstance(renderer, UniqueValuesRenderer):
        return "unique"
    else:
        raise ValueError("Could not find name for renderer: %s" % renderer)


def renderer_from_dict(renderer_dict):
    """Returns a renderer object from a dictionary object"""

    options = renderer_dict.get('options', {})

    try:
        renderer_type = renderer_dict['type']
        renderer_colors = [(float(x[0]), Color.from_hex(x[1])) for x in renderer_dict['colors']]
        fill_value = options.get('fill_value')
        if fill_value is not None:
            fill_value = float(fill_value)
    except KeyError:
        raise ValueError("Missing required keys from renderer renderer_dicturation")

    renderer_kwargs = {
        'colormap': renderer_colors,
        'fill_value': fill_value,
        'background_color': Color(255, 255, 255, 0)
    }

    if renderer_type == "stretched":
        color_space = options.get('color_space', 'hsv').lower().strip()
        if not color_space in ('rgb', 'hsv'):
            raise ValueError("Invalid color space: {}".format(color_space))

        renderer = StretchedRenderer(colorspace=color_space, **renderer_kwargs)
    elif renderer_type == "classified":
        renderer = ClassifiedRenderer(**renderer_kwargs)
    elif renderer_type == "unique":
        try:
            labels = [six.text_type(x) for x in options.get('labels', [])]
        except TypeError:
            raise ValueError("Labels option must be an array")

        renderer = UniqueValuesRenderer(labels=labels, **renderer_kwargs)

    return renderer