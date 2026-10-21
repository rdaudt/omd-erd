from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    omd_host: str = Field(alias="OMD_HOST")
    omd_token: str = Field(alias="OMD_TOKEN")
    request_timeout_seconds: float = Field(10.0, alias="OMD_REQUEST_TIMEOUT_SECONDS")
    cache_ttl_seconds: int = Field(60, alias="OMD_CACHE_TTL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
