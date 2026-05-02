"""
Central application configuration via pydantic-settings.
All values can be overridden with environment variables or a .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────
    # Default to 'db' for docker-compose, but overrideable via .env
    DATABASE_URL: str = "mysql+pymysql://root:12345678@db:3306/mark1_db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v):
        if isinstance(v, str) and v.startswith("mysql://"):
            return v.replace("mysql://", "mysql+pymysql://", 1)
        return v


    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_TO_A_RANDOM_SECRET_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours

    # ── CORS ──────────────────────────────────────────────────
    # Can be a comma-separated string in .env (e.g., "http://localhost:8000,http://example.com")
    # Use "*" to allow all origins.
    CORS_ORIGINS: str = "*"



    # ── Email ─────────────────────────────────────────────────
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "era3arc1@gmail.com"
    SMTP_PASSWORD: str = ""  # Should be set in .env

    # ── OpenRouter AI ─────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-lite-preview-02-05:free"

    # ── Razorpay ──────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True
    )



settings = Settings()
