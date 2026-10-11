"""Histórico de transcrições em JSON Lines (uma por linha, mais antiga primeiro)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pluto.config import app_data_dir


def default_history_path() -> Path:
    return app_data_dir() / "history.jsonl"


class History:
    def __init__(self, path: str | os.PathLike[str] | None = None, limit: int = 200):
        self.path = Path(path) if path else default_history_path()
        self.limit = max(1, int(limit))

    def _read_all(self) -> list[dict[str, Any]]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        items: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except ValueError:
                continue
        return items

    def _write_all(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8"
        )

    def append(self, text: str, raw: str, seconds: float) -> None:
        items = self._read_all()
        items.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "text": text,
                "raw": raw,
                "seconds": round(float(seconds), 2),
            }
        )
        self._write_all(items[-self.limit :])

    def read(self) -> list[dict[str, Any]]:
        """Mais recente primeiro."""
        return list(reversed(self._read_all()))

    def clear(self) -> None:
        self._write_all([])
