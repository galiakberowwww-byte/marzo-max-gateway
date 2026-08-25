from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    max_bot_token: str
    max_webhook_secret: str = ""
    max_api_base_url: str = "https://platform-api2.max.ru"
    max_ca_bundle: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
