import json
from unittest.mock import patch

import pytest

from pluto.llm import summarize_meeting


def test_summarize_requires_api_key():
    with pytest.raises(RuntimeError, match="Chave"):
        summarize_meeting("oi", provider="openai", api_key="")


def test_openai_summary_parses_response():
    payload = {
        "choices": [{"message": {"content": "## Resumo\n\nFeito."}}],
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    with patch("pluto.llm.urllib.request.urlopen", return_value=_Resp()):
        text = summarize_meeting(
            "**[00:01] Eu:** oi",
            provider="openai",
            api_key="sk-test",
            meeting_name="Daily",
        )
    assert "Feito" in text


def test_anthropic_summary_parses_response():
    payload = {"content": [{"type": "text", "text": "## Resumo\n\nHaiku."}]}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    with patch("pluto.llm.urllib.request.urlopen", return_value=_Resp()):
        text = summarize_meeting(
            "fala",
            provider="anthropic",
            api_key="ant-test",
            model="claude-haiku-4-5",
        )
    assert "Haiku" in text
