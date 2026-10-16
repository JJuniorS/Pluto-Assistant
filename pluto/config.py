"""Configuração persistida em %APPDATA%\\PlutoAssistent\\config.json."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from pluto.cleaner import DEFAULT_FILLERS

DEFAULTS: dict[str, Any] = {
    "hotkey": "<ctrl>+<space>",
    "meeting_hotkey": "<ctrl>+<shift>+m",  # toggle: inicia/para gravação de reunião
    "input_device": None,  # nome do microfone; None = padrão do sistema
    "model_size": "auto",  # auto | tiny | base | small | medium | large-v3 | large-v3-turbo
    "device": "auto",  # auto | cuda | cpu
    "fillers": list(DEFAULT_FILLERS),
    "dictionary": ["Pluto Assistant"],
    "snippets": {"meu linkedin": "https://www.linkedin.com/in/seu-perfil/"},
    "history_limit": 200,
    "min_audio_seconds": 0.4,
    "obsidian_dir": "",  # pasta do cofre; vazio = cola no app em foco
    # Resumo de reunião: OpenAI (gpt-4o-mini, mais barato) ou Anthropic (Haiku).
    "llm_provider": "openai",  # openai | anthropic
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",  # anthropic: claude-haiku-4-5
}


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "PlutoAssistent"


def default_config_path() -> Path:
    return app_data_dir() / "config.json"


class Config:
    """Atributos = chaves de DEFAULTS. Chaves desconhecidas no arquivo são ignoradas."""

    hotkey: str
    meeting_hotkey: str
    input_device: str | None
    model_size: str
    device: str
    fillers: list[str]
    dictionary: list[str]
    snippets: dict[str, str]
    history_limit: int
    min_audio_seconds: float
    obsidian_dir: str
    llm_provider: str
    llm_api_key: str
    llm_model: str

    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path) if path else default_config_path()
        data = deepcopy(DEFAULTS)
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key in DEFAULTS:
                    if key in loaded:
                        data[key] = loaded[key]
        except (OSError, ValueError):
            pass
        self.__dict__.update(data)

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in DEFAULTS}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
