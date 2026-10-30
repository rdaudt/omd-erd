from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore", populate_by_name=True)

    omd_host: str = Field(alias="OMD_HOST")
    omd_token: str = Field(alias="OMD_TOKEN")
    request_timeout_seconds: float = Field(10.0, alias="OMD_REQUEST_TIMEOUT_SECONDS")
    cache_ttl_seconds: int = Field(300, alias="MARKETPLACE_CACHE_TTL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
