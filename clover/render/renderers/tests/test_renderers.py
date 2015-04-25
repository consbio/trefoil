import numpy

from clover.utilities.color import Color
from clover.render.renderers.stretched import StretchedRenderer
from clover.render.renderers.classified import ClassifiedRenderer
from clover.render.renderers.unique import UniqueValuesRenderer
from clover.render.renderers.utilities import get_renderer_by_name


def test_stretched_renderer(tmpdir):
    data = numpy.zeros((100,100))
    for i in range(0, 100):
        data[i] = i
    colors = (
        (data.min(), Color(255,0,0,255)),
        (data.max(), Color(0,0,255,255))
    )
    renderer = StretchedRenderer(colors)

    img = renderer.render_image(data)
    assert len(img.getpalette()) / 3 == 256
    assert img.size == (100,100)
    img.save(str(tmpdir.join("stretched.png")))

    legend = renderer.get_legend(20,20)
    assert len(legend) == 1
    assert legend[0].image.size == (20,20)
    legend[0].image.save(str(tmpdir.join("stretched_legend.png")))

    legend = renderer.get_legend(20, 20, discrete_images=True)
    assert len(legend) == 2
    assert legend[0].image.size == (20, 20)


def test_classified_rendererer(tmpdir):
    data = numpy.zeros((100,100))
    for i in range(0, 100):
        data[i] = i
    colors = (
        (10, Color(255,0,0,255)),
        (50, Color(0,255,0,255)),
        (data.max(), Color(0,0,255,255))
    )
    renderer = ClassifiedRenderer(colors)

    img = renderer.render_image(data)
    img.save(str(tmpdir.join("classified.png")))
    assert img.palette.palette == '\xff\x00\x00\x00\xff\x00\x00\x00\xff'
    assert img.size == (100,100)

    legend = renderer.get_legend(20,20)
    assert len(legend) == 3
    for index, element in enumerate(legend):
        element.image.save(str(tmpdir.join("classified_legend_%i.png" % index)))


def test_uniquevalues_renderer(tmpdir):
    data = numpy.zeros((100,100))
    data[10:25] = 10
    data[35:50] = 25
    data[50:75] = 50
    data[85:100] = 100
    colors = (
        (10, Color(255,0,0,255)),
        (25, Color(255,255,255,255)),
        (50, Color(0,255,0,255)),
        (100, Color(0,0,255,255))
    )
    renderer = UniqueValuesRenderer(colors)
    img = renderer.render_image(data)
    img.save(str(tmpdir.join("unique.png")))
    assert img.palette.palette == '\xff\x00\x00\xff\xff\xff\x00\xff\x00\x00\x00\xff'
    assert img.size == (100,100)
    legend = renderer.get_legend(20,20)
    assert len(legend) == 4
    for index, element in enumerate(legend):
        element.image.save(str(tmpdir.join("uniquevalues_legend_%i.png" % index)))

def test_get_renderers_by_name():
    data = numpy.zeros((100,100))
    for i in range(0, 100):
        data[i] = i
    colors = (
        (10, Color(255,0,0,255)),
        (50, Color(0,255,0,255)),
        (data.max(), Color(0,0,255,255))
    )
    renderer = get_renderer_by_name("classified")(colors)
    img = renderer.render_image(data)
    assert img.palette.palette == '\xff\x00\x00\x00\xff\x00\x00\x00\xff'
    assert img.size == (100,100)