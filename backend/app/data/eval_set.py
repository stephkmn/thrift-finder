"""Dataset half of the S1-11 evaluation set (docs/EVALUATION.md -> S1-11 evaluation set).

Draws the dataset query photos from the `test`-split pool that `scripts/ingest.py --split test`
saves to data/eval/dataset/ (never the `train` listings the search index uses, so a query can
never also be a search result). Nothing is downloaded here: the importer already did that and
dropped exact duplicate images. Everything works on plain records, so it is tested offline.

Re-running is safe: the draw is fixed by the seed, and rows already in eval/*.csv are kept
as they are, so labels and edits Member D has filled in are never overwritten.
"""

from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.data.local_dataset import DEFAULT_LISTINGS, PROJECT_ROOT
from backend.app.data.preprocess import clean_text, is_outerwear, parse_colors
from backend.app.ml.attributes import Vocabulary, load_vocabulary
from backend.app.ml.index import CUT_TO_FIT, _main_material

SEED = 451
COUNT = 30
SPLIT = "test"
# Where `scripts/ingest.py --split test` writes the evaluation pool (relative to the project root).
EVAL_POOL_DIR = Path("data/eval/dataset")
EVAL_LISTINGS = PROJECT_ROOT / EVAL_POOL_DIR / "listings.jsonl"

QUERY_FIELDS = [
    "query_id", "source", "split", "row_index", "file",
    "edit_attribute", "edit_from", "edit_to", "seed",
]  # fmt: skip
LABEL_FIELDS = ["image", "category", "color", "fabric", "fit", "others"]
# The dataset's own labels, kept for reference while labeling (not read by any script).
SOURCE_FIELDS = ["query_id", "row_index", "type", "colors", "material", "cut", "pattern"]


@dataclass
class EvalSetPaths:
    eval_dir: Path  # eval/: the committed CSVs

    @property
    def queries(self) -> Path:
        return self.eval_dir / "queries.csv"

    @property
    def labels(self) -> Path:
        return self.eval_dir / "labels.csv"

    @property
    def source(self) -> Path:
        return self.eval_dir / "dataset_source.csv"


@dataclass
class BuildResult:
    pool_sizes: dict[str, int]
    chosen: list[int]
    added: dict[str, int] = field(default_factory=dict)


def check_pool(listings_path: Path) -> None:
    """Refuse the search index's own listings: those photos are what queries are searched in."""
    if listings_path.resolve() == DEFAULT_LISTINGS.resolve():
        raise ValueError(
            f"{listings_path} holds the train-split search listings; draw queries from the "
            "test-split pool instead (python scripts/ingest.py --split test)."
        )


def stratified_quotas(sizes: dict[str, int], count: int) -> dict[str, int]:
    """Photos per type, proportional to each type's share of the pool (largest remainder)."""
    total = sum(sizes.values())
    if not 0 < count <= total:
        raise ValueError(f"Cannot draw {count} photos from a pool of {total}")
    exact = {name: count * size / total for name, size in sizes.items()}
    quotas = {name: int(share) for name, share in exact.items()}
    leftover = count - sum(quotas.values())
    # Largest remainder first; ties go to the bigger type, then alphabetically, so it's stable.
    order = sorted(exact, key=lambda name: (quotas[name] - exact[name], -sizes[name], name))
    for name in order[:leftover]:
        quotas[name] += 1
    return quotas


def draw(pool: dict[int, str], count: int = COUNT, seed: int = SEED) -> list[int]:
    """Row indices of `count` photos drawn at random from `pool` (row index -> type)."""
    by_type: dict[str, list[int]] = defaultdict(list)
    for row_index, garment_type in pool.items():
        by_type[garment_type].append(row_index)
    quotas = stratified_quotas({name: len(rows) for name, rows in by_type.items()}, count)
    rng = random.Random(seed)
    chosen: list[int] = []
    for name in sorted(by_type):
        chosen.extend(rng.sample(sorted(by_type[name]), quotas[name]))
    return sorted(chosen)


def _to_vocabulary(vocabulary: Vocabulary, name: str, word: str | None) -> str:
    """A vocabulary value for `word` (directly or via a synonym), or "" when there is none."""
    if not word:
        return ""
    word = word.strip().lower()
    spec = vocabulary.scalars[name]
    return word if word in spec.values else spec.synonyms.get(word, "")


def dataset_labels(
    attributes: dict[str, Any], vocabulary: Vocabulary | None = None
) -> dict[str, str]:
    """Pre-filled labels from a listing's dataset attributes, using the index's mappings.

    Anything ambiguous or outside our vocabulary is left blank for Member D to decide:
    several colors, a type with no matching category (e.g. "Winter Jacket"), an unknown
    material. `others` is always blank: the dataset has no feature labels.
    """
    vocabulary = vocabulary or load_vocabulary()
    colors = {
        _to_vocabulary(vocabulary, "color", c) for c in parse_colors(attributes.get("colors"))
    }
    colors.discard("")
    cuts = parse_colors(attributes.get("cut"))
    fits = {CUT_TO_FIT[c.lower()] for c in cuts if c.lower() in CUT_TO_FIT}
    return {
        "category": _to_vocabulary(vocabulary, "category", clean_text(attributes.get("type"))),
        "color": colors.pop() if len(colors) == 1 else "",
        "fabric": _to_vocabulary(vocabulary, "fabric", _main_material(attributes.get("material"))),
        "fit": fits.pop() if len(fits) == 1 else "",
        "others": "",
    }


