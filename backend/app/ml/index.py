"""Precomputed listing embeddings (S2-3): one image and one text embedding per listing.

scripts/build_embeddings.py encodes every listing once and saves data/embeddings.npz, so
/api/search never re-encodes listings at request time (500 images take ~40 s on a CPU).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.app.config import get_settings
from backend.app.data.local_dataset import DEFAULT_LISTINGS, PROJECT_ROOT, load_listings
from backend.app.data.preprocess import clean_text, parse_colors
from backend.app.ml.attributes import load_vocabulary
from backend.app.ml.encoder import Encoder
from backend.app.ml.query import photo_caption

if TYPE_CHECKING:
    from PIL import Image

DEFAULT_INDEX = PROJECT_ROOT / "data" / "embeddings.npz"

# Source cut labels mapped onto our fit vocabulary; collar shapes and the like are dropped.
CUT_TO_FIT = {
    "regular": "regular fit",
    "loose": "oversized",
    "long": "longline",
    "cropped": "cropped",
}
MATERIAL_ALIASES = {"poly": "polyester", "nylone": "nylon", "polyamide": "nylon"}
# Pattern labels that say nothing visible about the garment.
UNINFORMATIVE_PATTERNS = {"other", "plain"}


@dataclass(frozen=True)
class ListingIndex:
    """Listings plus their L2-normalized embeddings; row i of each array is listings[i]."""

    listings: list[dict[str, Any]]
    image_embeddings: np.ndarray
    text_embeddings: np.ndarray
    model_name: str


@lru_cache(maxsize=1)
def _synonyms() -> dict[str, dict[str, str]]:
    vocabulary = load_vocabulary()
    return {name: spec.synonyms for name, spec in vocabulary.scalars.items()}


def _main_material(material: str | None) -> str | None:
    """'34%polyester 66%viscose' -> 'viscose'; 'PU leather' -> 'pu leather'."""
    text = (clean_text(material) or "").lower().split("lining")[0]
    shares = re.findall(r"(\d+)\s*%\s*([a-z]+)", text)
    if shares:
        word = max(shares, key=lambda share: int(share[0]))[1]
    else:
        word = " ".join(re.findall(r"[a-z]+", text)[:3])
    word = MATERIAL_ALIASES.get(word, word)
    return _synonyms()["fabric"].get(word, word) or None


def listing_text(listing: dict[str, Any]) -> str:
    """Describe a listing in the same words the query side uses, e.g.
    'a photo of a gray striped viscose regular fit blazer.'"""
    attributes = listing.get("attributes") or {}
    color_synonyms = _synonyms()["color"]
    colors = [color_synonyms.get(c.lower(), c.lower()) for c in attributes.get("colors") or []]
    pattern = (clean_text(attributes.get("pattern")) or "").lower()
    # parse_colors is the dataset's generic list-cell parser; cut cells look like "['Regular']".
    cuts = parse_colors(attributes.get("cut"))
    fits = [CUT_TO_FIT[c.lower()] for c in cuts if c.lower() in CUT_TO_FIT]
    garment = (clean_text(attributes.get("type")) or listing.get("title") or "jacket").lower()
    return photo_caption(
        [
            " and ".join(colors[:2]),
            "" if pattern in UNINFORMATIVE_PATTERNS else pattern,
            _main_material(attributes.get("material")) or "",
            fits[0] if fits else "",
            garment,
        ]
    )


def _open_listing_image(listing: dict[str, Any]) -> Image.Image:
    from PIL import Image

    with Image.open(PROJECT_ROOT / listing["image_path"]) as image:
        image.load()
        return image


def build_index(
    encoder: Encoder,
    listings: list[dict[str, Any]],
    model_name: str,
    *,
    batch_size: int = 32,
    open_image: Callable[[dict[str, Any]], Image.Image] = _open_listing_image,
    on_progress: Callable[[int, int], None] | None = None,
) -> ListingIndex:
    """Encode every listing's image and text. Images are opened one batch at a time."""
    if not listings:
        raise ValueError("No listings to index; run scripts/ingest.py first.")
    image_chunks = []
    for start, batch in _batches(listings, batch_size):
        image_chunks.append(encoder.encode_images([open_image(listing) for listing in batch]))
        if on_progress:
            on_progress(start + len(batch), len(listings))
    return ListingIndex(
        listings=listings,
        image_embeddings=np.concatenate(image_chunks).astype(np.float32),
        text_embeddings=encoder.encode_texts([listing_text(item) for item in listings]).astype(
            np.float32
        ),
        model_name=model_name,
    )


def _batches(items: list, size: int) -> Iterator[tuple[int, list]]:
    for start in range(0, len(items), size):
        yield start, items[start : start + size]


def save_index(index: ListingIndex, path: Path = DEFAULT_INDEX) -> None:
    """Write atomically, so a crash mid-save never leaves a half-written index behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".npz.tmp")
    with staging.open("wb") as handle:
        np.savez(
            handle,
            ids=np.array([listing["id"] for listing in index.listings]),
            image=index.image_embeddings,
            text=index.text_embeddings,
            model_name=np.array(index.model_name),
        )
    os.replace(staging, path)


def load_index(
    model_name: str, path: Path = DEFAULT_INDEX, listings_path: Path = DEFAULT_LISTINGS
) -> ListingIndex:
    """Load the saved embeddings and pair them with listings.jsonl, refusing stale data.

    Embeddings from different models live in different spaces, so an index built with
    another MODEL_NAME is rejected rather than silently returning nonsense rankings.
    """
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run scripts/build_embeddings.py first.")
    with np.load(path, allow_pickle=False) as saved:
        ids = [str(i) for i in saved["ids"]]
        image, text = saved["image"], saved["text"]
        saved_model = str(saved["model_name"])
    if saved_model != model_name:
        raise ValueError(
            f"{path} was built with {saved_model}, but MODEL_NAME is {model_name}; "
            "rebuild it with scripts/build_embeddings.py."
        )
    by_id = {
        listing["id"]: listing for listing in load_listings(listings_path, require_image=False)
    }
    if set(ids) != set(by_id):
        raise ValueError(
            f"{path} does not match {listings_path}; rebuild it with scripts/build_embeddings.py."
        )
    return ListingIndex([by_id[i] for i in ids], image, text, saved_model)


@lru_cache(maxsize=1)
def get_index() -> ListingIndex:
    """The configured model's index, loaded once per process."""
    return load_index(get_settings().model_name)
