"""Insere texto no aplicativo em foco via clipboard + Ctrl+V, restaurando o
clipboard (texto) em seguida. Funciona com acentos em qualquer app."""

from __future__ import annotations

import logging
import threading
import time

import pyperclip

log = logging.getLogger(__name__)


def paste_text(text: str, restore_delay: float = 0.4) -> None:
    from pynput.keyboard import Controller, Key

    previous: str | None
    try:
        previous = pyperclip.paste()
    except Exception:  # noqa: BLE001
        previous = None

    pyperclip.copy(text)
    time.sleep(0.05)

    keyboard = Controller()
    # Garante que nenhum modificador do atalho continue "preso" na simulação.
    for key in (Key.shift, Key.alt, Key.cmd):
        keyboard.release(key)
    with keyboard.pressed(Key.ctrl):
        keyboard.press("v")
        keyboard.release("v")

    if previous:
        threading.Timer(restore_delay, _restore, args=(previous,)).start()


def _restore(previous: str) -> None:
    try:
        pyperclip.copy(previous)
    except Exception:  # noqa: BLE001
        log.debug("Não foi possível restaurar o clipboard.", exc_info=True)
