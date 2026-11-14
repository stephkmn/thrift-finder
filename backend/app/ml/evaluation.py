"""Scoring for the S1-11 evaluation set (S3-2; docs/EVALUATION.md → "What it measures").

scripts/evaluate.py runs the model and the searches; this module only scores them, so the
metrics are unit-tested without torch.
"""

from __future__ import annotations

import csv
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.data.local_dataset import PROJECT_ROOT
from backend.app.ml.attributes import SCALAR_NAMES
from backend.app.ml.index import listing_labels
from backend.app.schemas import Attributes

EVAL_DIR = PROJECT_ROOT / "eval"

# Dataset garment types each category can be filed under. The dataset's "Jacket" is a catch-all:
# S1-11 labeling found coats, parkas, puffers, and blazers typed "Jacket".
CATEGORY_TYPES = {
    "blazer": frozenset({"blazer", "jacket"}),
    "vest": frozenset({"vest"}),
    "raincoat": frozenset({"rain jacket", "jacket"}),
    "windbreaker": frozenset({"rain jacket", "jacket"}),
    "puffer jacket": frozenset({"winter jacket", "jacket"}),
    "parka": frozenset({"winter jacket", "jacket"}),
    "trucker jacket": frozenset({"denim jacket", "jacket"}),
}
# Every other category (jacket, coat, bomber jacket, shacket, ...).
DEFAULT_TYPES = frozenset({"jacket", "winter jacket", "denim jacket"})

# Our colors the dataset doesn't label: it files navy under Blue, olive under Green, and so on, so
# a listing in that family counts as having the color.
COLOR_FAMILIES = {
    "navy": frozenset({"navy", "blue"}),
    "olive": frozenset({"olive", "green"}),
    "cream": frozenset({"cream", "white", "tan"}),
    "burgundy": frozenset({"burgundy", "red"}),
}

# Edits whose effect the listing labels can show. Feature edits can't be scored: listings
# carry no `others` labels.
SCOREABLE_EDITS = ("color", "fabric", "fit")


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    source: str  # "dataset" or "own"
    image_path: Path
    labels: dict[str, Any]  # scalar name -> value or None; "others" -> set or None
    edit_attribute: str
    edit_from: str
    edit_to: str


@dataclass(frozen=True)
class ExtractionScore:
    correct: dict[str, bool]  # scalar name -> prediction matches the label (labeled ones only)
    true_pos: int
    false_pos: int
    false_neg: int


@dataclass(frozen=True)
class RankingScore:
    edit_satisfaction: float | None  # share of labeled results that have the edited value
    type_match: float  # share of the k slots holding a listing of the query's garment type
    precision: float | None  # automatic P@k: right type and has the edited value


def load_eval_set(
    queries_path: Path = EVAL_DIR / "queries.csv", labels_path: Path = EVAL_DIR / "labels.csv"
) -> list[EvalQuery]:
    """Join queries.csv and labels.csv on the photo's file name."""
    with labels_path.open(newline="", encoding="utf-8") as handle:
        labels = {Path(row["image"]).name: row for row in csv.DictReader(handle)}
    queries = []
    with queries_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            label = labels[Path(row["file"]).name]
            cell = (label.get("others") or "").strip()
            features = {f.strip() for f in cell.split(";") if f.strip()} - {"none"}
            queries.append(
                EvalQuery(
                    query_id=row["query_id"],
                    source=row["source"],
                    image_path=(labels_path.parent / label["image"]).resolve(),
                    labels={
                        **{name: (label.get(name) or "").strip() or None for name in SCALAR_NAMES},
                        "others": features if cell else None,
                    },
                    edit_attribute=row["edit_attribute"],
                    edit_from=row["edit_from"],
                    edit_to=row["edit_to"],
                )
            )
    return queries


def apply_edit(attributes: Attributes, query: EvalQuery) -> Attributes:
    """The edit a user would make on the extracted attributes, e.g. color -> brown."""
    if query.edit_attribute != "others":
        return attributes.model_copy(update={query.edit_attribute: query.edit_to})
    features = [f for f in attributes.others or [] if f != query.edit_from]
    if query.edit_to != "none" and query.edit_to not in features:
        features.append(query.edit_to)
    return attributes.model_copy(update={"others": features or None})


def type_matches(listing: dict[str, Any], category: str | None) -> bool:
    return listing_labels(listing).garment in CATEGORY_TYPES.get(category or "", DEFAULT_TYPES)


def edit_satisfied(listing: dict[str, Any], attribute: str, value: str) -> bool | None:
    """Whether the listing has the edited value; None when its labels can't tell."""
    labels = listing_labels(listing)
    if attribute == "color":
        family = COLOR_FAMILIES.get(value, frozenset({value}))
        return bool(family.intersection(labels.colors)) if labels.colors else None
    if attribute == "fabric":
        return labels.fabric == value if labels.fabric else None
    if attribute == "fit":
        return value in labels.fits if labels.fits else None
    return None


def score_extraction(predicted: Attributes, query: EvalQuery) -> ExtractionScore:
    correct = {
        name: getattr(predicted, name) == query.labels[name]
        for name in SCALAR_NAMES
        if query.labels[name] is not None
    }
    labeled = query.labels["others"]
    if labeled is None:
        return ExtractionScore(correct, 0, 0, 0)
    found = set(predicted.others or [])
    return ExtractionScore(
        correct, len(found & labeled), len(found - labeled), len(labeled - found)
    )


def score_ranking(listings: list[dict[str, Any]], query: EvalQuery, k: int = 10) -> RankingScore:
    """Score one system's top-k for a query; missing slots (fewer than k results) are misses."""
    top = listings[:k]
    types = [type_matches(listing, query.labels["category"]) for listing in top]
    if query.edit_attribute not in SCOREABLE_EDITS:
        return RankingScore(None, sum(types) / k, None)
    satisfied = [edit_satisfied(listing, query.edit_attribute, query.edit_to) for listing in top]
    known = [s for s in satisfied if s is not None]
    return RankingScore(
        edit_satisfaction=sum(known) / len(known) if known else None,
        type_match=sum(types) / k,
        precision=sum(t and s is True for t, s in zip(types, satisfied, strict=True)) / k,
    )


def mean(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.fmean(present) if present else None


def precision_recall_f1(scores: Iterable[ExtractionScore]) -> tuple[float | None, ...]:
    scores = list(scores)
    tp = sum(s.true_pos for s in scores)
    fp = sum(s.false_pos for s in scores)
    fn = sum(s.false_neg for s in scores)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return precision, recall, f1
