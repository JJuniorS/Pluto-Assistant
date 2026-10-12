"""Ícone na bandeja do sistema (pystray). Callbacks são despachados para a
thread do Tk pelo app, por isso aqui só chamamos funções simples."""

from __future__ import annotations

from collections.abc import Callable

import pystray

from pluto import APP_NAME
from pluto.icon import render_icon


def make_icon_image(size: int = 64, enabled: bool = True):
    return render_icon(size, enabled=enabled)


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
