"""Janela de configurações (tkinter/ttk)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from pluto import APP_NAME
from pluto.config import Config
from pluto.hotkey import parse_hotkey
from pluto.icon import apply_window_icon
from pluto.llm import ANTHROPIC_DEFAULT_MODEL, OPENAI_DEFAULT_MODEL
from pluto.transcriber import MODEL_SIZES

SYSTEM_DEFAULT = "(padrão do sistema)"
LLM_PROVIDERS = ["openai", "anthropic"]


class SettingsWindow(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        config: Config,
        devices: list[str],
        on_save: Callable[[Config, bool], None],
    ):
        super().__init__(master)
        self.title(f"{APP_NAME} — Configurações")
        apply_window_icon(self)
        self.resizable(False, False)
        self.config_obj = config
        self.on_save = on_save
        self._before = config.to_dict()

        body = ttk.Frame(self, padding=14)
        body.grid(sticky="nsew")

        row = 0
        ttk.Label(body, text="Atalho ditado (segurar)").grid(row=row, column=0, sticky="w")
        self.hotkey_var = tk.StringVar(value=config.hotkey)
        ttk.Entry(body, textvariable=self.hotkey_var, width=34).grid(row=row, column=1, sticky="ew")
        row += 1
        ttk.Label(
            body,
            text="Ex.: <ctrl>+<space>, <ctrl>+<alt>+d, <f9>",
            foreground="#666",
        ).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(body, text="Atalho reunião (ligar/desligar)").grid(
            row=row, column=0, sticky="w", pady=(10, 0)
        )
        self.meeting_hotkey_var = tk.StringVar(value=config.meeting_hotkey)
        ttk.Entry(body, textvariable=self.meeting_hotkey_var, width=34).grid(
            row=row, column=1, sticky="ew", pady=(10, 0)
        )
        row += 1
        ttk.Label(
            body,
            text="Padrão: <ctrl>+<shift>+m — mic + o que você ouve",
            foreground="#666",
        ).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(body, text="Microfone").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.device_var = tk.StringVar(value=config.input_device or SYSTEM_DEFAULT)
        ttk.Combobox(
            body,
            textvariable=self.device_var,
            values=[SYSTEM_DEFAULT, *devices],
            state="readonly",
            width=32,
        ).grid(row=row, column=1, sticky="ew", pady=(10, 0))
        row += 1

        ttk.Label(body, text="Modelo Whisper").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.model_var = tk.StringVar(value=config.model_size)
        ttk.Combobox(body, textvariable=self.model_var, values=MODEL_SIZES, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=(10, 0)
        )
        row += 1

        ttk.Label(body, text="Pasta do Obsidian").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.obsidian_var = tk.StringVar(value=config.obsidian_dir)
        ttk.Entry(body, textvariable=self.obsidian_var, width=34).grid(
            row=row, column=1, sticky="ew", pady=(10, 0)
        )
        row += 1
        ttk.Label(
            body,
            text="Ditado → nota do dia. Reuniões → DD-MM-AAAA/meets/…",
            foreground="#666",
        ).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(body, text="Processamento").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.compute_var = tk.StringVar(value=config.device)
        ttk.Combobox(
            body, textvariable=self.compute_var, values=["auto", "cuda", "cpu"], state="readonly"
        ).grid(row=row, column=1, sticky="ew", pady=(10, 0))
        row += 1

        ttk.Label(body, text="LLM do resumo").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.llm_provider_var = tk.StringVar(value=config.llm_provider or "openai")
        ttk.Combobox(
            body,
            textvariable=self.llm_provider_var,
            values=LLM_PROVIDERS,
            state="readonly",
            width=32,
        ).grid(row=row, column=1, sticky="ew", pady=(10, 0))
        row += 1

        ttk.Label(body, text="Modelo LLM").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.llm_model_var = tk.StringVar(value=config.llm_model)
        ttk.Entry(body, textvariable=self.llm_model_var, width=34).grid(
            row=row, column=1, sticky="ew", pady=(10, 0)
        )
        row += 1
        ttk.Label(
            body,
            text=f"Barato: OpenAI {OPENAI_DEFAULT_MODEL} ou Anthropic {ANTHROPIC_DEFAULT_MODEL}",
            foreground="#666",
        ).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(body, text="Chave da API LLM").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.llm_key_var = tk.StringVar(value=config.llm_api_key)
        ttk.Entry(body, textvariable=self.llm_key_var, width=34, show="•").grid(
            row=row, column=1, sticky="ew", pady=(10, 0)
        )
        row += 1

        self.fillers_text = self._text_block(
            body, row, "Vícios de linguagem\n(um por linha)", "\n".join(config.fillers)
        )
        row += 1
        self.dictionary_text = self._text_block(
            body, row, "Dicionário pessoal\n(nomes/termos, um por linha)", "\n".join(config.dictionary)
        )
        row += 1
        self.snippets_text = self._text_block(
            body,
            row,
            "Snippets de voz\n(frase => texto, um por linha)",
            "\n".join(f"{k} => {v}" for k, v in config.snippets.items()),
        )
        row += 1

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Salvar", command=self._save).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.llm_provider_var.trace_add("write", self._on_provider_change)
        self.lift()
        self.focus_force()

    def _on_provider_change(self, *_args: object) -> None:
        provider = self.llm_provider_var.get()
        current = self.llm_model_var.get().strip()
        openai_ish = current.startswith("gpt-") or current == OPENAI_DEFAULT_MODEL
        anthropic_ish = current.startswith("claude-")
        if provider == "openai" and (not current or anthropic_ish):
            self.llm_model_var.set(OPENAI_DEFAULT_MODEL)
        elif provider == "anthropic" and (not current or openai_ish):
            self.llm_model_var.set(ANTHROPIC_DEFAULT_MODEL)

    @staticmethod
    def _text_block(parent: ttk.Frame, row: int, label: str, value: str) -> tk.Text:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", pady=(10, 0))
        text = tk.Text(parent, width=40, height=4, font=("Segoe UI", 9))
        text.insert("1.0", value)
        text.grid(row=row, column=1, sticky="ew", pady=(10, 0))
        return text

    @staticmethod
    def _lines(widget: tk.Text) -> list[str]:
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]

    def _save(self) -> None:
        hotkey = self.hotkey_var.get().strip()
        meeting_hotkey = self.meeting_hotkey_var.get().strip()
        try:
            hotkey = str(parse_hotkey(hotkey))
            meeting_hotkey = str(parse_hotkey(meeting_hotkey))
        except ValueError as exc:
            messagebox.showerror(APP_NAME, f"Atalho inválido: {exc}", parent=self)
            return
        if hotkey == meeting_hotkey:
            messagebox.showerror(
                APP_NAME, "O atalho de ditado e o de reunião precisam ser diferentes.", parent=self
            )
            return

        snippets: dict[str, str] = {}
        for line in self._lines(self.snippets_text):
            if "=>" not in line:
                messagebox.showerror(
                    APP_NAME, f"Snippet sem '=>': {line!r}\nUse: frase => texto", parent=self
                )
                return
            phrase, value = (part.strip() for part in line.split("=>", 1))
            if phrase and value:
                snippets[phrase.lower()] = value

        cfg = self.config_obj
        cfg.hotkey = hotkey
        cfg.meeting_hotkey = meeting_hotkey
        device = self.device_var.get()
        cfg.input_device = None if device == SYSTEM_DEFAULT else device
        cfg.model_size = self.model_var.get()
        cfg.device = self.compute_var.get()
        cfg.obsidian_dir = self.obsidian_var.get().strip()
        cfg.llm_provider = self.llm_provider_var.get()
        cfg.llm_model = self.llm_model_var.get().strip() or (
            OPENAI_DEFAULT_MODEL if cfg.llm_provider == "openai" else ANTHROPIC_DEFAULT_MODEL
        )
        cfg.llm_api_key = self.llm_key_var.get().strip()
        cfg.fillers = self._lines(self.fillers_text)
        cfg.dictionary = self._lines(self.dictionary_text)
        cfg.snippets = snippets
        cfg.save()

        needs_restart = (
            cfg.model_size != self._before["model_size"] or cfg.device != self._before["device"]
        )
        self.on_save(cfg, needs_restart)
        self.destroy()
