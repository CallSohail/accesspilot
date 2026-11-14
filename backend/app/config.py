"""Environment-driven configuration.

No secrets are stored in code. All provider-related settings come from
environment variables or a local `.env` file that the operator supplies.

Values fall back to safe defaults so the deterministic analysis always
works even without an AI provider configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime configuration. Loaded once at startup."""

    # Upload handling
    max_upload_mb: int = 25
    upload_dir: str = ".scratch/uploads"

    # AI provider (OpenAI-compatible endpoint; Nebius-hosted Nemotron by default)
    # Leave api_key empty to disable AI suggestions entirely.
    ai_enabled: bool = False
    ai_base_url: str = "https://api.nebius.ai/llm/v1"
    ai_model: str = "nemotron"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 60.0
    ai_user_confirmed: bool = False  # explicit opt-in required to send content

    # App
    app_name: str = "AccessPilot"
    version: str = "0.1.0"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])

    def ai_configured(self) -> bool:
        return self.ai_enabled and bool(self.ai_api_key) and self.ai_user_confirmed


def load_settings() -> Settings:
    """Build a Settings object from environment variables."""
    return Settings(
        max_upload_mb=int(os.environ.get("ACCESSPILOT_MAX_UPLOAD_MB", "25")),
        upload_dir=os.environ.get("ACCESSPILOT_UPLOAD_DIR", ".scratch/uploads"),
        ai_enabled=_to_bool(os.environ.get("ACCESSPILOT_AI_ENABLED")),
        ai_base_url=os.environ.get(
            "ACCESSPILOT_AI_BASE_URL", "https://api.nebius.ai/llm/v1"
        ),
        ai_model=os.environ.get("ACCESSPILOT_AI_MODEL", "nemotron"),
        ai_api_key=os.environ.get("ACCESSPILOT_AI_API_KEY", ""),
        ai_timeout_seconds=float(
            os.environ.get("ACCESSPILOT_AI_TIMEOUT_SECONDS", "60")
        ),
        ai_user_confirmed=_to_bool(
            os.environ.get("ACCESSPILOT_AI_USER_CONFIRMED")
        ),
        app_name=os.environ.get("ACCESSPILOT_APP_NAME", "AccessPilot"),
        version=os.environ.get("ACCESSPILOT_VERSION", "0.1.0"),
        cors_origins=[
            o.strip()
            for o in os.environ.get(
                "ACCESSPILOT_CORS_ORIGINS", "http://localhost:5173"
            ).split(",")
            if o.strip()
        ],
    )
