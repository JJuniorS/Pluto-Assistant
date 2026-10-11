"""Pílula flutuante de status (tkinter). Nunca rouba o foco do app do usuário."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk

BG = "#1b1830"
FG = "#f4f1ff"
ACCENT = "#8b6cff"
RED = "#ff4d6d"
GREEN = "#3ddc97"

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class Overlay(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master, bg=BG)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.94)
        self._hide_job: str | None = None

        frame = tk.Frame(self, bg=BG, padx=18, pady=9)
        frame.pack()
        self._dot = tk.Label(frame, text="●", bg=BG, fg=ACCENT, font=("Segoe UI", 12))
        self._dot.pack(side="left", padx=(0, 8))
        self._label = tk.Label(frame, text="", bg=BG, fg=FG, font=("Segoe UI", 11))
        self._label.pack(side="left")

        self.withdraw()
        self.update_idletasks()
        self._no_activate()

    def _no_activate(self) -> None:
        if sys.platform != "win32":
            return
        user32 = ctypes.windll.user32
        for hwnd in {self.winfo_id(), user32.GetParent(self.winfo_id())}:
            if not hwnd:
                continue
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

    def _place(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = self.winfo_screenheight() - h - 90
        self.geometry(f"{w}x{h}+{x}+{y}")

    def show(self, text: str, color: str = ACCENT) -> None:
        self._cancel_hide()
        self._label.config(text=text)
        self._dot.config(fg=color)
        self._place()
        self.deiconify()
        self.lift()

    def flash(self, text: str, ms: int = 2000, color: str = ACCENT) -> None:
        self.show(text, color)
        self._hide_job = self.after(ms, self.hide)

    def hide(self) -> None:
        self._cancel_hide()
        self.withdraw()

    def _cancel_hide(self) -> None:
        if self._hide_job is not None:
            self.after_cancel(self._hide_job)
            self._hide_job = None
