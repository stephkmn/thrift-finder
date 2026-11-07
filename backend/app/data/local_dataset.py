"""Read normalized local garment records for retrieval and embedding generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LISTINGS = PROJECT_ROOT / "data" / "listings.jsonl"


def load_listings(
    path: str | Path = DEFAULT_LISTINGS, *, require_image: bool = True
) -> list[dict[str, Any]]:
    """Load nonduplicate JSONL records and validate their saved image paths.

    Raises on malformed lines; silent corruption should not be hidden.
    The caller may set `require_image=False` for unit tests or metadata inspection.
    """
    file_path = Path(path)
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with file_path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON at {file_path}:{line_no}") from exc
            if not isinstance(rec, dict):
                raise ValueError(f"Expected object at {file_path}:{line_no}")
            if not rec.get("id") or not rec.get("title") or not rec.get("image_path"):
                raise ValueError(f"Missing required field at {file_path}:{line_no}")
            if rec["id"] in seen_ids:
                continue
            image_path = Path(rec["image_path"])
            if image_path.is_absolute() or ".." in image_path.parts:
                raise ValueError(f"Unsafe image path at {file_path}:{line_no}")
            if require_image and not (PROJECT_ROOT / image_path).is_file():
                raise FileNotFoundError(f"Image missing for {rec['id']}: {image_path}")
            records.append(rec)
            seen_ids.add(rec["id"])
    return records
