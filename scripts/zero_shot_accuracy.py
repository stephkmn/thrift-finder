"""Per-attribute zero-shot accuracy, FashionCLIP vs. base CLIP (S1-5).

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


def score_model(model_name: str, dtype: str, rows: list[dict]) -> tuple[dict, list[str]]:
    extractor = AttributeExtractor(get_encoder(model_name, dtype))
    features = list(extractor.vocabulary.features)
    correct: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    mistakes = []
    for row in rows:
        with Image.open(row["image"]) as image:
            attributes = extractor.extract(image=image).attributes
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
        predicted_others = set(attributes.others or [])
        for feature in features:
            total["others"] += 1
            correct["others"] += (feature in predicted_others) == (feature in row["others"])
        if predicted_others != row["others"]:
            missed = sorted(row["others"] - predicted_others)
            extra = sorted(predicted_others - row["others"])
            mistakes.append(f"{row['image'].name}: others missed={missed} extra={extra}")
    accuracy = {name: (correct[name] / total[name], total[name]) for name in total}
    return accuracy, mistakes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("labels", type=Path)
    parser.add_argument("--models", nargs="+", default=[PRIMARY_MODEL, BASELINE_MODEL])
    parser.add_argument("--out", type=Path, help="also write the Markdown table here")
    args = parser.parse_args()

    dtype = get_settings().model_dtype
    rows = read_labels(args.labels)
    results = {}
    for model_name in args.models:
        print(f"Scoring {model_name} on {len(rows)} images ({dtype})...")
        results[model_name], mistakes = score_model(model_name, dtype, rows)
        for mistake in mistakes:
            print(f"  miss  {mistake}")

    header = "| Attribute | n | " + " | ".join(m.split("/")[-1] for m in args.models) + " |"
    lines = [header, "|---|---|" + "---|" * len(args.models)]
    for name in [*SCALAR_NAMES, "others"]:
        first = results[args.models[0]].get(name)
        if first is None:
            continue
        cells = [f"{results[m][name][0]:.0%}" for m in args.models]
        label = "others (per-feature yes/no)" if name == "others" else name
        lines.append(f"| {label} | {first[1]} | " + " | ".join(cells) + " |")
    table = "\n".join(lines)
    print("\n" + table)
    if args.out:
        args.out.write_text(table + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
