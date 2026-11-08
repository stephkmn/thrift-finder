"""Test doubles shared by the ML tests: a fake CLIP that needs no torch or model download."""

from __future__ import annotations

import re

import numpy as np


class FakeImage:
    """Stands in for a PIL image: the fake encoder embeds its description instead of pixels."""

    def __init__(self, description: str) -> None:
        self.description = description


class FakeEncoder:
    """Embeds text as a sum of one-hot word vectors; words after 'without' subtract.

    One-hot keeps unrelated words exactly orthogonal, so scores only move for shared words.
    """

    logit_scale = 100.0
    dim = 1024
    stopwords = frozenset({"a", "an", "of", "the", "photo", "product", "with"})

    def __init__(self) -> None:
        self._index: dict[str, int] = {}

    def _word(self, word: str) -> np.ndarray:
        vector = np.zeros(self.dim)
        vector[self._index.setdefault(word, len(self._index))] = 1.0
        return vector

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dim)
        sign = 1.0
        for word in re.findall(r"[a-z]+", text.lower()):
            if word == "without":
                sign = -1.0
            elif word not in self.stopwords:
                vector += sign * self._word(word)
        return vector / max(np.linalg.norm(vector), 1e-12)

    def encode_texts(self, texts):
        return np.stack([self._embed(text) for text in texts]).astype(np.float32)

    def encode_images(self, images):
        return np.stack([self._embed(image.description) for image in images]).astype(np.float32)
