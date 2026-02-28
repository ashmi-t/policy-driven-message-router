"""Application configuration from environment."""
import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings with env var support."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/message_router"
    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    # Twilio (SMS)
    twilio_account_sid: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from_number: Optional[str] = os.getenv("TWILIO_FROM_NUMBER")
    # Mailjet (Email)
    mailjet_api_key: Optional[str] = os.getenv("MAILJET_API_KEY")
    mailjet_api_secret: Optional[str] = os.getenv("MAILJET_API_SECRET")
    mailjet_from_email: str = os.getenv("MAILJET_FROM_EMAIL", "noreply@example.com")
    mailjet_from_name: str = os.getenv("MAILJET_FROM_NAME", "Message Router")
    # Retry / DLQ
    default_max_retries: int = 3
    dlq_max_retries: int = 5


settings = Settings()
