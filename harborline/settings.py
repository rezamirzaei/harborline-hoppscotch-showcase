from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(..., alias="APP_NAME")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_issuer: str = Field(..., alias="JWT_ISSUER")
    token_ttl_seconds: int = Field(..., alias="TOKEN_TTL_SECONDS")
    demo_user: str = Field(..., alias="DEMO_USER")
    demo_password: str = Field(..., alias="DEMO_PASSWORD")
    partner_api_key: str = Field(..., alias="PARTNER_API_KEY")
    webhook_secret: str = Field(..., alias="WEBHOOK_SECRET")
    cors_allow_origins: str = Field(..., alias="CORS_ALLOW_ORIGINS")
    inventory_seed_path: str = Field(..., alias="INVENTORY_SEED_PATH")
    document_prefix: str = Field(..., alias="DOCUMENT_PREFIX")
    ui_defaults_path: str = Field(..., alias="UI_DEFAULTS_PATH")
    request_id_header: str = Field("X-Request-Id", alias="REQUEST_ID_HEADER")
    idempotency_replay_header: str = Field(
        "Idempotency-Replayed",
        alias="IDEMPOTENCY_REPLAY_HEADER",
    )

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


def resolve_env_file() -> Optional[Path]:
    explicit = os.getenv("HARBORLINE_ENV_FILE")
    if explicit:
        return Path(explicit)
    default = Path.cwd() / "config" / "api.env"
    if default.exists():
        return default
    return None


def load_settings() -> Settings:
    env_file = resolve_env_file()
    if env_file:
        return Settings(_env_file=str(env_file))
    return Settings()
