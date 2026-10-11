"""Janela de histórico das últimas transcrições."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pyperclip

from pluto import APP_NAME
from pluto.history import History


class HistoryWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk, history: History):
        super().__init__(master)
        self.title(f"{APP_NAME} — Histórico")
        self.geometry("640x420")
        self.history = history

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        columns = ("quando", "texto")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("quando", text="Quando")
        self.tree.heading("texto", text="Texto")
        self.tree.column("quando", width=130, stretch=False)
        self.tree.column("texto", width=460)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        buttons = ttk.Frame(self, padding=(10, 0, 10, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Copiar selecionado", command=self._copy).pack(side="left")
        ttk.Button(buttons, text="Limpar histórico", command=self._clear).pack(side="right")

        self._items: list[str] = []
        self._load()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.lift()
        self.focus_force()

    def _load(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._items = []
        for entry in self.history.read():
            when = entry.get("timestamp", "").replace("T", " ")[:16]
            text = entry.get("text", "")
            self._items.append(text)
            self.tree.insert("", "end", iid=str(len(self._items) - 1), values=(when, text))

    def _copy(self) -> None:
        selected = self.tree.selection()
        if selected:
            pyperclip.copy(self._items[int(selected[0])])

    def _clear(self) -> None:
        self.history.clear()
        self._load()
