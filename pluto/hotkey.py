"""Atalho global "segurar para falar".

`parse_hotkey` é puro (testável); `HotkeyListener` usa pynput e só importa a
biblioteca quando instanciado.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

MODIFIERS = {"ctrl", "alt", "shift", "cmd"}
_MODIFIER_ALIASES = {"win": "cmd", "super": "cmd", "control": "ctrl", "option": "alt"}


@dataclass(frozen=True)
class Combo:
    modifiers: frozenset[str]
    key: str

    def is_satisfied(self, pressed: set[str]) -> bool:
        return self.modifiers <= pressed and self.key in pressed

    def involves(self, name: str) -> bool:
        return name == self.key or name in self.modifiers

    def __str__(self) -> str:
        parts = [f"<{m}>" for m in sorted(self.modifiers)]
        parts.append(f"<{self.key}>" if len(self.key) > 1 else self.key)
        return "+".join(parts)


def parse_hotkey(spec: str) -> Combo:
    """Ex.: "<ctrl>+<space>", "<f9>", "<ctrl>+<alt>+d"."""
    parts = [p.strip().lower().strip("<>").strip() for p in spec.split("+")]
    parts = [p for p in parts if p]
    if not parts:
        raise ValueError("Atalho vazio.")

    modifiers: set[str] = set()
    key: str | None = None
    for part in parts:
        part = _MODIFIER_ALIASES.get(part, part)
        if part in MODIFIERS:
            modifiers.add(part)
        elif key is None:
            key = part
        else:
            raise ValueError(f"Atalho com mais de uma tecla principal: {spec!r}")
    if key is None:
        raise ValueError("O atalho precisa de uma tecla além dos modificadores (ex.: <ctrl>+<space>).")
    return Combo(frozenset(modifiers), key)


class HotkeyListener:
    """Chama on_activate quando o combo é pressionado e on_deactivate ao soltar
    qualquer tecla dele. Suprime a tecla principal para o app em foco não reagir
    (ex.: Ctrl+Espaço abrindo autocomplete)."""

    def __init__(
        self,
        combo: Combo,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
        suppress: bool = True,
    ):
        self.combo = combo
        self.on_activate = on_activate
        self.on_deactivate = on_deactivate
        self.suppress = suppress
        self._pressed: set[str] = set()
        self._active = False
        self._lock = threading.Lock()
        self._listener = None
        self._main_vk = self._resolve_vk(combo.key)

    # --- pynput glue -------------------------------------------------------

    @staticmethod
    def _resolve_vk(name: str) -> int | None:
        from pynput.keyboard import Key, KeyCode

        if len(name) == 1:
            code = KeyCode.from_char(name)
            return code.vk if code.vk is not None else ord(name.upper())
        try:
            return Key[name].value.vk
        except KeyError:
            return None

    @staticmethod
    def _name_of(key) -> str | None:
        from pynput.keyboard import Key, KeyCode

        if isinstance(key, Key):
            name = key.name
            for mod in ("ctrl", "alt", "shift", "cmd"):
                if name == mod or name.startswith(mod + "_") or name == "alt_gr":
                    return mod
            return name
        if isinstance(key, KeyCode):
            if key.char and key.char.isprintable() and not key.char.isspace():
                return key.char.lower()
            if key.vk is not None and 0x30 <= key.vk <= 0x5A:  # 0-9, A-Z (com Ctrl segurado)
                return chr(key.vk).lower()
        return None

    def _press(self, name: str) -> None:
        fire = False
        with self._lock:
            self._pressed.add(name)
            if not self._active and self.combo.is_satisfied(self._pressed):
                self._active = True
                fire = True
        if fire:
            self._safe(self.on_activate)

    def _release(self, name: str) -> None:
        fire = False
        with self._lock:
            self._pressed.discard(name)
            if self._active and self.combo.involves(name):
                self._active = False
                fire = True
        if fire:
            self._safe(self.on_deactivate)

    def _on_press(self, key) -> None:
        name = self._name_of(key)
        if name:
            self._press(name)

    def _on_release(self, key) -> None:
        name = self._name_of(key)
        if name:
            self._release(name)

    _WM_KEYDOWN = (0x0100, 0x0104)
    _WM_KEYUP = (0x0101, 0x0105)

    def _win32_filter(self, msg, data) -> None:
        """Suprime a tecla principal enquanto os modificadores estão pressionados.

        O pynput não entrega on_press/on_release de eventos suprimidos, então o
        estado da tecla principal é atualizado aqui antes de suprimir.
        """
        if not self.suppress or self._main_vk is None or data.vkCode != self._main_vk:
            return
        with self._lock:
            modifiers_down = self.combo.modifiers <= self._pressed
        if not modifiers_down:
            return
        if msg in self._WM_KEYDOWN:
            self._press(self.combo.key)
        elif msg in self._WM_KEYUP:
            self._release(self.combo.key)
        if self._listener is not None:
            self._listener.suppress_event()

    @staticmethod
    def _safe(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001
            log.exception("Erro no callback do atalho")

    # --- API ---------------------------------------------------------------

    def start(self) -> None:
        from pynput import keyboard

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            win32_event_filter=self._win32_filter,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._lock:
            self._pressed.clear()
            self._active = False
