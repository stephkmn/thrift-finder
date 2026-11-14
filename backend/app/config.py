"""Application settings loaded from environment variables (never from code)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_source: Literal["ebay", "local"] = "local"
    model_name: str = "patrickjohncyh/fashion-clip"
    model_dtype: Literal["float32", "float64"] = "float32"
    # Load the model at startup instead of on the first /api/extract request.
    preload_model: bool = True
    # In-memory query cache: query_id -> upload embedding, reused by /api/search.
    query_cache_ttl_seconds: int = Field(default=1800, gt=0)
    query_cache_max_entries: int = Field(default=256, gt=0)
    ebay_client_id: str | None = None
    ebay_client_secret: str | None = Field(default=None, repr=False)
    ebay_environment: Literal["sandbox", "production"] = "production"


def get_settings() -> Settings:
    return Settings()
