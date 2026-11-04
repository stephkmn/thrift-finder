"""Application settings loaded from environment variables (never from code)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_source: Literal["ebay", "local"] = "local"
    model_name: str = "patrickjohncyh/fashion-clip"
    ebay_client_id: str | None = None
    ebay_client_secret: str | None = Field(default=None, repr=False)


def get_settings() -> Settings:
    return Settings()
