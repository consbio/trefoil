from trefoil.utilities.color import Color


def test_color():
    color_tuple = (0, 0, 0)
    c = Color(*color_tuple)
    assert c.to_tuple() == color_tuple
    assert c.to_hex() == "#000"
    c2 = Color.from_hsv(*c.to_hsv())
    assert c2.to_tuple() == color_tuple

    assert Color.from_hex("#000000", alpha=100)
