"""Nota diária em uma pasta do Obsidian. Cada fala vira uma linha no arquivo do dia."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

SEPARATOR = "---"
_COMMAND = re.compile(
    r"^\s*nova\s+anota(?:ção|cao)\b[\s,.;:!?…-]*",
    re.IGNORECASE,
)


def render_entry(text: str) -> str:
    """Texto da fala, ou o separador quando a fala começa com 'nova anotação'."""
    cleaned = text.strip()
    match = _COMMAND.match(cleaned)
    if not match:
        return cleaned
    rest = cleaned[match.end() :].strip()
    # Linha em branco antes e depois, para o Obsidian desenhar a régua
    # e não ler o "---" como título ou metadado.
    block = f"\n{SEPARATOR}\n"
    if rest:
        return f"{block}\n{rest}"
    return block


def daily_note_path(folder: Path, when: date) -> Path:
    return folder / f"{when.day:02d}-{when.month:02d}-{when.year}.md"


def append_daily_note(folder: str | Path, text: str, when: date | None = None) -> Path:
    """Acrescenta a fala na nota do dia. Cria o arquivo se ele ainda não existe."""
    vault = Path(folder)
    if not vault.is_dir():
        raise FileNotFoundError(f"Pasta do Obsidian não encontrada: {vault}")

    path = daily_note_path(vault, when or date.today())
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + render_entry(text) + "\n", encoding="utf-8")
    return path
