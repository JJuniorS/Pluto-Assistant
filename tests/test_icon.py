from pluto.icon import RED, render_icon


def test_enabled_icon_is_a_circle_with_red_center():
    image = render_icon(64, enabled=True)
    assert image.size == (64, 64)
    assert image.mode == "RGBA"
    assert image.getpixel((32, 32)) == RED
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((2, 2))[3] == 0
    assert image.getpixel((6, 32)) == (0, 0, 0, 255)


def test_paused_icon_keeps_the_shape_with_a_gray_dot():
    image = render_icon(64, enabled=False)
    red, green, blue, alpha = image.getpixel((32, 32))
    assert alpha == 255
    assert abs(red - green) < 8
    assert abs(green - blue) < 8
    assert image.getpixel((0, 0))[3] == 0
