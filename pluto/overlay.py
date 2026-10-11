"""Pílula flutuante de status (tkinter). Nunca rouba o foco do app do usuário.

A silhueta é desenhada com Pillow e aplicada com transparência por pixel.
Um recorte Win32 (região) deixa a curva serrilhada e a borda opaca vira um
contorno claro; por isso a janela não usa região nem borda desenhada.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
import tkinter as tk
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageFont

BG = "#000000"
FG = "#ffffff"
WHITE = "#ffffff"
RED = "#e10600"
RED_DIM = "#2d0100"
GREEN = "#3ddc97"

DOT = 8
GAP = 8
PAD_X = 16
PAD_Y = 8
PULSE_MS = 1000
FRAME_MS = 50
SCALE = 4
FONT_SIZE = 14

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
ULW_ALPHA = 0x00000002
AC_SRC_ALPHA = 0x01

_FONT_PATH = r"C:\Windows\Fonts\segoeui.ttf"


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _win32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
        ctypes.POINTER(_POINT),
        ctypes.POINTER(_SIZE),
        wintypes.HDC,
        ctypes.POINTER(_POINT),
        wintypes.COLORREF,
        ctypes.POINTER(_BLENDFUNCTION),
        wintypes.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(_BITMAPINFOHEADER),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    return user32, gdi32


_USER32, _GDI32 = _win32() if sys.platform == "win32" else (None, None)


def _mix(start: str, end: str, t: float) -> str:
    def channel(hex_color: str, index: int) -> int:
        return int(hex_color[index : index + 2], 16)

    left = start.lstrip("#")
    right = end.lstrip("#")
    parts = []
    for index in (0, 2, 4):
        value = round(channel(left, index) + (channel(right, index) - channel(left, index)) * t)
        parts.append(f"{max(0, min(255, value)):02x}")
    return "#" + "".join(parts)


def _rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = hex_color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha)


def _premultiply(image: Image.Image) -> bytes:
    raw = bytearray(image.convert("RGBA").tobytes("raw", "BGRA"))
    for index in range(0, len(raw), 4):
        alpha = raw[index + 3]
        if alpha == 255:
            continue
        raw[index] = raw[index] * alpha // 255
        raw[index + 1] = raw[index + 1] * alpha // 255
        raw[index + 2] = raw[index + 2] * alpha // 255
    return bytes(raw)


def render_pill(text: str, dot: str) -> Image.Image:
    """Cápsula preta antisserrilhada, sem contorno. O fundo fica transparente."""
    font = ImageFont.truetype(_FONT_PATH, FONT_SIZE * SCALE)
    ascent, descent = font.getmetrics()
    text_w = math.ceil(font.getlength(text) / SCALE)
    text_h = math.ceil((ascent + descent) / SCALE)
    height = PAD_Y + max(text_h, DOT) + PAD_Y
    width = max(PAD_X + DOT + GAP + text_w + PAD_X, height)
    big_w, big_h = width * SCALE, height * SCALE

    image = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big_w - 1, big_h - 1), radius=big_h // 2, fill=(0, 0, 0, 255))

    cy = big_h / 2
    dot_size = DOT * SCALE
    cx = PAD_X * SCALE + dot_size / 2
    radius_dot = dot_size / 2
    draw.ellipse(
        (cx - radius_dot, cy - radius_dot, cx + radius_dot, cy + radius_dot),
        fill=_rgba(dot),
    )
    draw.text(
        (PAD_X * SCALE + dot_size + GAP * SCALE, cy),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        anchor="lm",
    )

    # BOX é a média de cada bloco. Lanczos cria halo e pontos soltos na curva.
    return image.resize((width, height), Image.Resampling.BOX)


class Overlay(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master, bg=BG)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._hide_job: str | None = None
        self._blink_job: str | None = None
        self._blinking = False
        self._blink_started = 0.0
        self._text = ""
        self._image: Image.Image | None = None

        self.withdraw()
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.update_idletasks()
        self._style()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self._blinking = False
        self._hide_job = None
        self._blink_job = None

    def _hwnd(self) -> int:
        child = self.winfo_id()
        parent = _USER32.GetParent(child)
        return parent or child

    def _style(self) -> None:
        if _USER32 is None:
            return
        hwnd = self._hwnd()
        if not hwnd:
            return
        style = _USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        _USER32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        )

    def _present(self, image: Image.Image) -> None:
        self._image = image
        width, height = image.size
        x = (self.winfo_screenwidth() - width) // 2
        y = self.winfo_screenheight() - height - 90
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self._style()
        if _USER32 is None:
            return

        data = _premultiply(image)
        header = _BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height
        header.biPlanes = 1
        header.biBitCount = 32

        screen_dc = _USER32.GetDC(0)
        mem_dc = _GDI32.CreateCompatibleDC(screen_dc)
        bits = ctypes.c_void_p()
        bitmap = _GDI32.CreateDIBSection(mem_dc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            _GDI32.DeleteDC(mem_dc)
            _USER32.ReleaseDC(0, screen_dc)
            return
        ctypes.memmove(bits, data, len(data))
        previous = _GDI32.SelectObject(mem_dc, bitmap)

        blend = _BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        origin = _POINT(x, y)
        size = _SIZE(width, height)
        source = _POINT(0, 0)
        _USER32.UpdateLayeredWindow(
            self._hwnd(),
            screen_dc,
            ctypes.byref(origin),
            ctypes.byref(size),
            mem_dc,
            ctypes.byref(source),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

        _GDI32.SelectObject(mem_dc, previous)
        _GDI32.DeleteObject(bitmap)
        _GDI32.DeleteDC(mem_dc)
        _USER32.ReleaseDC(0, screen_dc)

    def show(self, text: str, color: str = WHITE, blink: bool = False) -> None:
        self._cancel_hide()
        self._stop_blink()
        self._text = text
        self._present(render_pill(text, color))
        if blink:
            self._start_blink()

    def flash(self, text: str, ms: int = 2000, color: str = WHITE, blink: bool = False) -> None:
        self.show(text, color, blink)
        self._hide_job = self.after(ms, self.hide)

    def hide(self) -> None:
        self._cancel_hide()
        self._stop_blink()
        self.withdraw()

    def _cancel_hide(self) -> None:
        if self._hide_job is None:
            return
        try:
            self.after_cancel(self._hide_job)
        except tk.TclError:
            pass
        self._hide_job = None

    def _start_blink(self) -> None:
        self._blinking = True
        self._blink_started = time.monotonic()
        self._tick_blink()

    def _stop_blink(self) -> None:
        self._blinking = False
        if self._blink_job is None:
            return
        try:
            self.after_cancel(self._blink_job)
        except tk.TclError:
            pass
        self._blink_job = None

    def _tick_blink(self) -> None:
        if not self._blinking:
            return
        try:
            if not self.winfo_exists():
                self._blinking = False
                return
            elapsed = (time.monotonic() - self._blink_started) % (PULSE_MS / 1000)
            amount = (1 - math.cos(2 * math.pi * elapsed)) / 2
            self._present(render_pill(self._text, _mix(RED, RED_DIM, amount)))
            self._blink_job = self.after(FRAME_MS, self._tick_blink)
        except tk.TclError:
            self._blinking = False
            self._blink_job = None
