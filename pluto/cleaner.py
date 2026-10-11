"""Limpeza de texto transcrito (pt-BR) baseada em regras, sem LLM.

Pipeline: vícios de linguagem → "é" de hesitação → repetições → espaçamento/
pontuação → capitalização → pontuação final → passos extras (ponto de extensão
para, por exemplo, um LLM no futuro).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

DEFAULT_FILLERS: list[str] = [
    "éé",
    "ééé",
    "hum",
    "hmm",
    "hã",
    "ahn",
    "ahm",
    "né",
    "tipo assim",
]

# Pausa opcional que costuma acompanhar um vício: vírgula, reticências, ponto,
# ou "?"/"!" (ex.: "né?", que vira ponto final).
_PAUSE = r"\s*(\.\.\.|…|,|\.|\?|!)?\s*"


def clean(
    text: str,
    fillers: Iterable[str] | None = None,
    extra_steps: Iterable[Callable[[str], str]] = (),
) -> str:
    """Limpa um texto transcrito. Retorna "" se nada sobrar."""
    fillers = list(DEFAULT_FILLERS if fillers is None else fillers)
    t = text.strip()
    if not t:
        return ""

    for step in (
        lambda s: _remove_fillers(s, fillers),
        _remove_hesitation_e,
        _remove_repetitions,
        _fix_spacing,
        _capitalize_sentences,
        _ensure_terminal_punctuation,
    ):
        t = step(t)
        if not t.strip():
            return ""

    for step in extra_steps:
        t = step(t)
    return t.strip()


def _remove_fillers(text: str, fillers: list[str]) -> str:
    for filler in sorted((f.strip() for f in fillers if f.strip()), key=len, reverse=True):
        words = r"\s+".join(re.escape(w) for w in filler.split())
        pattern = re.compile(rf"(?<!\w){words}(?!\w){_PAUSE}", re.IGNORECASE)
        text = pattern.sub(lambda m: " . " if m.group(1) in ("?", "!") else " ", text)
    return text


def _remove_hesitation_e(text: str) -> str:
    # "é..." em qualquer posição é hesitação.
    text = re.sub(r"(?<!\w)é(?!\w)\s*(?:\.\.\.|…)\s*", " ", text, flags=re.IGNORECASE)
    # "É, ..." no início de uma frase é hesitação; "isso é bom" é verbo e fica.
    text = re.sub(r"(?:^|(?<=[.!?]\s))\s*é\s*,\s*", "", text.strip(), flags=re.IGNORECASE)
    return text


def _remove_repetitions(text: str) -> str:
    # Bigramas repetidos: "a gente a gente vai" -> "a gente vai"
    text = re.sub(r"(?<!\w)(\w+\s+\w+)(?:\s+\1(?!\w))+", r"\1", text, flags=re.IGNORECASE)
    # Palavras repetidas: "o o projeto" -> "o projeto"
    text = re.sub(r"(?<!\w)(\w+)(?:\s+\1(?!\w))+", r"\1", text, flags=re.IGNORECASE)
    return text


def _fix_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    # Sem espaço antes de pontuação.
    text = re.sub(r"\s+([,.;:!?…])", r"\1", text)
    # Pontuação "fraca" seguida de outra pontuação: ", ." -> "."; ",," -> ","
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"[,;:]+\s*(?=[,.;:!?…])", "", text)
    # Nada de pontuação solta no começo ou vírgula no fim.
    text = re.sub(r"^[\s,;:.!?…]+", "", text)
    text = re.sub(r"[\s,;:]+$", "", text)
    return text


def _capitalize_sentences(text: str) -> str:
    def upper_first(m: re.Match[str]) -> str:
        return m.group(1) + m.group(2).upper()

    text = re.sub(r"^(\s*)(\w)", upper_first, text)
    # Após . ! ? seguidos de espaço (mas não após reticências).
    return re.sub(r"((?<!\.)[.!?]\s+)(\w)", upper_first, text)


def _ensure_terminal_punctuation(text: str) -> str:
    if text and (text[-1].isalnum() or text[-1] in ")\"'”’"):
        return text + "."
    return text
