"""Pydantic mirrors of `frontend/src/api/types.ts` (S1-4).

Change in lockstep with the TypeScript file; the frontend is the authoritative
contract draft per docs/PHASE2_SPRINT_PLAN.md §4.2.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Attributes(BaseModel):
    """Outerwear attributes. Scalars are always present; `others` is None when empty (never [])."""

    model_config = ConfigDict(extra="forbid")

    category: str
    color: str
    fabric: str
    fit: str
    others: list[str] | None = None


class Confidences(BaseModel):
    """0-1 confidence per scalar; `others` is a per-feature map or None, matching Attributes."""

    model_config = ConfigDict(extra="forbid")

    category: float = Field(ge=0.0, le=1.0)
    color: float = Field(ge=0.0, le=1.0)
    fabric: float = Field(ge=0.0, le=1.0)
    fit: float = Field(ge=0.0, le=1.0)
    others: dict[str, float] | None = None


class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attributes: Attributes
    confidences: Confidences
    query_id: str

    @model_validator(mode="after")
    def _validate_others_parity(self) -> ExtractResponse:
        attrs_none = self.attributes.others is None
        confs_none = self.confidences.others is None
        if attrs_none != confs_none:
            raise ValueError(
                "attributes.others and confidences.others must both be None or both be set"
            )
        if self.attributes.others == []:
            raise ValueError("attributes.others must be null when empty, never []")
        if self.attributes.others is not None and self.confidences.others is not None:
            missing = set(self.attributes.others) - set(self.confidences.others)
            extra = set(self.confidences.others) - set(self.attributes.others)
            if missing or extra:
                raise ValueError(
                    f"confidences.others keys must match attributes.others "
                    f"(missing={sorted(missing)}, extra={sorted(extra)})"
                )
            for name, score in self.confidences.others.items():
                if not 0.0 <= score <= 1.0:
                    raise ValueError(f"confidences.others['{name}']={score} outside [0,1]")
        return self


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    original_attributes: Attributes
    edited_attributes: Attributes
    text: str | None = None


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    # Required keys with nullable values: local archive items have no verified price or
    # purchase link (docs/DATA.md), so both are None for them. Mirrors types.ts.
    price: float | None
    image_url: str
    listing_url: str | None
    source: Literal["ebay", "local"]
    match_score: float = Field(ge=0.0, le=100.0)


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[SearchResult] = Field(max_length=10)


# GET /api/item/{id} (S3-6): details for an archive listing. eBay listings are never stored
# (docs/EBAY_FEASIBILITY.md), so the details page builds those from the search result instead.
class DatasetLabels(BaseModel):
    """The listing's labels exactly as the dataset has them (any may be missing)."""

    model_config = ConfigDict(extra="forbid")

    type: str | None
    category: str | None
    colors: list[str]
    material: str | None
    cut: str | None
    pattern: str | None
    brand: str | None


class AttributeComparison(BaseModel):
    """One searched attribute next to the listing's label, mapped onto our vocabulary."""

    model_config = ConfigDict(extra="forbid")

    attribute: Literal["category", "color", "fabric", "fit"]
    yours: str
    listing: str | None  # None when the dataset has no label for it
    match: bool | None  # None when the label can't tell


class ItemCredit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    url: str


class ItemDetails(BaseModel):
    """Mirrors ItemDetails in frontend/src/api/types.ts. Archive items have no price or link."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    image_url: str
    source: Literal["local"]
    dataset_labels: DatasetLabels
    # Empty unless the request passed the searched attributes as query parameters.
    comparison: list[AttributeComparison]
    credit: ItemCredit
