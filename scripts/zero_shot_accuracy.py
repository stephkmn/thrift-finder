"""Per-attribute zero-shot accuracy, FashionCLIP vs. base CLIP (S1-5).

Scalars report accuracy. `others` reports precision, recall, and F1 over the features,
since most features are absent from most photos and plain accuracy would reward
predicting "none" everywhere.

Labels CSV columns: image,category,color,fabric,fit,others
  - image: path relative to the CSV file
  - scalar columns: a value from backend/app/ml/attributes.yaml, or blank if unknown
  - others: features separated by ';' (e.g. "hood;zipper"), "none", or blank if unknown

Usage:
    python scripts/zero_shot_accuracy.py eval/labels.csv
    python scripts/zero_shot_accuracy.py eval/labels.csv --out docs/s1_5_accuracy.md
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

from backend.app.config import get_settings
from backend.app.ml.attributes import SCALAR_NAMES, AttributeExtractor, load_vocabulary
from backend.app.ml.encoder import BASELINE_MODEL, PRIMARY_MODEL, get_encoder


def read_labels(path: Path) -> list[dict]:
    vocabulary = load_vocabulary()
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            for name in SCALAR_NAMES:
                value = (row.get(name) or "").strip()
                if value and value not in vocabulary.scalars[name].values:
                    raise SystemExit(f"{path}:{line}: {name}={value!r} is not in attributes.yaml")
                row[name] = value or None
            cell = (row.get("others") or "").strip()
            others = {f.strip() for f in cell.split(";") if f.strip()} - {"none"}
            unknown = others - set(vocabulary.features)
            if unknown:
                raise SystemExit(f"{path}:{line}: unknown others {sorted(unknown)}")
            row["others"] = others if cell else None
            row["image"] = path.parent / row["image"]
            rows.append(row)
    return rows


OTHERS_METRICS = ("others precision", "others recall", "others F1")


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_model(
    model_name: str, dtype: str, rows: list[dict]
) -> tuple[dict[str, tuple[float | None, int]], list[str], float]:
    """Returns {metric: (score, n)}, a list of misses, and the median extract time in ms."""
    extractor = AttributeExtractor(get_encoder(model_name, dtype))
    correct: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    true_pos = false_pos = false_neg = others_images = 0
    latencies = []
    mistakes = []
    for row in rows:
        with Image.open(row["image"]) as image:
            started = time.perf_counter()
            attributes = extractor.extract(image=image).attributes
            latencies.append((time.perf_counter() - started) * 1000)
        for name in SCALAR_NAMES:
            if row[name] is None:
                continue
            predicted = getattr(attributes, name)
            total[name] += 1
            correct[name] += predicted == row[name]
            if predicted != row[name]:
                mistakes.append(f"{row['image'].name}: {name} {row[name]} -> {predicted}")
        if row["others"] is None:
            continue
        others_images += 1
        predicted_others = set(attributes.others or [])
        true_pos += len(predicted_others & row["others"])
        false_pos += len(predicted_others - row["others"])
        false_neg += len(row["others"] - predicted_others)
        if predicted_others != row["others"]:
            missed = sorted(row["others"] - predicted_others)
            extra = sorted(predicted_others - row["others"])
            mistakes.append(f"{row['image'].name}: others missed={missed} extra={extra}")

    scores = {name: (correct[name] / total[name], total[name]) for name in total}
    precision = _ratio(true_pos, true_pos + false_pos)
    recall = _ratio(true_pos, true_pos + false_neg)
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    for metric, value in zip(OTHERS_METRICS, (precision, recall, f1), strict=True):
        scores[metric] = (value, others_images)
    return scores, mistakes, statistics.median(latencies)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("labels", type=Path)
    parser.add_argument("--models", nargs="+", default=[PRIMARY_MODEL, BASELINE_MODEL])
    parser.add_argument("--out", type=Path, help="also write the Markdown table here")
    args = parser.parse_args()

    dtype = get_settings().model_dtype
    rows = read_labels(args.labels)
    results = {}
    latency = {}
    for model_name in args.models:
        print(f"Scoring {model_name} on {len(rows)} images ({dtype})...")
        results[model_name], mistakes, latency[model_name] = score_model(model_name, dtype, rows)
        for mistake in mistakes:
            print(f"  miss  {mistake}")

    header = "| Attribute | n | " + " | ".join(m.split("/")[-1] for m in args.models) + " |"
    lines = [header, "|---|---|" + "---|" * len(args.models)]
    for name in [*SCALAR_NAMES, *OTHERS_METRICS]:
        first = results[args.models[0]].get(name)
        if first is None or first[1] == 0:
            continue
        cells = [
            "n/a" if results[m][name][0] is None else f"{results[m][name][0]:.0%}"
            for m in args.models
        ]
        lines.append(f"| {name} | {first[1]} | " + " | ".join(cells) + " |")
    cells = [f"{latency[m]:.0f} ms" for m in args.models]
    lines.append(
        f"| median extract time ({dtype}, CPU) | {len(rows)} | " + " | ".join(cells) + " |"
    )
    table = "\n".join(lines)
    print("\n" + table)
    if args.out:
        args.out.write_text(table + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
