from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_debug: bool = True

    database_url: str
    redis_url: str

    default_source_system: str = "sample-app"
    auto_migrate: bool = False
    auto_seed: bool = False


settings = Settings()  # type: ignore[call-arg]

