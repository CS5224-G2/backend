from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"

    # --- Databases ---
    # Places DB (PostgreSQL + PostGIS)
    PLACES_DB_URL: str = "postgresql+asyncpg://postgres:dev@localhost:5432/CycleLink"

    # --- Auth ---
    # Generate with: openssl rand -hex 32
    SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- Microservice base URLs ---
    # Populated as services come online. Format: {"service_name": "http://host:port"}
    # Example: {"route_recommender": "http://route-svc:8001", "weather": "http://weather-svc:8002"}
    SERVICE_URLS: dict[str, str] = {}

    @field_validator("SERVICE_URLS", mode="before")
    @classmethod
    def parse_service_urls(cls, v: str | dict) -> dict[str, str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # --- External APIs ---
    NEA_API_KEY: str = ""
    NEA_BASE_URL: str = ""

    # --- AWS URLs (For later on) ---

    # --- GPX export ---
    SAVE_GPX: bool = False


settings = Settings()