def merge_rows(path: Path, fields: list[str], rows: list[dict[str, str]], key: str) -> int:
    """Append rows whose `key` isn't in the CSV yet. Existing bytes are never rewritten.

    Returns how many rows were added. Refuses a CSV whose header differs from `fields`.
    New rows use the file's own line endings (LF by default), so git diffs show only them.
    """
    existing_keys: set[str] = set()
    raw = path.read_bytes() if path.is_file() else b""
    if raw:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != fields:
                raise ValueError(f"{path} has columns {reader.fieldnames}, expected {fields}")
            existing_keys = {row[key] for row in reader}
    added = [row for row in rows if row[key] not in existing_keys]
    if not added:
        return 0
    newline = "\r\n" if b"\r\n" in raw else "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator=newline)
        if not raw:
            writer.writeheader()
        elif not raw.endswith(b"\n"):
            handle.write(newline)  # the last existing row has no line break yet
        writer.writerows(added)
    return len(added)


def _check_existing_draw(path: Path, rows: list[dict[str, str]]) -> None:
    """A dataset query_id already in queries.csv must still point at the same photo."""
    if not path.is_file():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        existing = {row["query_id"]: row for row in csv.DictReader(handle)}
    for row in rows:
        old = existing.get(row["query_id"])
        if old and (old["row_index"], old["split"]) != (row["row_index"], row["split"]):
            raise ValueError(
                f"{path}: {row['query_id']} is row {old['row_index']} ({old['split']}), but this "
                f"draw gives row {row['row_index']} ({row['split']}). Use the original seed and "
                "count, or remove the dataset rows first."
            )


def _relative_to_pool(image: Path) -> str:
    """queries.csv `file`: relative to data/eval/dataset/, like own photos to data/eval/own/."""
    try:
        return image.relative_to(EVAL_POOL_DIR).as_posix()
    except ValueError:
        return image.as_posix()


def _cell(value: Any) -> str:
    return "; ".join(map(str, value)) if isinstance(value, list) else str(value or "")


def build(
    listings: Iterable[dict[str, Any]],
    paths: EvalSetPaths,
    *,
    count: int = COUNT,
    seed: int = SEED,
    vocabulary: Vocabulary | None = None,
) -> BuildResult:
    """Draw the queries from the test-split pool's listing records and write eval/*.csv.

    `row_index` is each record's `source_index`: its row in the test split, which together
    with the seed identifies the photo for anyone rebuilding the set.
    """
    by_row: dict[int, dict[str, Any]] = {}
    for record in listings:
        attributes = record.get("attributes") or {}
        if is_outerwear(attributes.get("type")):
            by_row[int(record["source_index"])] = record
    pool = {row: clean_text(rec["attributes"]["type"]) or "" for row, rec in by_row.items()}
    chosen = draw(pool, count, seed)
    result = BuildResult(pool_sizes=dict(sorted(Counter(pool.values()).items())), chosen=chosen)

    vocabulary = vocabulary or load_vocabulary()
    queries, labels, sources = [], [], []
    for number, row_index in enumerate(chosen, start=1):
        record = by_row[row_index]
        attributes = record["attributes"]
        query_id = f"ds-{number:02d}"
        # Image paths in listings are relative to the project root, e.g.
        # data/eval/dataset/images/secondhand-000059.jpg.
        image = Path(record["image_path"])
        queries.append(
            {
                "query_id": query_id, "source": "dataset", "split": SPLIT,
                "row_index": str(row_index),
                "file": _relative_to_pool(image),
                "edit_attribute": "", "edit_from": "", "edit_to": "", "seed": str(seed),
            }
        )  # fmt: skip
        labels.append(
            {"image": (Path("..") / image).as_posix(), **dataset_labels(attributes, vocabulary)}
        )
        sources.append(
            {
                "query_id": query_id, "row_index": str(row_index),
                **{name: _cell(attributes.get(name)) for name in SOURCE_FIELDS[2:]},
            }
        )  # fmt: skip

    _check_existing_draw(paths.queries, queries)
    result.added = {
        "queries": merge_rows(paths.queries, QUERY_FIELDS, queries, "query_id"),
        "labels": merge_rows(paths.labels, LABEL_FIELDS, labels, "image"),
        "source": merge_rows(paths.source, SOURCE_FIELDS, sources, "query_id"),
    }
    return result
