"""Resumo de reunião via OpenAI (padrão, mais barato) ou Anthropic."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5"

SUMMARY_SYSTEM = (
    "Você é um assistente que resume reuniões em português do Brasil. "
    "Com base na transcrição (falantes Eu = microfone do usuário, Outro = áudio do sistema), "
    "produza notas claras em Markdown com estas seções:\n"
    "## Resumo\n"
    "## Pontos combinados / decisões\n"
    "## Próximos passos\n"
    "## Tópicos discutidos\n"
    "Seja fiel ao que foi dito; se algo for incerto, indique. Não invente participantes."
)


def summarize_meeting(
    transcript: str,
    *,
    provider: str,
    api_key: str,
    model: str | None = None,
    meeting_name: str = "",
) -> str:
    """Devolve Markdown do resumo. Levanta RuntimeError se a API falhar."""
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("Chave da API de LLM não configurada.")

    user = transcript.strip()
    if not user:
        raise RuntimeError("Transcrição vazia.")

    title = meeting_name.strip()
    if title:
        user = f"Reunião: {title}\n\n{user}"

    prov = (provider or "openai").strip().lower()
    if prov == "anthropic":
        return _anthropic(key, model or ANTHROPIC_DEFAULT_MODEL, user)
    if prov == "openai":
        return _openai(key, model or OPENAI_DEFAULT_MODEL, user)
    raise RuntimeError(f"Provedor de LLM desconhecido: {provider!r}")


def _openai(api_key: str, model: str, user: str) -> str:
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    data = _post_json(
        "https://api.openai.com/v1/chat/completions",
        body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"Resposta inesperada da OpenAI: {data!r}") from exc


def _anthropic(api_key: str, model: str, user: str) -> str:
    body = {
        "model": model,
        "max_tokens": 4096,
        "system": SUMMARY_SYSTEM,
        "messages": [{"role": "user", "content": user}],
    }
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        parts = data["content"]
        texts = [p["text"] for p in parts if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(texts).strip()
    except (KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"Resposta inesperada da Anthropic: {data!r}") from exc


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        log.error("LLM HTTP %s: %s", exc.code, detail)
        raise RuntimeError(f"API LLM retornou {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha de rede na API LLM: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Resposta da API LLM não é JSON objeto.")
    return payload
