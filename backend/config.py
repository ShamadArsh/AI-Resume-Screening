# ============================================================
# AI Resume Screening — Central Configuration
# ============================================================
# Reads ALL settings from environment variables (.env).
# Follows pydantic-settings for typed, validated config.
# ============================================================

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ------------------------------------------------------------------
# Base paths
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent   # /workspace
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_name: str = "AI Resume Screening"
    app_env: str = Field(default="development", description="development | production")
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 8501

    # ---- Gemini (2.5 Flash) ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.2
    gemini_max_tokens: int = 8192
    gemini_timeout: int = 60          # seconds
    gemini_max_retries: int = 3

    # ---- Airtable ----
    airtable_api_key: str = ""
    airtable_base_id: str = ""
    airtable_table_name: str = "Candidates"

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600             # 1 hour
    cache_enabled: bool = True

    # ---- Google OAuth (Gmail + Calendar) ----
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    gmail_refresh_token: str = ""
    calendar_refresh_token: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    # Path to credentials.json downloaded from Google Cloud Console
    google_credentials_file: str = ""
    calendar_id: str = "primary"
    interview_duration_minutes: int = 60
    interview_lookahead_days: int = 7

    # ---- Email ----
    smtp_from_email: str = "recruiter@example.com"
    smtp_from_name: str = "AI Recruiter"

    # ---- Business Rules ----
    shortlist_threshold: int = 80
    review_threshold: int = 60

    # ---- n8n ----
    n8n_webhook_url: str = "http://localhost:5678/webhook"
    n8n_api_key: str = ""

    # ---- Security ----
    secret_key: str = "change-me-in-production"
    allowed_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


# Convenience module-level instance
settings = get_settings()
