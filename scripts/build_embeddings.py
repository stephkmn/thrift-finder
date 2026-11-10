"""Build the listing embedding index used by /api/search (S2-3).

Encodes every listing in data/listings.jsonl (image + text) with MODEL_NAME and saves
data/embeddings.npz. Re-run after scripts/ingest.py or after changing MODEL_NAME.

Usage:
    python scripts/build_embeddings.py
    python scripts/build_embeddings.py --model openai/clip-vit-base-patch32 --out data/clip.npz
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from backend.app.config import get_settings
from backend.app.data.local_dataset import DEFAULT_LISTINGS, load_listings
from backend.app.ml.encoder import get_encoder
from backend.app.ml.index import DEFAULT_INDEX, build_index, save_index


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.model_name)
    parser.add_argument("--listings", type=Path, default=DEFAULT_LISTINGS)
    parser.add_argument("--out", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    listings = load_listings(args.listings)
    print(f"Encoding {len(listings)} listings with {args.model} ({settings.model_dtype})...")
    started = time.perf_counter()
    index = build_index(
        get_encoder(args.model, settings.model_dtype),
        listings,
        args.model,
        batch_size=args.batch_size,
        on_progress=lambda done, total: print(f"  images {done}/{total}"),
    )
    save_index(index, args.out)
    rows, dims = index.image_embeddings.shape
    print(f"Saved {rows} x {dims} image + text embeddings to {args.out}")
    print(f"Done in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()
