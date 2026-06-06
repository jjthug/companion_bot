from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_cloud_project: str
    google_application_credentials: str
    gemini_api_key: str
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    session_ttl_seconds: int = 14_400
    summary_ttl_seconds: int = 86_400
    tts_voice: str = "en-US-Journey-F"
    tts_audio_encoding: str = "MP3"
    llm_model: str
    llm_max_tokens: int
    llm_temperature: float = 0.25
    log_level: str = "INFO"

    otlp_endpoint: str
    otlp_insecure: bool

    postgres_pooler_url: str

    redis_url: str

    service_name: str = "companion-backend"

    default_daily_limit_seconds: int = 1800
    quota_warning_threshold_seconds: int = 120
    quota_tick_interval_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str

settings = Settings()
