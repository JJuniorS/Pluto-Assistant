from pluto.hotkey import parse_hotkey, Combo


def test_parse_ctrl_space():
    combo = parse_hotkey("<ctrl>+<space>")
    assert combo.modifiers == {"ctrl"}
    assert combo.key == "space"


def test_parse_single_function_key():
    combo = parse_hotkey("<f9>")
    assert combo.modifiers == set()
    assert combo.key == "f9"


def test_parse_with_letter_and_two_modifiers():
    combo = parse_hotkey("<ctrl>+<alt>+d")
    assert combo.modifiers == {"ctrl", "alt"}
    assert combo.key == "d"


def test_parse_is_case_and_space_insensitive():
    assert parse_hotkey(" <Ctrl> + <SPACE> ") == Combo(frozenset({"ctrl"}), "space")


def test_parse_rejects_only_modifiers():
    import pytest

    with pytest.raises(ValueError):
        parse_hotkey("<ctrl>+<shift>")


def test_combo_matches_pressed_set():
    combo = parse_hotkey("<ctrl>+<space>")
    assert combo.is_satisfied({"ctrl", "space"})
    assert combo.is_satisfied({"ctrl", "shift", "space"})
    assert not combo.is_satisfied({"space"})
    assert not combo.is_satisfied({"ctrl"})


def test_combo_str_roundtrip():
    assert str(parse_hotkey("<ctrl>+<space>")) == "<ctrl>+<space>"
    assert str(parse_hotkey("<f9>")) == "<f9>"
