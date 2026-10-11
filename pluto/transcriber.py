"""Transcrição local com faster-whisper. GPU (CUDA) com fallback para CPU."""

from __future__ import annotations

import logging
import os
import site
import sys
import sysconfig
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
GPU_DEFAULT_MODEL = "large-v3-turbo"
CPU_DEFAULT_MODEL = "small"
MODEL_SIZES = ["auto", "tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]


def _register_cuda_dlls() -> None:
    """Expõe as DLLs de cuBLAS/cuDNN instaladas via pip para o ctranslate2."""
    if sys.platform != "win32":
        return
    roots = {sysconfig.get_paths()["purelib"], *site.getsitepackages()}
    for root in roots:
        for sub in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            bin_dir = Path(root) / "nvidia" / sub / "bin"
            if bin_dir.is_dir():
                try:
                    os.add_dll_directory(str(bin_dir))
                except OSError:
                    pass
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


_register_cuda_dlls()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class Transcriber:
    def __init__(self, model_size: str = "auto", device: str = "auto"):
        self.requested_model = model_size
        self.requested_device = device
        self.model = None
        self.device_in_use: str | None = None
        self.model_in_use: str | None = None

    # --- carregamento --------------------------------------------------------

    def _candidates(self) -> list[tuple[str, str, str]]:
        """(device, compute_type, model) em ordem de preferência."""
        want_gpu = self.requested_device in ("auto", "cuda")
        want_cpu = self.requested_device in ("auto", "cpu")
        out: list[tuple[str, str, str]] = []
        if want_gpu and self._cuda_available():
            model = GPU_DEFAULT_MODEL if self.requested_model == "auto" else self.requested_model
            out.append(("cuda", "float16", model))
        if want_cpu or not out:
            model = CPU_DEFAULT_MODEL if self.requested_model == "auto" else self.requested_model
            out.append(("cpu", "int8", model))
        return out

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import ctranslate2

            return ctranslate2.get_cuda_device_count() > 0
        except Exception:  # noqa: BLE001
            return False

    def load(self) -> None:
        from faster_whisper import WhisperModel

        errors: list[str] = []
        for device, compute_type, model_name in self._candidates():
            try:
                log.info("Carregando modelo %s em %s (%s)…", model_name, device, compute_type)
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                # Aquecimento: garante que as DLLs de CUDA funcionam de verdade.
                list(model.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language="pt")[0])
                self.model, self.device_in_use, self.model_in_use = model, device, model_name
                log.info("Modelo pronto: %s em %s", model_name, device)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("Falha ao carregar %s em %s: %s", model_name, device, exc)
                errors.append(f"{device}/{model_name}: {exc}")
        raise RuntimeError("Não foi possível carregar o modelo. " + " | ".join(errors))

    # --- uso -------------------------------------------------------------------

    def transcribe(self, audio: np.ndarray, prompt: str | None = None) -> str:
        if self.model is None:
            raise RuntimeError("Modelo ainda não carregado.")
        segments, _info = self.model.transcribe(
            audio,
            language="pt",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            initial_prompt=prompt or None,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
