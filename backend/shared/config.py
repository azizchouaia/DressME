from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../infra/.env", extra="ignore")

    database_url: str = "postgresql+asyncpg://dressme:change_me@localhost:5432/dressme"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "dressme"
    llm_provider: str = "anthropic"
    llm_model: str = ""
    llm_api_key: str = ""
    weather_api_url: str = "https://api.open-meteo.com/v1/forecast"
    jwt_secret: str = "change_me"


settings = Settings()
