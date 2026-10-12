"""Orquestração: estado, threads e tratamento de erros.

Regras de thread:
- Tk (overlay, janelas) roda na thread principal. Tudo que mexe em UI passa por
  `_ui()`, que agenda no loop do Tk.
- Atalho (pynput) e bandeja (pystray) têm threads próprias e só chamam `_ui()`.
- Carregamento do modelo e transcrição rodam em threads de trabalho.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from typing import Any

import numpy as np

from pluto import APP_NAME
from pluto.cleaner import clean
from pluto.config import Config
from pluto.history import History
from pluto.history_ui import HistoryWindow
from pluto.icon import apply_window_icon, ensure_app_id
from pluto.hotkey import HotkeyListener, parse_hotkey
from pluto.inserter import paste_text
from pluto.obsidian_note import append_daily_note
from pluto.overlay import GREEN, RED, WHITE, Overlay
from pluto.recorder import SAMPLE_RATE, Recorder, list_input_devices
from pluto.settings_ui import SettingsWindow
from pluto.snippets import expand
from pluto.transcriber import Transcriber
from pluto.tray import Tray

log = logging.getLogger(__name__)

LOADING, IDLE, RECORDING, PROCESSING, ERROR = "loading", "idle", "recording", "processing", "error"


class PlutoApp:
    def __init__(self) -> None:
        self.config = Config()
        self.history = History(limit=self.config.history_limit)
        self.enabled = True
        self.state = LOADING

        ensure_app_id()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        apply_window_icon(self.root)
        self.overlay = Overlay(self.root)

        self.recorder = Recorder(self.config.input_device)
        self.transcriber = Transcriber(self.config.model_size, self.config.device)

        self.tray = Tray(
            is_enabled=lambda: self.enabled,
            on_toggle=lambda: self._ui(self.toggle_enabled),
            on_settings=lambda: self._ui(self.open_settings),
            on_history=lambda: self._ui(self.open_history),
            on_quit=lambda: self._ui(self.quit),
        )
        self.hotkey: HotkeyListener | None = None
        self._settings_window: SettingsWindow | None = None
        self._history_window: HistoryWindow | None = None

    # --- ciclo de vida --------------------------------------------------------

    def run(self) -> None:
        self.tray.start()
        self._start_hotkey()
        threading.Thread(target=self._load_model, name="model-loader", daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.mainloop()

    def quit(self) -> None:
        log.info("Encerrando.")
        if self.hotkey:
            self.hotkey.stop()
        if self.recorder.is_recording:
            self.recorder.stop()
        self.tray.stop()
        self.root.after(50, self.root.destroy)

    def _ui(self, fn: Callable[..., Any], *args: Any) -> None:
        try:
            self.root.after(0, fn, *args)
        except RuntimeError:
            pass  # Tk já encerrado

    # --- modelo ----------------------------------------------------------------

    def _load_model(self) -> None:
        self._ui(self.overlay.show, "Carregando modelo de voz… (a primeira vez baixa o modelo)")
        try:
            self.transcriber.load()
        except Exception as exc:  # noqa: BLE001
            log.exception("Falha ao carregar o modelo")
            self.state = ERROR
            self._ui(self.overlay.flash, f"Erro ao carregar modelo: {exc}", 8000, RED)
            return
        self.state = IDLE
        where = "GPU" if self.transcriber.device_in_use == "cuda" else "CPU"
        self._ui(
            self.overlay.flash,
            f"{APP_NAME} pronto · {self.transcriber.model_in_use} na {where} · segure {self.config.hotkey} e fale",
            3500,
            GREEN,
        )

    # --- atalho ----------------------------------------------------------------

    def _start_hotkey(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
        combo = parse_hotkey(self.config.hotkey)
        self.hotkey = HotkeyListener(
            combo,
            on_activate=lambda: self._ui(self._on_hotkey_down),
            on_deactivate=lambda: self._ui(self._on_hotkey_up),
        )
        self.hotkey.start()
        log.info("Atalho registrado: %s", combo)

    def _on_hotkey_down(self) -> None:
        if not self.enabled:
            return
        if self.state == LOADING:
            self.overlay.flash("O modelo ainda está carregando…", 1500)
            return
        if self.state == ERROR:
            self.overlay.flash("Modelo não carregou. Veja o log e reinicie.", 2500, RED)
            return
        if self.state != IDLE:
            return
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro ao abrir o microfone")
            self.overlay.flash(f"Erro no microfone: {exc}", 3000, RED)
            return
        self.state = RECORDING
        self.overlay.show("Ouvindo…", RED, blink=True)

    def _on_hotkey_up(self) -> None:
        if self.state != RECORDING:
            return
        audio = self.recorder.stop()
        seconds = len(audio) / SAMPLE_RATE
        if seconds < self.config.min_audio_seconds:
            self.state = IDLE
            self.overlay.hide()
            return
        self.state = PROCESSING
        self.overlay.show("Transcrevendo…", WHITE)
        threading.Thread(
            target=self._process, args=(audio, seconds), name="transcribe", daemon=True
        ).start()

    # --- pipeline --------------------------------------------------------------

    def _process(self, audio: np.ndarray, seconds: float) -> None:
        try:
            prompt = ", ".join(self.config.dictionary) or None
            raw = self.transcriber.transcribe(audio, prompt=prompt)
            text = expand(clean(raw, self.config.fillers), self.config.snippets)
            self._ui(self._deliver, raw, text, seconds)
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro na transcrição")
            self._ui(self._fail, str(exc))

    def _deliver(self, raw: str, text: str, seconds: float) -> None:
        self.state = IDLE
        self.overlay.hide()
        if not text:
            self.overlay.flash("Não entendi nada.", 1500)
            return
        log.info("(%.1fs) %r -> %r", seconds, raw, text)
        folder = (self.config.obsidian_dir or "").strip()
        try:
            if folder:
                append_daily_note(folder, text)
                self.overlay.flash("Anotado.", 1200, GREEN)
            else:
                paste_text(text)
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro ao entregar o texto")
            where = "anotar no Obsidian" if folder else "colar"
            self.overlay.flash(f"Transcrevi, mas não consegui {where}: {exc}", 3000, RED)
        self.history.append(text, raw=raw, seconds=seconds)

    def _fail(self, message: str) -> None:
        self.state = IDLE
        self.overlay.flash(f"Erro: {message}", 3000, RED)

    # --- bandeja ----------------------------------------------------------------

    def toggle_enabled(self) -> None:
        self.enabled = not self.enabled
        if not self.enabled and self.state == RECORDING:
            self.recorder.stop()
            self.state = IDLE
        self.overlay.flash(
            f"{APP_NAME} {'ativado' if self.enabled else 'pausado'}",
            1500,
            GREEN if self.enabled else RED,
        )
        self.tray.refresh()

    def open_settings(self) -> None:
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        try:
            devices = list_input_devices()
        except Exception:  # noqa: BLE001
            devices = []
        self._settings_window = SettingsWindow(self.root, self.config, devices, self._apply_settings)

    def _apply_settings(self, config: Config, needs_restart: bool) -> None:
        self.recorder.device_name = config.input_device
        self.history.limit = config.history_limit
        try:
            self._start_hotkey()
        except ValueError as exc:
            self.overlay.flash(f"Atalho inválido: {exc}", 3000, RED)
            return
        if needs_restart:
            self.overlay.flash("Configurações salvas. Reinicie o Pluto para trocar o modelo.", 4000)
        else:
            self.overlay.flash("Configurações salvas.", 1500, GREEN)

    def open_history(self) -> None:
        if self._history_window and self._history_window.winfo_exists():
            self._history_window.lift()
            self._history_window.focus_force()
            return
        self._history_window = HistoryWindow(self.root, self.history)
