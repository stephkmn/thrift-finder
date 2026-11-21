"""Reproduce a sample result: run the committed sample photos through extract + search.

Each photo in samples/ goes through the same code as the app: zero-shot attribute extraction
(POST /api/extract), then the photo's scripted edit from eval/queries.csv (e.g. color red -> green)
and edit-aware search over the local index (POST /api/search). The output is compared with
samples/expected_output.json, recorded with scripts/evaluate.py (FashionCLIP, float64 on a
laptop CPU).

Pass criteria per photo: the extracted category, color, fabric, fit and features match exactly,
and at least MIN_TITLE_OVERLAP of the 10 result titles match (as a multiset). The titles allow
some slack because float32 and float64 can swap listings whose scores are nearly tied.

Needs the `ml` extra and the local index (data/listings.jsonl + data/embeddings.npz; see README).

Usage:
    python scripts/reproduce_sample.py                         # all samples in expected_output.json
    python scripts/reproduce_sample.py samples/shacket1-hung.JPG
    python scripts/reproduce_sample.py --write                 # re-record the expected output
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PATH = PROJECT_ROOT / "samples" / "expected_output.json"
SCALARS = ("category", "color", "fabric", "fit")
MIN_TITLE_OVERLAP = 8
TOP_K = 10


def attribute_dict(attributes: Any) -> dict[str, Any]:
    """Attributes as JSON-friendly values; features sorted so their order doesn't matter."""
    values = {name: getattr(attributes, name) for name in SCALARS}
    values["others"] = sorted(attributes.others or [])
    return values


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Differences between one sample's expected and actual result; empty when it passes."""
    problems = []
    for name in (*SCALARS, "others"):
        want, got = expected["attributes"][name], actual["attributes"][name]
        if name == "others":
            want, got = sorted(want), sorted(got)
        if want != got:
            problems.append(f"{name}: expected {want!r}, got {got!r}")
    overlap = sum((Counter(expected["top_titles"]) & Counter(actual["top_titles"])).values())
    if overlap < MIN_TITLE_OVERLAP:
        problems.append(
            f"only {overlap} of {len(expected['top_titles'])} result titles match "
            f"(need {MIN_TITLE_OVERLAP})"
        )
    return problems


def run_sample(image_path: Path, extractor: Any, queries: dict[str, Any]) -> dict[str, Any]:
    """Extract, apply the photo's scripted edit, and search, as the app would."""
    from PIL import Image

    from backend.app.ml import evaluation as ev
    from backend.app.ml.rerank import search_listings

    query = queries.get(image_path.name)
    if query is None:
        raise SystemExit(f"{image_path.name} has no scripted edit in eval/queries.csv")
    with Image.open(image_path) as image:
        extraction = extractor.extract(image=image)
    edited = ev.apply_edit(extraction.attributes, query)
    matches = search_listings(extraction.embedding, "image", extraction.attributes, edited, TOP_K)
    return {
        "image": image_path.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "edit": {"attribute": query.edit_attribute, "from": query.edit_from, "to": query.edit_to},
        "attributes": attribute_dict(extraction.attributes),
        "top_titles": [m.listing["title"] for m in matches],
        "top_ids": [m.listing["id"] for m in matches],
        "match_scores": [m.match_score for m in matches],
    }


def print_result(result: dict[str, Any]) -> None:
    edit = result["edit"]
    attrs = result["attributes"]
    print(f"\n{result['image']}")
    print(
        f"  extracted: {attrs['color']} {attrs['fabric']} {attrs['fit']} {attrs['category']}, "
        f"features {attrs['others'] or 'none'}"
    )
    print(f"  edit:      {edit['attribute']} {edit['from']} -> {edit['to']}")
    pairs = zip(result["top_titles"], result["match_scores"], strict=True)
    for rank, (title, score) in enumerate(pairs, start=1):
        print(f"  {rank:2}. {title:<24} match {score:5.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("images", nargs="*", type=Path, help="sample photos (default: all)")
    parser.add_argument("--expected", type=Path, default=EXPECTED_PATH)
    parser.add_argument("--write", action="store_true", help="save this run as the expected output")
    args = parser.parse_args()

    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    by_image = {sample["image"]: sample for sample in expected["samples"]}
    images = args.images or [PROJECT_ROOT / name for name in by_image]

    from backend.app.ml import evaluation as ev
    from backend.app.ml.attributes import get_extractor

    try:
        extractor = get_extractor()
    except (ImportError, OSError, RuntimeError) as exc:
        print(f"Could not load the model ({exc}). Install the ml extra: pip install -e '.[dev,ml]'")
        return 2
    queries = {q.image_path.name: q for q in ev.load_eval_set()}

    results, failures = [], 0
    for image in images:
        try:
            result = run_sample(image, extractor, queries)
        except (FileNotFoundError, ValueError) as exc:  # local index missing or stale
            print(f"{exc}\nBuild the local index first: see 'Reproduce a sample' in README.md.")
            return 2
        results.append(result)
        print_result(result)
        if args.write:
            continue
        sample = by_image.get(result["image"])
        if sample is None:
            print("  no expected output for this photo; run with --write to record one")
            failures += 1
            continue
        problems = compare(sample, result)
        print("  PASS" if not problems else "  FAIL: " + "; ".join(problems))
        failures += bool(problems)

    if args.write:
        from backend.app.config import get_settings

        settings = get_settings()
        expected["note"] = (
            f"Recorded with scripts/reproduce_sample.py ({settings.model_name}, "
            f"{settings.model_dtype}, local index). Re-record with --write."
        )
        expected["samples"] = results
        args.expected.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {len(results)} samples to {args.expected}")
        return 0
    print(f"\n{len(results) - failures} of {len(results)} samples match the expected output.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
