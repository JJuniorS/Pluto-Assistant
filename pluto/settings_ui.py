"""Janela de configurações (tkinter/ttk)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from pluto import APP_NAME
from pluto.config import Config
from pluto.icon import apply_window_icon
from pluto.hotkey import parse_hotkey
from pluto.transcriber import MODEL_SIZES

SYSTEM_DEFAULT = "(padrão do sistema)"


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
        ttk.Label(body, text="Atalho (segurar para falar)").grid(row=row, column=0, sticky="w")
        self.hotkey_var = tk.StringVar(value=config.hotkey)
        ttk.Entry(body, textvariable=self.hotkey_var, width=34).grid(row=row, column=1, sticky="ew")
        row += 1
        ttk.Label(
            body,
            text="Ex.: <ctrl>+<space>, <ctrl>+<alt>+d, <f9>",
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
            text="Nota do dia nesta pasta, uma fala por linha. Vazio cola no cursor.",
            foreground="#666",
        ).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(body, text="Processamento").grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.compute_var = tk.StringVar(value=config.device)
        ttk.Combobox(
            body, textvariable=self.compute_var, values=["auto", "cuda", "cpu"], state="readonly"
        ).grid(row=row, column=1, sticky="ew", pady=(10, 0))
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
        self.lift()
        self.focus_force()

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
        try:
            hotkey = str(parse_hotkey(hotkey))
        except ValueError as exc:
            messagebox.showerror(APP_NAME, f"Atalho inválido: {exc}", parent=self)
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
        device = self.device_var.get()
        cfg.input_device = None if device == SYSTEM_DEFAULT else device
        cfg.model_size = self.model_var.get()
        cfg.device = self.compute_var.get()
        cfg.obsidian_dir = self.obsidian_var.get().strip()
        cfg.fillers = self._lines(self.fillers_text)
        cfg.dictionary = self._lines(self.dictionary_text)
        cfg.snippets = snippets
        cfg.save()

        needs_restart = (
            cfg.model_size != self._before["model_size"] or cfg.device != self._before["device"]
        )
        self.on_save(cfg, needs_restart)
        self.destroy()
