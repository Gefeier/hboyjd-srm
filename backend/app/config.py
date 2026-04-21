from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "欧阳聚德 SRM API"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "replace-me-in-production"
    access_token_expire_minutes: int = 480
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/hboyjd_srm"
    redis_url: str = "redis://localhost:6379/0"
    # 存成逗号分隔字符串,避开pydantic-settings 2.x对list[str]的JSON强制解析
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    auto_create_tables: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
