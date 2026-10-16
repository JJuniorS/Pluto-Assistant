import json

from pluto.config import Config, DEFAULTS


def test_defaults_when_file_missing(tmp_path):
    cfg = Config(tmp_path / "config.json")
    assert cfg.hotkey == DEFAULTS["hotkey"]
    assert cfg.meeting_hotkey == DEFAULTS["meeting_hotkey"]
    assert cfg.llm_provider == "openai"
    assert cfg.llm_model == "gpt-4o-mini"
    assert cfg.fillers == DEFAULTS["fillers"]
    assert cfg.fillers is not DEFAULTS["fillers"]  # deep copy


def test_partial_file_is_merged_with_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"hotkey": "<f9>"}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.hotkey == "<f9>"
    assert cfg.model_size == DEFAULTS["model_size"]


def test_save_and_reload(tmp_path):
    path = tmp_path / "sub" / "config.json"
    cfg = Config(path)
    cfg.dictionary = ["Pluto", "Silva"]
    cfg.snippets = {"meu site": "https://x.y"}
    cfg.save()
    again = Config(path)
    assert again.dictionary == ["Pluto", "Silva"]
    assert again.snippets == {"meu site": "https://x.y"}


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    cfg = Config(path)
    assert cfg.hotkey == DEFAULTS["hotkey"]


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"foo": 1}), encoding="utf-8")
    cfg = Config(path)
    assert not hasattr(cfg, "foo")
