"""Ensure evaluation ingestion stays isolated from search listings (offline)."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from PIL import Image

from scripts import ingest as ingest_module


def test_test_split_does_not_overwrite_train(monkeypatch, tmp_path):
    """The test split goes to data/eval/dataset, leaving the search index intact."""
    selected_splits = []

    def fake_load_dataset(_dataset_id, *, split, streaming, revision):
        selected_splits.append(split)
        assert streaming is True
        assert revision == "main"
        return [{"type": "Jacket", "colors": "['Blue']", "image": Image.new("RGB", (8, 8))}]

    monkeypatch.setitem(sys.modules, "datasets", SimpleNamespace(load_dataset=fake_load_dataset))
    monkeypatch.setattr(ingest_module, "PROJECT_ROOT", tmp_path)
    train_output = tmp_path / "data" / "listings.jsonl"
    train_output.parent.mkdir(parents=True)
    train_output.write_text("TRAIN RECORDS STAY HERE\n")

    test_dir = tmp_path / "data" / "eval" / "dataset"
    stats = ingest_module.ingest(
        limit=3,
        max_scan=10,
        output=test_dir / "listings.jsonl",
        image_dir=test_dir / "images",
        revision="main",
        split="test",
    )
    assert selected_splits == ["test"]
    assert stats["saved"] == 1
    assert train_output.read_text() == "TRAIN RECORDS STAY HERE\n"
    record = json.loads((test_dir / "listings.jsonl").read_text())
    assert record["image_path"].startswith("data/eval/dataset/images/")
    assert (tmp_path / record["image_path"]).is_file()


def test_cli_routes_splits_to_separate_directories(monkeypatch, tmp_path):
    """The CLI keeps existing training path and uses a separate test path."""
    calls = []
    monkeypatch.setattr(ingest_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ingest_module, "ingest", lambda **kw: calls.append(kw))

    monkeypatch.setattr(sys, "argv", ["ingest.py", "--limit", "5"])
    ingest_module.main()
    assert calls[-1]["split"] == "train"
    assert calls[-1]["output"] == tmp_path / "data" / "listings.jsonl"
    assert calls[-1]["image_dir"] == tmp_path / "data" / "images"

    monkeypatch.setattr(sys, "argv", ["ingest.py", "--split", "test", "--limit", "5"])
    ingest_module.main()
    assert calls[-1]["split"] == "test"
    assert calls[-1]["output"] == tmp_path / "data" / "eval" / "dataset" / "listings.jsonl"
    assert calls[-1]["image_dir"] == tmp_path / "data" / "eval" / "dataset" / "images"
