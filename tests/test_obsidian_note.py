from datetime import date

import pytest

from pluto.obsidian_note import SEPARATOR, append_daily_note, render_entry


def test_render_entry_keeps_plain_text():
    assert render_entry("Comprei pão.") == "Comprei pão."


def test_render_entry_turns_command_into_separator():
    assert render_entry("Nova anotação.") == f"\n{SEPARATOR}\n"
    assert render_entry("nova anotacao") == f"\n{SEPARATOR}\n"


def test_render_entry_puts_the_rest_under_the_separator():
    assert render_entry("Nova anotação. Comprei pão.") == f"\n{SEPARATOR}\n\nComprei pão."


def test_daily_file_is_created_and_each_utterance_is_a_new_line(tmp_path):
    when = date(2026, 10, 11)
    path = append_daily_note(tmp_path, "Primeira fala.", when=when)
    append_daily_note(tmp_path, "Segunda fala.", when=when)

    assert path.name == "11-10-2026.md"
    assert path.read_text(encoding="utf-8") == "Primeira fala.\nSegunda fala.\n"


def test_separator_is_appended_on_its_own_line(tmp_path):
    when = date(2026, 10, 11)
    append_daily_note(tmp_path, "Antes.", when=when)
    append_daily_note(tmp_path, "Nova anotação.", when=when)
    append_daily_note(tmp_path, "Depois.", when=when)

    assert (tmp_path / "11-10-2026.md").read_text(encoding="utf-8") == (
        f"Antes.\n\n{SEPARATOR}\n\nDepois.\n"
    )


def test_missing_folder_is_an_error(tmp_path):
    missing = tmp_path / "nao-existe"
    with pytest.raises(FileNotFoundError):
        append_daily_note(missing, "Oi.", when=date(2026, 10, 11))
