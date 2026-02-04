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
    database_url: str = Field("", alias="DATABASE_URL")
    db_echo: bool = Field(False, alias="DB_ECHO")
    graph_db_uri: str = Field("", alias="GRAPH_DB_URI")
    graph_db_user: str = Field("neo4j", alias="GRAPH_DB_USER")
    graph_db_password: str = Field("", alias="GRAPH_DB_PASSWORD")
    graph_db_database: str = Field("", alias="GRAPH_DB_DATABASE")
    analytics_max_orders: int = Field(2000, alias="ANALYTICS_MAX_ORDERS")
    hoppscotch_app_url: str = Field("http://localhost:3000", alias="HOPPSCOTCH_APP_URL")
    hoppscotch_admin_url: str = Field("http://localhost:3100", alias="HOPPSCOTCH_ADMIN_URL")
    rate_limit_enabled: bool = Field(False, alias="RATE_LIMIT_ENABLED")
    rate_limit_default: str = Field("600/minute", alias="RATE_LIMIT_DEFAULT")
    otel_enabled: bool = Field(False, alias="OTEL_ENABLED")
    otel_service_name: str = Field("harborline-commerce-api", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field("", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
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
