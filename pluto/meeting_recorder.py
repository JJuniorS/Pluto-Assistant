"""Gravação de reunião: microfone (sounddevice) + áudio do sistema (SoundCard loopback)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np
import soundcard as sc
import sounddevice as sd

from pluto.recorder import SAMPLE_RATE, resolve_device

log = logging.getLogger(__name__)

_CHUNK = SAMPLE_RATE // 10


@dataclass
class DualAudio:
    mic: np.ndarray
    system: np.ndarray


class MeetingRecorder:
    """Captura microfone e loopback em paralelo até `stop()`.

    Os dois canais são alinhados no tempo: o que começa depois ganha silêncio
    no início, para os timestamps do Whisper baterem na mesma linha do tempo.
    """

    def __init__(self, mic_device_name: str | None = None):
        self.mic_device_name = mic_device_name
        self._mic_chunks: list[np.ndarray] = []
        self._sys_chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._mic_stream: sd.InputStream | None = None
        self._loop_thread: threading.Thread | None = None
        self._recording = False
        self._errors: list[str] = []
        self._t0: float = 0.0
        self._mic_first_at: float | None = None
        self._sys_first_at: float | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def last_errors(self) -> list[str]:
        return list(self._errors)

    def start(self) -> None:
        if self._recording:
            return
        with self._lock:
            self._mic_chunks = []
            self._sys_chunks = []
            self._errors = []
            self._mic_first_at = None
            self._sys_first_at = None
        self._stop.clear()
        self._t0 = time.monotonic()

        loopback = self._resolve_loopback()
        log.info(
            "Reunião: mic=%r | loopback=%s",
            self.mic_device_name or "(padrão)",
            loopback.name,
        )

        # Microfone via sounddevice (SoundCard quebra em vários mics USB a 16 kHz).
        try:
            self._mic_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                device=resolve_device(self.mic_device_name),
                callback=self._mic_callback,
            )
            self._mic_stream.start()
        except Exception as exc:  # noqa: BLE001
            log.exception("Falha ao abrir microfone")
            self._mic_stream = None
            self._errors.append(f"microfone: {exc}")

        self._loop_thread = threading.Thread(
            target=self._capture_loopback,
            args=(loopback,),
            name="meet-loopback",
            daemon=True,
        )
        self._loop_thread.start()
        self._recording = True

        if self._mic_stream is None:
            log.warning("Reunião sem microfone; só áudio do sistema.")

    def stop(self) -> DualAudio:
        if not self._recording:
            empty = np.zeros(0, dtype=np.float32)
            return DualAudio(empty, empty)

        self._stop.set()
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:  # noqa: BLE001
                log.exception("Erro ao fechar microfone da reunião")
            finally:
                self._mic_stream = None

        if self._loop_thread is not None:
            self._loop_thread.join(timeout=5.0)
            self._loop_thread = None

        self._recording = False
        with self._lock:
            mic = self._concat(self._mic_chunks)
            system = self._concat(self._sys_chunks)
            mic_first = self._mic_first_at
            sys_first = self._sys_first_at
            self._mic_chunks, self._sys_chunks = [], []

        mic = self._pad_leading(mic, mic_first)
        system = self._pad_leading(system, sys_first)
        if mic_first is not None and sys_first is not None:
            lag_ms = abs(mic_first - sys_first) * 1000
            log.info(
                "Alinhamento reunião: atraso mic=%.0fms sistema=%.0fms (relativo ao start)",
                (mic_first - self._t0) * 1000,
                (sys_first - self._t0) * 1000,
            )
            if lag_ms > 50:
                log.info("Diferença entre canais: %.0f ms (corrigida com silêncio inicial)", lag_ms)

        # Equaliza o fim com silêncio (não corta o canal mais longo).
        if len(mic) and len(system):
            n = max(len(mic), len(system))
            if len(mic) < n:
                mic = np.concatenate([mic, np.zeros(n - len(mic), dtype=np.float32)])
            if len(system) < n:
                system = np.concatenate([system, np.zeros(n - len(system), dtype=np.float32)])
        return DualAudio(mic, system)

    def _pad_leading(self, audio: np.ndarray, first_at: float | None) -> np.ndarray:
        if audio.size == 0 or first_at is None:
            return audio
        delay = max(0.0, first_at - self._t0)
        n = int(round(delay * SAMPLE_RATE))
        if n <= 0:
            return audio
        return np.concatenate([np.zeros(n, dtype=np.float32), audio])

    def _mic_callback(self, indata, _frames, _time, status) -> None:
        if status:
            log.debug("Status do mic (reunião): %s", status)
        now = time.monotonic()
        with self._lock:
            if self._mic_first_at is None:
                self._mic_first_at = now
            self._mic_chunks.append(indata[:, 0].copy())

    def _capture_loopback(self, device) -> None:
        try:
            channels = 2 if getattr(device, "channels", 2) != 1 else 1
            with device.recorder(samplerate=SAMPLE_RATE, channels=channels) as rec:
                while not self._stop.is_set():
                    try:
                        block = rec.record(numframes=_CHUNK)
                    except Exception:  # noqa: BLE001
                        if self._stop.is_set():
                            break
                        log.exception("Erro ao capturar loopback")
                        break
                    arr = np.asarray(block, dtype=np.float32)
                    if arr.ndim == 2:
                        mono = arr.mean(axis=1)
                    else:
                        mono = arr.reshape(-1)
                    now = time.monotonic()
                    with self._lock:
                        if self._sys_first_at is None:
                            self._sys_first_at = now
                        self._sys_chunks.append(mono.copy())
        except Exception as exc:  # noqa: BLE001
            log.exception("Falha ao abrir loopback %s", getattr(device, "name", device))
            with self._lock:
                self._errors.append(f"sistema: {exc}")

    @staticmethod
    def _resolve_loopback():
        speaker = sc.default_speaker()
        return sc.get_microphone(id=speaker.id, include_loopback=True)

    @staticmethod
    def _concat(chunks: list[np.ndarray]) -> np.ndarray:
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32, copy=False)


__all__ = ["DualAudio", "MeetingRecorder", "SAMPLE_RATE"]
