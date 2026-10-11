"""Ponto de entrada do Pluto Assistant."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from pluto.config import app_data_dir


def _setup_logging() -> None:
    app_data_dir().mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            app_data_dir() / "pluto.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:  # pythonw.exe não tem console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()
    from pluto.app import PlutoApp

    PlutoApp().run()


if __name__ == "__main__":
    main()
