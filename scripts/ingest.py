"""Build the local secondhand-outerwear fallback dataset.

Run from repository root after: pip install -e '.[dev,data]'
    python scripts/ingest.py --limit 25
    python scripts/ingest.py --limit 500
    python scripts/ingest.py --split test --limit 300

This is a licensed archival dataset, not live eBay inventory. Images and
records are saved locally and intentionally excluded from Git.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data.preprocess import (  # noqa: E402
    DATASET_ID,
    is_outerwear,
    normalize_record,
)


def to_pil(value: Any) -> Image.Image:
    """Convert a Hugging Face Image feature (PIL or bytes mapping) to a PIL image."""
    if isinstance(value, Image.Image):
        return value
    if isinstance(value, dict):
        if value.get("bytes"):
            return Image.open(io.BytesIO(value["bytes"]))
        if value.get("path"):
            return Image.open(value["path"])
    raise ValueError("Missing or unsupported image representation")


def ingest(
    *, limit: int, max_scan: int, output: Path, image_dir: Path, revision: str, split: str = "train"
) -> dict[str, int]:
    """Stream dataset; keep unique outerwear photos and normalize metadata."""
    from datasets import load_dataset

    if limit <= 0 or max_scan <= 0:
        raise ValueError("--limit and --max-scan must be positive")
    if split not in {"train", "test"}:
        raise ValueError("--split must be train or test")

    output.parent.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading {DATASET_ID}, revision={revision}, split={split} (streaming)...")
    ds = load_dataset(DATASET_ID, split=split, streaming=True, revision=revision)
    counts = {"scanned": 0, "outerwear": 0, "invalid_images": 0, "duplicates": 0, "saved": 0}
    seen_hashes: set[str] = set()
    staging_path = output.with_suffix(".jsonl.tmp")

    try:
        with staging_path.open("w", encoding="utf-8") as stream:
            for source_index, raw in enumerate(ds):
                if counts["scanned"] >= max_scan or counts["saved"] >= limit:
                    break
                counts["scanned"] += 1
                if not is_outerwear(raw.get("type")):
                    continue
                counts["outerwear"] += 1

                try:
                    img = ImageOps.exif_transpose(to_pil(raw.get("image")))
                    img = img.convert("RGB")
                    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    image_bytes = io.BytesIO()
                    img.save(image_bytes, format="JPEG", quality=85, optimize=True)
                except (ValueError, OSError, UnidentifiedImageError):
                    counts["invalid_images"] += 1
                    continue
                payload = image_bytes.getvalue()
                digest = hashlib.sha256(payload).hexdigest()
                if digest in seen_hashes:
                    counts["duplicates"] += 1
                    continue

                filename = f"secondhand-{source_index:06d}.jpg"
                # Paths in JSONL must be portable within the repository.
                relative_image = (image_dir / filename).relative_to(PROJECT_ROOT)
                rec = normalize_record(
                    raw, source_index=source_index, image_path=relative_image.as_posix()
                )
                if rec is None:
                    continue
                (image_dir / filename).write_bytes(payload)
                seen_hashes.add(digest)
                stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
                counts["saved"] += 1
                if counts["saved"] % 50 == 0:
                    print(f"Saved {counts['saved']} garments; scanned {counts['scanned']} rows")
        if not counts["saved"]:
            raise RuntimeError("Found no usable outerwear; adjust --max-scan or inspect labels")
        staging_path.replace(output)
    finally:
        if staging_path.exists():
            staging_path.unlink()

    print(json.dumps(counts, indent=2))
    print(f"Metadata: {output}")
    print(f"Images:   {image_dir}")
    if counts["saved"] < limit:
        print("WARNING: fewer than the requested count; increase --max-scan")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest licensed secondhand outerwear data")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--split", choices=("train", "test"), default="train")
    parser.add_argument("--max-scan", type=int, default=28_248)
    parser.add_argument(
        "--revision", default="main", help="Pin a Hugging Face commit for reproducibility"
    )
    args = parser.parse_args()
    output_dir = (
        PROJECT_ROOT / "data"
        if args.split == "train"
        else PROJECT_ROOT / "data" / "eval" / "dataset"
    )
    ingest(
        limit=args.limit,
        max_scan=args.max_scan,
        output=output_dir / "listings.jsonl",
        image_dir=output_dir / "images",
        revision=args.revision,
        split=args.split,
    )


if __name__ == "__main__":
    main()
