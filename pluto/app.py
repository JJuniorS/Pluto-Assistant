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
from pluto.hotkey import HotkeyListener, parse_hotkey
from pluto.icon import apply_window_icon, ensure_app_id
from pluto.inserter import paste_text
from pluto.llm import summarize_meeting
from pluto.meeting_dialog import ask_meeting_name
from pluto.meeting_notes import create_meeting_notes, format_transcript, merge_speaker_segments
from pluto.meeting_recorder import DualAudio, MeetingRecorder
from pluto.obsidian_note import append_daily_note
from pluto.overlay import GREEN, RED, WHITE, Overlay
from pluto.recorder import SAMPLE_RATE, Recorder, list_input_devices
from pluto.settings_ui import SettingsWindow
from pluto.snippets import expand
from pluto.transcriber import Transcriber
from pluto.tray import Tray

log = logging.getLogger(__name__)

LOADING, IDLE, RECORDING, MEETING, PROCESSING, ERROR = (
    "loading",
    "idle",
    "recording",
    "meeting",
    "processing",
    "error",
)


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
        self.meeting_recorder = MeetingRecorder(self.config.input_device)
        self.transcriber = Transcriber(self.config.model_size, self.config.device)

        self.tray = Tray(
            is_enabled=lambda: self.enabled,
            on_toggle=lambda: self._ui(self.toggle_enabled),
            on_settings=lambda: self._ui(self.open_settings),
            on_history=lambda: self._ui(self.open_history),
            on_quit=lambda: self._ui(self.quit),
        )
        self.hotkey: HotkeyListener | None = None
        self.meeting_hotkey: HotkeyListener | None = None
        self._settings_window: SettingsWindow | None = None
        self._history_window: HistoryWindow | None = None

    # --- ciclo de vida --------------------------------------------------------

    def run(self) -> None:
        self.tray.start()
        self._start_hotkeys()
        threading.Thread(target=self._load_model, name="model-loader", daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.mainloop()

    def quit(self) -> None:
        log.info("Encerrando.")
        if self.hotkey:
            self.hotkey.stop()
        if self.meeting_hotkey:
            self.meeting_hotkey.stop()
        if self.recorder.is_recording:
            self.recorder.stop()
        if self.meeting_recorder.is_recording:
            self.meeting_recorder.stop()
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
            f"{APP_NAME} pronto · {self.transcriber.model_in_use} na {where} · "
            f"ditado {self.config.hotkey} · reunião {self.config.meeting_hotkey}",
            4000,
            GREEN,
        )

    # --- atalhos ----------------------------------------------------------------

    def _start_hotkeys(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
        if self.meeting_hotkey:
            self.meeting_hotkey.stop()

        dictation = parse_hotkey(self.config.hotkey)
        self.hotkey = HotkeyListener(
            dictation,
            on_activate=lambda: self._ui(self._on_hotkey_down),
            on_deactivate=lambda: self._ui(self._on_hotkey_up),
        )
        self.hotkey.start()

        meeting = parse_hotkey(self.config.meeting_hotkey)
        self.meeting_hotkey = HotkeyListener(
            meeting,
            on_activate=lambda: self._ui(self._on_meeting_hotkey),
            on_deactivate=lambda: None,
        )
        self.meeting_hotkey.start()
        log.info("Atalhos: ditado=%s reunião=%s", dictation, meeting)

    def _on_hotkey_down(self) -> None:
        if not self.enabled:
            return
        if self.state == LOADING:
            self.overlay.flash("O modelo ainda está carregando…", 1500)
            return
        if self.state == ERROR:
            self.overlay.flash("Modelo não carregou. Veja o log e reinicie.", 2500, RED)
            return
        if self.state == MEETING:
            self.overlay.flash("Reunião em andamento — pare com o atalho de reunião.", 2000)
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

    def _on_meeting_hotkey(self) -> None:
        if not self.enabled:
            return
        if self.state == LOADING:
            self.overlay.flash("O modelo ainda está carregando…", 1500)
            return
        if self.state == ERROR:
            self.overlay.flash("Modelo não carregou. Veja o log e reinicie.", 2500, RED)
            return
        if self.state == MEETING:
            self._stop_meeting()
            return
        if self.state == PROCESSING:
            self.overlay.flash("Ainda processando a reunião…", 1500)
            return
        if self.state != IDLE:
            self.overlay.flash("Aguarde o ditado terminar.", 1500)
            return
        folder = (self.config.obsidian_dir or "").strip()
        if not folder:
            self.overlay.flash("Configure a pasta do Obsidian para gravar reuniões.", 3000, RED)
            return
        try:
            self.meeting_recorder.start()
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro ao iniciar gravação de reunião")
            self.overlay.flash(f"Erro ao gravar reunião: {exc}", 3000, RED)
            return
        self.state = MEETING
        self.overlay.show("Gravando reunião… (atalho de novo para parar)", RED, blink=True)

    def _stop_meeting(self) -> None:
        # Sai de MEETING antes do diálogo para o atalho não “parar” de novo
        # (o que descartava o áudio já capturado).
        self.state = PROCESSING
        self.overlay.show("Parando gravação…", WHITE)
        audio = self.meeting_recorder.stop()
        seconds = max(len(audio.mic), len(audio.system)) / SAMPLE_RATE
        errors = self.meeting_recorder.last_errors
        if seconds < 1.0:
            self.state = IDLE
            self.overlay.hide()
            detail = "; ".join(errors) if errors else "nenhum áudio capturado"
            self.overlay.flash(f"Falha na captura da reunião ({detail}).", 4000, RED)
            return

        self.overlay.hide()
        name = ask_meeting_name(self.root)
        if name is None:
            self.state = IDLE
            self.overlay.flash("Reunião descartada.", 1500)
            return

        self.overlay.show("Processando reunião…", WHITE)
        threading.Thread(
            target=self._process_meeting,
            args=(audio, name, seconds),
            name="meeting",
            daemon=True,
        ).start()

    # --- pipeline ditado -------------------------------------------------------

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

    # --- pipeline reunião ------------------------------------------------------

    def _process_meeting(self, audio: DualAudio, meeting_name: str, seconds: float) -> None:
        try:
            prompt = ", ".join(self.config.dictionary) or None
            self._ui(self.overlay.show, "Transcrevendo você…", WHITE)
            mine = self.transcriber.transcribe_segments(audio.mic, prompt=prompt)
            self._ui(self.overlay.show, "Transcrevendo o que você ouviu…", WHITE)
            theirs = self.transcriber.transcribe_segments(audio.system, prompt=prompt)

            utterances = merge_speaker_segments(
                [(s.start, s.end, s.text) for s in mine],
                [(s.start, s.end, s.text) for s in theirs],
            )
            transcript_md = format_transcript(utterances)
            if not utterances:
                self._ui(self._fail, "Nada foi transcrito na reunião.")
                return

            summary_md: str
            api_key = (self.config.llm_api_key or "").strip()
            if not api_key:
                summary_md = (
                    "_Resumo da IA não gerado — nenhuma chave de API configurada._\n\n"
                    "Quando quiser, coloque a chave OpenAI (gpt-4o-mini) ou Anthropic (Haiku) "
                    "em Configurações. A transcrição completa está em `Transcricao.md`."
                )
            else:
                try:
                    self._ui(self.overlay.show, "Gerando resumo com a IA…", WHITE)
                    summary_md = summarize_meeting(
                        transcript_md,
                        provider=self.config.llm_provider,
                        api_key=api_key,
                        model=self.config.llm_model or None,
                        meeting_name=meeting_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.exception("Falha no resumo LLM")
                    summary_md = (
                        "_Não foi possível gerar o resumo automaticamente._\n\n"
                        f"Motivo: {exc}\n\n"
                        "A transcrição completa está em `Transcricao.md`."
                    )

            paths = create_meeting_notes(
                self.config.obsidian_dir,
                meeting_name,
                transcript_md,
                summary_md,
            )
            log.info("Reunião salva (%.1fs) em %s", seconds, paths.folder)
            self._ui(self._meeting_done, str(paths.folder), seconds, transcript_md)
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro ao processar reunião")
            self._ui(self._fail, str(exc))

    def _meeting_done(self, folder: str, seconds: float, transcript: str) -> None:
        self.state = IDLE
        self.overlay.hide()
        self.overlay.flash("Reunião salva no Obsidian.", 2500, GREEN)
        self.history.append(f"[reunião] {folder}", raw=transcript[:500], seconds=seconds)

    def _fail(self, message: str) -> None:
        self.state = IDLE
        self.overlay.flash(f"Erro: {message}", 3000, RED)

    # --- bandeja ----------------------------------------------------------------

    def toggle_enabled(self) -> None:
        self.enabled = not self.enabled
        if not self.enabled and self.state == RECORDING:
            self.recorder.stop()
            self.state = IDLE
        if not self.enabled and self.state == MEETING:
            self.meeting_recorder.stop()
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
        self.meeting_recorder.mic_device_name = config.input_device
        self.history.limit = config.history_limit
        try:
            self._start_hotkeys()
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
