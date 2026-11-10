"""Attribute-edit query embeddings (AI Task 2, S2-4; docs/PHASE2_SPRINT_PLAN.md §4.3).

Edits steer the search away from the original look while keeping the rest of it:
    q_img = normalize(E(upload) + λ · (E_txt(edited) − E_txt(original)))
    q_txt = E_txt(edited)
E_txt(attributes) embeds a caption built from the attributes, e.g. "a photo of a brown
suede regular fit bomber jacket with a hood." With no edits the direction is zero and
q_img is the upload's own embedding.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from backend.app.cache import EmbeddingKind
from backend.app.ml.attributes import Vocabulary, load_vocabulary
from backend.app.ml.encoder import Encoder, l2_normalize
from backend.app.schemas import Attributes

# Re-exported for callers of build_query; defined once, by the query cache.
__all__ = ["EDIT_STRENGTH", "EmbeddingKind", "Query", "build_query", "describe", "photo_caption"]

# attributes.yaml only changes between deploys, so read it once instead of on every search.
_default_vocabulary = lru_cache(maxsize=1)(load_vocabulary)

# Edit strength λ. 1.0 is the plan's starting point; tuned on the evaluation set in S3-1.
EDIT_STRENGTH = 1.0


@dataclass(frozen=True)
class Query:
    # Edited upload embedding; None for text-only uploads, which have no image side.
    image: np.ndarray | None
    # The text-side query: the edited caption, or the edited description for text-only uploads.
    text: np.ndarray


def photo_caption(words: list[str]) -> str:
    """'a photo of a ...' / 'a photo of an ...' around the non-empty words, as CLIP expects."""
    phrase = " ".join(word for word in words if word)
    article = "an" if phrase[:1].lower() in "aeiou" else "a"
    return f"a photo of {article} {phrase}."


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def describe(attributes: Attributes, vocabulary: Vocabulary) -> str:
    """Caption for a set of attributes, using each feature's prompt phrase when known."""
    caption = photo_caption(
        [attributes.color, attributes.fabric, attributes.fit, attributes.category]
    )
    features = [
        vocabulary.features[f].phrase if f in vocabulary.features else f
        for f in attributes.others or []
    ]
    return caption if not features else f"{caption[:-1]} with {_join(features)}."


def build_query(
    encoder: Encoder,
    embedding: np.ndarray,
    kind: EmbeddingKind,
    original: Attributes,
    edited: Attributes,
    *,
    vocabulary: Vocabulary | None = None,
    strength: float = EDIT_STRENGTH,
) -> Query:
    """Turn a cached upload embedding plus the user's attribute edits into a search query.

    For a text-only upload the cached embedding is the description's text embedding, so
    the edit is applied to it and it becomes the text-side query; there is no image side.
    """
    vocabulary = vocabulary or _default_vocabulary()
    original_text, edited_text = encoder.encode_texts(
        [describe(original, vocabulary), describe(edited, vocabulary)]
    )
    edited_upload = l2_normalize(embedding + strength * (edited_text - original_text))
    if kind == "text":
        return Query(image=None, text=edited_upload)
    return Query(image=edited_upload, text=edited_text)
