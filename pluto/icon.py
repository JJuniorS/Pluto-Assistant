"""Ícone do Pluto: círculo preto com o ponto vermelho da pílula.

Desenhado em resolução maior e reduzido com BOX, o mesmo critério da pílula,
para a curva ficar lisa em 16 px na bandeja e em 256 px no arquivo.

No Windows a barra de tarefas mostra o ícone do pythonw.exe até o processo
ter um AppUserModelID próprio e a janela receber o .ico via WM_SETICON.
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

BG = (0, 0, 0, 255)
RED = (0xE1, 0x06, 0x00, 255)
PAUSED = (0x6E, 0x6E, 0x6E, 255)
DOT_RATIO = 0.32
SCALE = 4
APP_ID = "Pluto.Assistant"

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010

_HANDLES: tuple[int, int] | None = None


def render_icon(size: int = 64, enabled: bool = True) -> Image.Image:
    canvas = size * SCALE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, canvas - 1, canvas - 1), fill=BG)
    dot = round(canvas * DOT_RATIO)
    left = (canvas - dot) // 2
    color = RED if enabled else PAUSED
    draw.ellipse((left, left, left + dot - 1, left + dot - 1), fill=color)
    return image.resize((size, size), Image.Resampling.BOX)


def ico_path() -> Path:
    return ASSETS / "pluto.ico"


def ensure_app_id() -> None:
    """Separa o Pluto do ícone do Python na barra de tarefas. Chamar antes do Tk."""
    if sys.platform != "win32":
        return
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.HRESULT
    shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def apply_window_icon(window: tk.Misc) -> None:
    """Aplica o .ico na barra de título e na barra de tarefas."""
    path = ico_path()
    if path.is_file():
        try:
            window.iconbitmap(default=str(path))
        except tk.TclError:
            pass
        try:
            window.iconbitmap(str(path))
        except tk.TclError:
            pass
    photo = ImageTk.PhotoImage(render_icon(64))
    window.iconphoto(False, photo)
    window._pluto_icon = photo  # type: ignore[attr-defined]
    _reapply_taskbar_icon(window)
    if not getattr(window, "_pluto_icon_bound", False):
        window.bind("<Map>", lambda _event: _reapply_taskbar_icon(window), add="+")
        window._pluto_icon_bound = True  # type: ignore[attr-defined]


def _reapply_taskbar_icon(window: tk.Misc) -> None:
    _apply_taskbar_icon(window)

    def later() -> None:
        try:
            _apply_taskbar_icon(window)
        except tk.TclError:
            return

    try:
        window.after(100, later)
    except tk.TclError:
        return


def _user32():
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    return user32


def _icon_handles() -> tuple[int, int] | None:
    global _HANDLES
    if _HANDLES is not None:
        return _HANDLES
    if sys.platform != "win32" or not ico_path().is_file():
        return None
    user32 = _user32()
    path = str(ico_path())
    small = user32.LoadImageW(None, path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE) or 0
    big = user32.LoadImageW(None, path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE) or 0
    if not small and not big:
        return None
    _HANDLES = (small, big)
    return _HANDLES


def _apply_taskbar_icon(window: tk.Misc) -> None:
    handles = _icon_handles()
    if not handles:
        return
    user32 = _user32()
    child = int(window.winfo_id())
    parent = int(user32.GetParent(child) or 0)
    small, big = handles
    for hwnd in {child, parent} - {0}:
        if small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
        if big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
