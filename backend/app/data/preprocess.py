"""Normalize labeled secondhand garment data for the local search fallback.

The source dataset is not a live marketplace. We intentionally do not invent
prices, purchase links, or ML confidence scores.
"""

from __future__ import annotations

import ast
import re
from typing import Any

DATASET_ID = "fnauman/fashion-second-hand-front-only-rgb"

# Keep Sprint 2 scoped to outerwear, not every garment in the source dataset.
OUTERWEAR_WORDS = frozenset(
    {"jacket", "coat", "blazer", "parka", "windbreaker", "anorak", "vest", "gilet"}
)
MISSING_VALUES = frozenset({"", "none", "null", "n/a", "not applicable", "unknown", "[]"})


def clean_text(value: Any) -> str | None:
    """Return a nonempty normalized string, or None for missing data."""
    if value is None:
        return None
    result = " ".join(str(value).split())
    return None if result.lower() in MISSING_VALUES else result


def is_outerwear(garment_type: Any) -> bool:
    """Match type labels such as 'Jacket' and 'Winter jacket'."""
    name = clean_text(garment_type)
    return bool(name and OUTERWEAR_WORDS.intersection(re.findall(r"[a-z]+", name.lower())))


def parse_colors(value: Any) -> list[str]:
    """Handle lists and text-encoded lists found in source dataset rows."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value) if value.lstrip().startswith("[") else value
        except (ValueError, SyntaxError):
            parsed = value
        value = parsed
    values = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for item in values:
        color = clean_text(item)
        if color and color.casefold() not in {v.casefold() for v in result}:
            result.append(color)
    return result


def normalize_record(
    raw: dict[str, Any], *, source_index: int, image_path: str
) -> dict[str, Any] | None:
    """Convert one Hugging Face garment row to our local JSONL record.

    Image bytes are saved separately by scripts/ingest.py. `image_path` is
    relative to the project root and is NOT a web image URL.
    """
    garment_type = clean_text(raw.get("type"))
    if not is_outerwear(garment_type) or not image_path:
        return None

    colors = parse_colors(raw.get("colors"))
    brand = clean_text(raw.get("brand"))
    cut = clean_text(raw.get("cut"))
    material = clean_text(raw.get("material"))
    pattern = clean_text(raw.get("pattern"))
    category = clean_text(raw.get("category"))
    price_band = clean_text(raw.get("price"))

    # Source price is a category/range, NOT a verified USD price.
    headline = " ".join(x for x in [colors[0] if colors else None, garment_type] if x)
    return {
        "id": f"secondhand-{source_index:06d}",
        "title": headline,
        "source": "local",
        "dataset_id": DATASET_ID,
        "source_index": source_index,
        "image_path": image_path,
        "listing_url": None,  # No live product listing in an archival dataset.
        "price": None,  # Never fabricate a numeric price.
        "price_band": price_band,
        "attributes": {
            "type": garment_type,
            "category": category,
            "colors": colors,
            "material": material,
            "cut": cut,
            "pattern": pattern,
            "brand": brand,
        },
    }
