"""Pastas de reunião no Obsidian: DD-MM-YYYY/meets/<nome>/{Transcricao,Resumo}.md"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class MeetingPaths:
    folder: Path
    transcript: Path
    summary: Path


def day_folder_name(when: date) -> str:
    """Mesmo esquema de data da nota diária: DD-MM-YYYY."""
    return f"{when.day:02d}-{when.month:02d}-{when.year}"


def sanitize_meeting_name(name: str) -> str:
    cleaned = _UNSAFE.sub("-", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    return cleaned[:80] or "Reuniao"


def unique_meeting_folder(parent: Path, name: str) -> Path:
    """Cria pasta única: Nome, Nome (2), Nome (3), …"""
    base = sanitize_meeting_name(name)
    candidate = parent / base
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = parent / f"{base} ({n})"
        if not candidate.exists():
            return candidate
        n += 1


def create_meeting_notes(
    vault: str | Path,
    meeting_name: str,
    transcript_md: str,
    summary_md: str,
    when: date | None = None,
) -> MeetingPaths:
    """
    Cria:
      <vault>/DD-MM-YYYY/meets/<nome>/Transcricao.md
      <vault>/DD-MM-YYYY/meets/<nome>/Resumo.md
    """
    root = Path(vault)
    if not root.is_dir():
        raise FileNotFoundError(f"Pasta do Obsidian não encontrada: {root}")

    day = when or date.today()
    meets_root = root / day_folder_name(day) / "meets"
    meets_root.mkdir(parents=True, exist_ok=True)
    folder = unique_meeting_folder(meets_root, meeting_name)
    folder.mkdir(parents=True, exist_ok=False)

    transcript_path = folder / "Transcricao.md"
    summary_path = folder / "Resumo.md"
    stamp = datetime.now().strftime("%H:%M")
    title = sanitize_meeting_name(meeting_name)

    transcript_path.write_text(
        f"# {title}\n\n_Gravada em {day_folder_name(day)} às {stamp}_\n\n{transcript_md.strip()}\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        f"# Resumo — {title}\n\n{summary_md.strip()}\n",
        encoding="utf-8",
    )
    return MeetingPaths(folder, transcript_path, summary_path)


def format_transcript(utterances: list[tuple[float, str, str]]) -> str:
    """utterances: (start_seconds, speaker, text) ordenados."""
    lines: list[str] = []
    for start, speaker, text in utterances:
        text = text.strip()
        if not text:
            continue
        m, s = divmod(int(start), 60)
        h, m = divmod(m, 60)
        stamp = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        lines.append(f"**[{stamp}] {speaker}:** {text}")
    return "\n\n".join(lines) if lines else "_Nada foi transcrito._"


def merge_speaker_segments(
    mine: list[tuple[float, float, str]],
    theirs: list[tuple[float, float, str]],
    *,
    coalesce_gap: float = 0.85,
) -> list[tuple[float, str, str]]:
    """Junta falas dos dois canais numa linha do tempo.

    Cada item é (start, end, text). Ordena por início (depois fim) e funde
    falas seguidas do mesmo falante quando o buraco é pequeno.
    """
    items: list[tuple[float, float, str, str]] = [
        (start, end, "Eu", text) for start, end, text in mine if text.strip()
    ]
    items.extend((start, end, "Outro", text) for start, end, text in theirs if text.strip())
    items.sort(key=lambda x: (x[0], x[1], 0 if x[2] == "Eu" else 1))

    if not items:
        return []

    merged: list[tuple[float, float, str, str]] = [items[0]]
    for start, end, speaker, text in items[1:]:
        prev_start, prev_end, prev_speaker, prev_text = merged[-1]
        if speaker == prev_speaker and start - prev_end <= coalesce_gap:
            merged[-1] = (
                prev_start,
                max(prev_end, end),
                speaker,
                f"{prev_text.rstrip()} {text.lstrip()}".strip(),
            )
        else:
            merged.append((start, end, speaker, text))

    return [(start, speaker, text) for start, _end, speaker, text in merged]
