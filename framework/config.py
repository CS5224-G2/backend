from typing import Any
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
    # MongoDB Cluster
    MONGODB_URL: str = "mongodb://localhost:27017"

    # Redis / ElastiCache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_SSL: bool = False

    # --- Auth ---
    # Generate with: openssl rand -hex 32
    SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_REMEMBER_ME_DAYS: int = 30
    RATE_LIMIT_LOGIN: str = "10/minute"

    # --- CORS ---
    # Using Any type to prevent Pydantic V2 from trying to parse comma-separated strings as JSON.
    ALLOWED_ORIGINS: Any = ["*"]

    # --- Swagger Settings ---
    SWAGGER_USERNAME: str = "admin"
    SWAGGER_PASSWORD: str = "changeme"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: Any) -> list[str]:
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

    # --- AWS ---
    AWS_REGION: str = "ap-southeast-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_USER_BUCKET: str = "cyclelink-user-content"
    CDN_BASE_URL: str = ""           # e.g. https://cdn.cyclelink.example.com — avatar URLs use this if set

    # --- S3 / Pre-downloaded OSM Graph ---
    S3_BUCKET_NAME: str = ""
    OSM_GRAPH_S3_KEY: str = "osm-graphs/singapore_bike_graph.graphml"
    OSM_GRAPH_LOCAL_PATH: str = ""  # Set for local dev (overrides S3)
    OSM_TREES_S3_KEY: str = "osm-graphs/singapore_trees.json"
    OSM_TREES_LOCAL_PATH: str = ""  # Set for local dev (overrides S3)

    # --- GPX export ---
    SAVE_GPX: bool = False


settings = Settings()
