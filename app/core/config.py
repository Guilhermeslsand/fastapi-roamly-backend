from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Roamly"
    app_env: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    app_timezone: str = "America/Sao_Paulo"


    database_url: str
    database_url_async: str
    redis_url: str = "redis://localhost:6379/0"
    # cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    cors_origins: list[str] = ["*"]

    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "travel-api"
    jwt_audience: str = "travel-api-client"
    access_token_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_days: int = Field(default=7, gt=0, le=90)

    rate_limit_general_per_minute: int = Field(default=120, gt=0)
    rate_limit_login_per_minute: int = Field(default=5, gt=0)
    rate_limit_register_per_minute: int = Field(default=5, gt=0)
    rate_limit_refresh_per_minute: int = Field(default=10, gt=0)

    destinations_cache_ttl_seconds: int = Field(default=120, gt=0, le=3600)
    packages_cache_ttl_seconds: int = Field(default=45, gt=0, le=3600)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_decoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()