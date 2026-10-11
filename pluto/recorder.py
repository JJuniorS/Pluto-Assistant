"""Captura do microfone em 16 kHz mono float32 (formato que o Whisper espera)."""

from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


def list_input_devices() -> list[str]:
    """Nomes dos dispositivos de entrada, sem duplicatas, na ordem do sistema."""
    names: list[str] = []
    for dev in sd.query_devices():
        if dev["max_input_channels"] > 0 and dev["name"] not in names:
            names.append(dev["name"])
    return names


def resolve_device(name: str | None) -> int | None:
    """Converte nome em índice. None (ou nome não encontrado) = padrão do sistema."""
    if not name:
        return None
    for index, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and dev["name"] == name:
            return index
    log.warning("Microfone %r não encontrado; usando o padrão do sistema.", name)
    return None


class Recorder:
    def __init__(self, device_name: str | None = None):
        self.device_name = device_name
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def _callback(self, indata, _frames, _time, status) -> None:
        if status:
            log.debug("Status do áudio: %s", status)
        with self._lock:
            self._chunks.append(indata[:, 0].copy())

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=resolve_device(self.device_name),
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
        with self._lock:
            chunks, self._chunks = self._chunks, []
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    @property
    def is_recording(self) -> bool:
        return self._stream is not None
