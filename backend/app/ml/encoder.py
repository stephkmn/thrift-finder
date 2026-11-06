"""CLIP / FashionCLIP encoder: images and text in, L2-normalized embeddings out.

Everything downstream (attribute extraction, embedding cache, re-ranking) talks to the
`Encoder` protocol, so tests can swap in a fake without loading torch.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

import numpy as np

if TYPE_CHECKING:
    from PIL import Image

PRIMARY_MODEL = "patrickjohncyh/fashion-clip"
BASELINE_MODEL = "openai/clip-vit-base-patch32"


class Encoder(Protocol):
    """Anything that maps images and text into one shared, normalized embedding space."""

    @property
    def logit_scale(self) -> float: ...

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray: ...

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray: ...


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


class ClipEncoder:
    """Hugging Face CLIP model on CPU.

    `dtype="float64"` exists for machines whose float32 BLAS returns garbage (seen on
    macOS 14.2: every FashionCLIP output was NaN). Embeddings are always returned as
    float32 NumPy arrays whatever the compute dtype.
    """

    def __init__(self, model_name: str = PRIMARY_MODEL, dtype: str = "float32") -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        if dtype not in ("float32", "float64"):
            raise ValueError(f"dtype must be 'float32' or 'float64', got {dtype!r}")
        self._torch = torch
        self._dtype = getattr(torch, dtype)
        self.model_name = model_name
        self._model = CLIPModel.from_pretrained(model_name).eval().to(self._dtype)
        self._processor = CLIPProcessor.from_pretrained(model_name)

    @property
    def logit_scale(self) -> float:
        return float(self._model.logit_scale.detach().exp())

    def encode_images(self, images: Sequence[Image.Image], batch_size: int = 16) -> np.ndarray:
        chunks = []
        for start in range(0, len(images), batch_size):
            batch = [image.convert("RGB") for image in images[start : start + batch_size]]
            pixels = self._processor(images=batch, return_tensors="pt")["pixel_values"]
            with self._torch.no_grad():
                # Call the sub-modules directly: get_image_features changed its return
                # type in transformers 5, while these layers are stable across 4.x and 5.x.
                pooled = self._model.vision_model(pixel_values=pixels.to(self._dtype)).pooler_output
                chunks.append(self._model.visual_projection(pooled))
        return self._finish(chunks)

    def encode_texts(self, texts: Sequence[str], batch_size: int = 64) -> np.ndarray:
        chunks = []
        for start in range(0, len(texts), batch_size):
            tokens = self._processor(
                text=list(texts[start : start + batch_size]),
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            with self._torch.no_grad():
                pooled = self._model.text_model(
                    input_ids=tokens["input_ids"], attention_mask=tokens["attention_mask"]
                ).pooler_output
                chunks.append(self._model.text_projection(pooled))
        return self._finish(chunks)

    def _finish(self, chunks: list) -> np.ndarray:
        vectors = self._torch.cat(chunks).double().numpy()
        if not np.isfinite(vectors).all():
            raise RuntimeError(
                f"{self.model_name} produced NaN/inf embeddings. This machine's float32 math "
                "is likely broken (known on macOS 14.2); set MODEL_DTYPE=float64 in .env."
            )
        return l2_normalize(vectors).astype(np.float32)


@lru_cache(maxsize=2)
def get_encoder(model_name: str = PRIMARY_MODEL, dtype: str = "float32") -> ClipEncoder:
    """Load a model once per process; reused by the API and scripts."""
    return ClipEncoder(model_name, dtype)
