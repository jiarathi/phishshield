from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- API / deployment ---
    environment: str = Field(default="dev", description="dev|prod")
    allowed_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", description="Comma-separated origins for CORS")

    # --- Input safety ---
    max_text_length: int = Field(default=5000, ge=1)
    max_urls_per_message: int = Field(default=10, ge=0, le=50)

    # --- Scoring thresholds (tune via evaluation) ---
    scam_threshold: float = Field(default=0.65, ge=0.0, le=1.0)

    # --- Optional reputation keys ---
    enable_reputation_lookups: bool = Field(default=False, description="If true, perform outbound reputation lookups (GSB/VT) when keys exist.")
    google_safe_browsing_api_key: str | None = None
    virustotal_api_key: str | None = None

    # --- Network safety ---
    http_timeout_seconds: float = Field(default=4.0, ge=0.5, le=30.0)

    # --- Abuse controls ---
    rate_limit_per_minute: int = Field(default=60, ge=1, le=600, description="Requests per minute per IP for /analyze")

settings = Settings()
