"""Snippets de voz: uma frase falada vira um texto cadastrado."""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    text = re.sub(r"[\s.,!?…;:]+$", "", text.strip().lower())
    return re.sub(r"\s+", " ", text)


def expand(text: str, snippets: dict[str, str]) -> str:
    """Substitui frases cadastradas pelo texto correspondente.

    Se o texto inteiro for apenas o snippet (ignorando caixa e pontuação final),
    retorna só o valor, sem pontuação. Caso contrário, substitui ocorrências
    inteiras (sem casar dentro de outras palavras).
    """
    if not snippets:
        return text

    normalized = _normalize(text)
    for phrase, value in snippets.items():
        if normalized == _normalize(phrase):
            return value

    for phrase, value in sorted(snippets.items(), key=lambda kv: len(kv[0]), reverse=True):
        phrase = phrase.strip()
        if not phrase:
            continue
        words = r"\s+".join(re.escape(w) for w in phrase.split())
        pattern = re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE)
        text = pattern.sub(lambda _m, v=value: v, text)
    return text
