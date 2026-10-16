from datetime import date

import pytest

from pluto.meeting_notes import (
    create_meeting_notes,
    day_folder_name,
    format_transcript,
    merge_speaker_segments,
    sanitize_meeting_name,
    unique_meeting_folder,
)


def test_day_folder_matches_daily_note_scheme():
    assert day_folder_name(date(2026, 10, 15)) == "15-10-2026"


def test_sanitize_meeting_name():
    assert sanitize_meeting_name('  Sync: Q3/OK?  ') == "Sync- Q3-OK"
    assert sanitize_meeting_name("") == "Reuniao"


def test_unique_meeting_folder_appends_number(tmp_path):
    first = unique_meeting_folder(tmp_path, "Daily")
    first.mkdir()
    second = unique_meeting_folder(tmp_path, "Daily")
    assert second.name == "Daily (2)"


def test_create_meeting_notes_structure(tmp_path):
    when = date(2026, 10, 15)
    paths = create_meeting_notes(
        tmp_path,
        "Alinhamento",
        "**[00:01] Eu:** oi",
        "## Resumo\n\nOk.",
        when=when,
    )
    assert paths.folder == tmp_path / "15-10-2026" / "meets" / "Alinhamento"
    assert paths.transcript.name == "Transcricao.md"
    assert paths.summary.name == "Resumo.md"
    assert "Alinhamento" in paths.transcript.read_text(encoding="utf-8")
    assert "## Resumo" in paths.summary.read_text(encoding="utf-8")


def test_create_meeting_notes_requires_vault(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_meeting_notes(tmp_path / "missing", "X", "t", "s")


def test_format_transcript():
    md = format_transcript([(65.0, "Eu", "olá"), (70.2, "Outro", "e aí")])
    assert "**[01:05] Eu:** olá" in md
    assert "**[01:10] Outro:** e aí" in md


def test_merge_orders_by_start_then_end():
    mine = [(1.0, 2.0, "oi"), (5.0, 6.0, "valeu")]
    theirs = [(0.5, 1.5, "e aí"), (3.0, 4.0, "beleza")]
    out = merge_speaker_segments(mine, theirs)
    assert [u[1] for u in out] == ["Outro", "Eu", "Outro", "Eu"]
    assert out[0][2] == "e aí"


def test_merge_coalesces_same_speaker():
    mine = [(1.0, 2.0, "parte um"), (2.2, 3.0, "parte dois")]
    out = merge_speaker_segments(mine, [])
    assert len(out) == 1
    assert out[0][2] == "parte um parte dois"
