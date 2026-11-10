"""Zero-shot outerwear attribute extraction (AI Task 1, docs/PHASE2_SPRINT_PLAN.md §4.3).

Scalar attributes: score every vocabulary value's prompt embedding against the query
embedding, softmax with CLIP's logit scale, report the argmax and its probability.
`others` features: independent "with X" vs. "without X" softmax per feature.
An optional text description overrides the model wherever it names a vocabulary value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import yaml

from backend.app.config import get_settings
from backend.app.ml.encoder import Encoder, get_encoder, l2_normalize
from backend.app.schemas import Attributes, Confidences

if TYPE_CHECKING:
    from PIL import Image

VOCABULARY_PATH = Path(__file__).with_name("attributes.yaml")
SCALAR_NAMES = ("category", "color", "fabric", "fit")

# Confidence reported for anything the user stated in their own description.
STATED_CONFIDENCE = 1.0
NEGATIONS = (
    "no", "not", "non", "without", "never",
    "don't", "dont", "doesn't", "doesnt", "didn't", "didnt",
    "isn't", "isnt", "aren't", "arent", "won't", "wont",
)  # fmt: skip
# How far back a negation reaches: "I don't want a hood" puts "don't" three words before "hood".
NEGATION_WINDOW = 3
# A negation never reaches across these: "no zip, keep the hood", "no hood but a zipper".
CLAUSE_BREAK = re.compile(r"[,;.!?]|\b(?:but|and)\b")


@dataclass(frozen=True)
class ScalarSpec:
    values: list[str]
    templates: list[str]
    synonyms: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSpec:
    phrase: str
    synonyms: list[str] = field(default_factory=list)
    threshold: float | None = None  # overrides the shared others threshold


@dataclass(frozen=True)
class Vocabulary:
    scalars: dict[str, ScalarSpec]
    features: dict[str, FeatureSpec]
    others_threshold: float
    with_template: str
    without_template: str


class Extraction(NamedTuple):
    attributes: Attributes
    confidences: Confidences
    # Query embedding (image, or text when there is no image); /api/search reuses it via query_id.
    embedding: np.ndarray


def load_vocabulary(path: Path = VOCABULARY_PATH) -> Vocabulary:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    scalars = {name: ScalarSpec(**raw["scalars"][name]) for name in SCALAR_NAMES}
    for name, spec in scalars.items():
        unknown = set(spec.synonyms.values()) - set(spec.values)
        if unknown:
            raise ValueError(f"{name} synonyms point at unknown values: {sorted(unknown)}")
    others = raw["others"]
    return Vocabulary(
        scalars=scalars,
        features={name: FeatureSpec(**spec) for name, spec in others["features"].items()},
        others_threshold=float(others["threshold"]),
        with_template=others["with_template"],
        without_template=others["without_template"],
    )


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return shifted / shifted.sum(axis=-1, keepdims=True)


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Whole-word match that also accepts a plural ("hoods", "patches")."""
    return re.compile(rf"\b{re.escape(phrase)}(?:e?s)?\b", re.IGNORECASE)


def _is_negated(text: str, start: int) -> bool:
    """True when a NEGATIONS word, or "instead of", sits within NEGATION_WINDOW words before
    `start` in the same clause."""
    # Phone keyboards type a curly apostrophe in "don't".
    before = text[:start].lower().replace("\u2019", "'")
    words = re.findall(r"[a-z']+", CLAUSE_BREAK.split(before)[-1])
    preceding = words[-NEGATION_WINDOW:]
    # A negation carries through an "or" list: "without a hood or zipper".
    if "or" in preceding:
        preceding = words
    return "instead of" in " ".join(preceding) or any(word in NEGATIONS for word in preceding)


