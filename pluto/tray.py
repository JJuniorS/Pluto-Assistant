"""Ícone na bandeja do sistema (pystray). Callbacks são despachados para a
thread do Tk pelo app, por isso aqui só chamamos funções simples."""

from __future__ import annotations

from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw

from pluto import APP_NAME


def make_icon_image(size: int = 64, enabled: bool = True) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (139, 108, 255, 255) if enabled else (120, 120, 130, 255)
    d.ellipse((2, 2, size - 2, size - 2), fill=color)
    # Microfone estilizado em branco.
    cx = size // 2
    d.rounded_rectangle((cx - 8, 14, cx + 8, 36), radius=8, fill="white")
    d.arc((cx - 14, 20, cx + 14, 44), start=0, end=180, fill="white", width=4)
    d.line((cx, 44, cx, 52), fill="white", width=4)
    d.line((cx - 8, 52, cx + 8, 52), fill="white", width=4)
    return img


class Tray:
    def __init__(
        self,
        is_enabled: Callable[[], bool],
        on_toggle: Callable[[], None],
        on_settings: Callable[[], None],
        on_history: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._is_enabled = is_enabled
        menu = pystray.Menu(
            pystray.MenuItem(
                "Ativado", lambda: on_toggle(), checked=lambda _i: is_enabled(), default=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Configurações…", lambda: on_settings()),
            pystray.MenuItem("Histórico…", lambda: on_history()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda: on_quit()),
        )
        self.icon = pystray.Icon(APP_NAME, make_icon_image(), APP_NAME, menu)

    def start(self) -> None:
        self.icon.run_detached()

    def refresh(self) -> None:
        self.icon.icon = make_icon_image(enabled=self._is_enabled())
        self.icon.title = f"{APP_NAME} — {'ativado' if self._is_enabled() else 'pausado'}"
        self.icon.update_menu()

    def notify(self, message: str) -> None:
        try:
            self.icon.notify(message, APP_NAME)
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:  # noqa: BLE001
            pass
