"""WebPilot Agent — Centralized configuration via Pydantic Settings.

All configuration is loaded from environment variables (or .env file).
No secrets should ever be hardcoded here or anywhere in the codebase.
"""

from pathlib import Path
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    # Option A+C: Uses Anthropic API key (separate from subscription).
    # $5 credit lasts months because Option C minimizes LLM calls —
    # CSS selectors handle 90% of cases, vision API is the rare fallback.
    anthropic_api_key: str = Field(description="Anthropic API key from console.anthropic.com")
    llm_model: str = Field(default="claude-sonnet-4-20250514", description="Claude model to use")
    llm_max_tokens: int = Field(default=1024, description="Max tokens per LLM call")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://webpilot:webpilot@localhost:5432/webpilot"
    )
    database_echo: bool = Field(default=False, description="Echo SQL queries")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Credential Vault ---
    vault_encryption_key: str = Field(description="Fernet key for credential encryption")

    # --- Browser ---
    browser_headless: bool = Field(default=False, description="Run browser headless")
    browser_slow_mo: int = Field(default=100, description="ms delay between browser actions")
    browser_timeout: int = Field(default=30000, description="ms max wait for selectors")

    # --- API Server ---
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_secret_key: str = Field(default="change-me-in-production")

    # --- Checkpoints ---
    checkpoint_mode: str = Field(default="cli", description="cli | websocket | auto")
    checkpoint_timeout: int = Field(default=300, description="Seconds to wait for human response")

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="json | console")
    screenshot_dir: Path = Field(default=Path("./data/screenshots"))

    # --- Paths ---
    workflows_dir: Path = Field(default=Path("./workflows"))

    @field_validator("checkpoint_mode")
    @classmethod
    def validate_checkpoint_mode(cls, v: str) -> str:
        allowed = {"cli", "websocket", "auto"}
        if v not in allowed:
            raise ValueError(f"checkpoint_mode must be one of {allowed}, got '{v}'")
        return v

    @field_validator("screenshot_dir", "workflows_dir")
    @classmethod
    def ensure_dir_exists(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance — cached after first load."""
    return Settings()
