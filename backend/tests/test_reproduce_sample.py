"""scripts/reproduce_sample.py: the pass/fail rule and the committed expected output (no model)."""

import importlib.util
import json
from pathlib import Path

from backend.app.ml import evaluation as ev

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "reproduce_sample", ROOT / "scripts" / "reproduce_sample.py"
)
reproduce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reproduce)

EXPECTED = {
    "attributes": {
        "category": "shacket",
        "color": "red",
        "fabric": "cotton",
        "fit": "regular fit",
        "others": ["belt", "buttons"],
    },
    "top_titles": ["Green Jacket"] * 8 + ["Green Blazer"] * 2,
}


def _actual(**changes):
    attributes = {**EXPECTED["attributes"], **changes.pop("attributes", {})}
    return {
        "attributes": attributes,
        "top_titles": changes.get("top_titles", EXPECTED["top_titles"]),
    }


def test_identical_result_passes():
    assert reproduce.compare(EXPECTED, _actual()) == []


def test_feature_order_does_not_matter():
    assert reproduce.compare(EXPECTED, _actual(attributes={"others": ["buttons", "belt"]})) == []


def test_different_attribute_fails():
    problems = reproduce.compare(EXPECTED, _actual(attributes={"color": "orange"}))
    assert problems == ["color: expected 'red', got 'orange'"]


def test_two_swapped_titles_still_pass():
    titles = ["Green Jacket"] * 8 + ["Red Jacket"] * 2
    assert reproduce.compare(EXPECTED, _actual(top_titles=titles)) == []


def test_three_different_titles_fail():
    titles = ["Green Jacket"] * 7 + ["Red Jacket"] * 3
    problems = reproduce.compare(EXPECTED, _actual(top_titles=titles))
    assert problems == ["only 7 of 10 result titles match (need 8)"]


def test_committed_expected_output_matches_the_samples_and_scripted_edits():
    expected = json.loads(reproduce.EXPECTED_PATH.read_text(encoding="utf-8"))
    queries = {q.image_path.name: q for q in ev.load_eval_set()}
    assert expected["samples"]
    for sample in expected["samples"]:
        image = ROOT / sample["image"]
        assert image.is_file(), sample["image"]
        query = queries[image.name]
        assert sample["edit"] == {
            "attribute": query.edit_attribute,
            "from": query.edit_from,
            "to": query.edit_to,
        }
        assert set(sample["attributes"]) == {*reproduce.SCALARS, "others"}
        assert len(sample["top_titles"]) == reproduce.TOP_K
