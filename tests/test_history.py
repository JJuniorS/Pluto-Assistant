from pluto.history import History


def test_append_and_read_latest_first(tmp_path):
    h = History(tmp_path / "h.jsonl", limit=10)
    h.append("primeiro", raw="primeiro bruto", seconds=1.2)
    h.append("segundo", raw="segundo bruto", seconds=0.8)
    items = h.read()
    assert [i["text"] for i in items] == ["segundo", "primeiro"]
    assert items[0]["raw"] == "segundo bruto"
    assert "timestamp" in items[0]


def test_limit_is_enforced(tmp_path):
    h = History(tmp_path / "h.jsonl", limit=3)
    for i in range(5):
        h.append(f"t{i}", raw="", seconds=0)
    assert [i["text"] for i in h.read()] == ["t4", "t3", "t2"]


def test_missing_file_reads_empty(tmp_path):
    assert History(tmp_path / "nope.jsonl", limit=5).read() == []


def test_clear(tmp_path):
    h = History(tmp_path / "h.jsonl", limit=5)
    h.append("x", raw="", seconds=0)
    h.clear()
    assert h.read() == []