class AttributeExtractor:
    """Holds precomputed prompt embeddings; `extract()` is cheap after construction."""

    def __init__(self, encoder: Encoder, vocabulary: Vocabulary | None = None) -> None:
        self.encoder = encoder
        self.vocabulary = vocabulary or load_vocabulary()
        self._scalar_prompts = {
            name: self._ensemble(spec) for name, spec in self.vocabulary.scalars.items()
        }
        phrases = [spec.phrase for spec in self.vocabulary.features.values()]
        self._with_prompts = encoder.encode_texts(
            [self.vocabulary.with_template.format(phrase=p) for p in phrases]
        )
        self._without_prompts = encoder.encode_texts(
            [self.vocabulary.without_template.format(phrase=p) for p in phrases]
        )

    def _ensemble(self, spec: ScalarSpec) -> np.ndarray:
        """One embedding per value: the normalized mean over all of its prompt templates."""
        prompts = [t.format(value=v) for v in spec.values for t in spec.templates]
        embedded = self.encoder.encode_texts(prompts).reshape(
            len(spec.values), len(spec.templates), -1
        )
        return l2_normalize(embedded.mean(axis=1))

    def extract(self, image: Image.Image | None = None, text: str | None = None) -> Extraction:
        text = text.strip() if text else None
        if image is None and not text:
            raise ValueError("extract() needs an image, text, or both.")

        query = (
            self.encoder.encode_images([image])[0]
            if image is not None
            else self.encoder.encode_texts([text])[0]
        )
        attributes, confidences, others = self._zero_shot(query)
        if image is None:
            # Without a photo, "with X" vs. "without X" compares two sentences, and any
            # description that says "with" leans towards every feature. Report only the
            # features the text actually names.
            others.clear()
        if text:
            self._apply_text(text, attributes, confidences, others)
        return Extraction(
            Attributes(**attributes, others=list(others) or None),
            Confidences(**confidences, others=others or None),
            query,
        )

    def _zero_shot(self, query: np.ndarray) -> tuple[dict, dict, dict[str, float]]:
        """Model guesses: scalar values, their confidences, and found features -> P(with)."""
        scale = self.encoder.logit_scale
        attributes: dict = {}
        confidences: dict = {}
        for name, prompts in self._scalar_prompts.items():
            probs = _softmax(scale * (prompts @ query))
            best = int(probs.argmax())
            attributes[name] = self.vocabulary.scalars[name].values[best]
            confidences[name] = round(float(probs[best]), 4)

        pair_logits = scale * np.stack(
            [self._with_prompts @ query, self._without_prompts @ query], axis=-1
        )
        p_with = _softmax(pair_logits)[:, 0]
        default = self.vocabulary.others_threshold
        others = {
            feature: round(float(p), 4)
            for (feature, spec), p in zip(self.vocabulary.features.items(), p_with, strict=True)
            if p > (spec.threshold if spec.threshold is not None else default)
        }
        return attributes, confidences, others

    def _apply_text(
        self, text: str, attributes: dict, confidences: dict, others: dict[str, float]
    ) -> None:
        """Override model guesses with whatever the description states explicitly."""
        for name, spec in self.vocabulary.scalars.items():
            stated = self._stated_value(text, spec)
            guess = attributes[name]
            # A generic word ("jacket") must not replace a more specific guess ("bomber jacket").
            if stated is None or (stated != guess and _phrase_pattern(stated).search(guess)):
                continue
            attributes[name] = stated
            confidences[name] = STATED_CONFIDENCE

        for feature, spec in self.vocabulary.features.items():
            terms = [feature, *spec.synonyms]
            match = next((m for t in terms if (m := _phrase_pattern(t).search(text))), None)
            if match is None:
                continue
            if _is_negated(text, match.start()):
                others.pop(feature, None)
            else:
                others[feature] = STATED_CONFIDENCE

    @staticmethod
    def _stated_value(text: str, spec: ScalarSpec) -> str | None:
        """The vocabulary value the text names, preferring the longest, then earliest, match."""
        terms = {value: value for value in spec.values} | spec.synonyms
        matches = [
            (-len(term), match.start(), value)
            for term, value in terms.items()
            if (match := _phrase_pattern(term).search(text))
            and not _is_negated(text, match.start())
        ]
        return min(matches)[2] if matches else None


@lru_cache(maxsize=1)
def get_extractor() -> AttributeExtractor:
    """The configured model's extractor, built once per process (prompt embeddings included)."""
    settings = get_settings()
    return AttributeExtractor(get_encoder(settings.model_name, settings.model_dtype))


def extract_attributes(image: Image.Image | None = None, text: str | None = None) -> Extraction:
    """Entry point for POST /api/extract (S2-1)."""
    return get_extractor().extract(image=image, text=text)
