from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    max_bot_token: str
    max_webhook_secret: str = ""
    max_api_base_url: str = "https://platform-api2.max.ru"
    max_ca_bundle: str | None = None

    # Existing MAX bot ingress forwards every accepted update to the canonical
    # Rodcom runtime. Keep this empty during deployment only; /webhooks/max
    # fails closed with 503 until the target is configured.
    rodcom_webhook_url: str = ""
    # If omitted, use the same secret that MAX sends to this ingress.
    rodcom_webhook_secret: str = ""
    rodcom_request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
