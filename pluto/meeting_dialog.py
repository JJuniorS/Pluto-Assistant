"""Diálogo para nomear a reunião ao parar a gravação.

O root do Pluto fica oculto (withdrawn); o diálogo precisa forçar foco/topo
no Windows senão some atrás das outras janelas e o app parece travado.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from pluto import APP_NAME
from pluto.icon import apply_window_icon


def ask_meeting_name(master: tk.Misc) -> str | None:
    """Retorna o nome digitado, ou None se cancelar."""
    result: dict[str, str | None] = {"value": None}

    win = tk.Toplevel(master)
    win.title(f"{APP_NAME} — Nome da reunião")
    apply_window_icon(win)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.lift()

    body = ttk.Frame(win, padding=14)
    body.grid(sticky="nsew")
    ttk.Label(body, text="Nome da reunião").grid(row=0, column=0, sticky="w")
    default = f"Reunião {datetime.now().strftime('%H-%M')}"
    var = tk.StringVar(value=default)
    entry = ttk.Entry(body, textvariable=var, width=40)
    entry.grid(row=1, column=0, sticky="ew", pady=(6, 12))

    def ok() -> None:
        name = var.get().strip() or default
        result["value"] = name
        win.destroy()

    def cancel() -> None:
        result["value"] = None
        win.destroy()

    buttons = ttk.Frame(body)
    buttons.grid(row=2, column=0, sticky="e")
    ttk.Button(buttons, text="Cancelar", command=cancel).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Salvar", command=ok).pack(side="right")

    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: cancel())
    win.protocol("WM_DELETE_WINDOW", cancel)

    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")

    win.deiconify()
    win.focus_force()
    entry.focus_set()
    entry.select_range(0, "end")
    try:
        win.grab_set()
    except tk.TclError:
        pass

    master.wait_window(win)
    return result["value"]
