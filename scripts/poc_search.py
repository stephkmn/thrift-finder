"""Proof of concept (S1-7): photo -> attributes -> top-k most similar images in a folder.

The folder stands in for Member B's local listings until data/listings.jsonl and
data/embeddings.npy exist (S2-2, S2-3); ranking here is plain image-to-image cosine.

Usage:
    python scripts/poc_search.py samples/query.jpg --gallery data/samples/listings
    python scripts/poc_search.py query.jpg --gallery photos/ --text "brown suede" --top-k 3
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image

from backend.app.config import get_settings
from backend.app.ml.attributes import AttributeExtractor
from backend.app.ml.encoder import get_encoder

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", type=Path, help="query photo")
    parser.add_argument("--gallery", type=Path, required=True, help="folder of listing images")
    parser.add_argument("--text", help="optional description, e.g. 'brown suede with a hood'")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=get_settings().model_name)
    args = parser.parse_args()

    gallery = sorted(
        p
        for p in args.gallery.iterdir()
        if p.suffix.lower() in IMAGE_SUFFIXES and p.resolve() != args.image.resolve()
    )
    if not gallery:
        raise SystemExit(f"No JPG/PNG/WebP images in {args.gallery}")

    started = time.perf_counter()
    encoder = get_encoder(args.model, get_settings().model_dtype)
    extractor = AttributeExtractor(encoder)
    print(f"Loaded {args.model} in {time.perf_counter() - started:.1f}s")

    with Image.open(args.image) as image:
        query_image = image.convert("RGB")
    started = time.perf_counter()
    attributes, confidences, query_embedding = extractor.extract(image=query_image, text=args.text)
    print(f"\nAttributes ({(time.perf_counter() - started) * 1000:.0f} ms):")
    for name in ("category", "color", "fabric", "fit"):
        print(f"  {name:9s} {getattr(attributes, name):15s} {getattr(confidences, name):.0%}")
    features = ", ".join(f"{f} {s:.0%}" for f, s in (confidences.others or {}).items())
    print(f"  {'others':9s} {features or 'none detected'}")

    images = []
    for path in gallery:
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
    started = time.perf_counter()
    gallery_embeddings = encoder.encode_images(images)
    print(f"\nEmbedded {len(gallery)} gallery images in {time.perf_counter() - started:.1f}s")

    similarities = gallery_embeddings @ query_embedding
    print(f"\nTop {min(args.top_k, len(gallery))} matches (cosine similarity):")
    for rank, index in enumerate(np.argsort(-similarities)[: args.top_k], start=1):
        print(f"  {rank}. {similarities[index]:.3f}  {gallery[index].name}")


if __name__ == "__main__":
    main()
