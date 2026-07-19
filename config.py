from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import field_validator

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    FAN_AUTH_TOKEN: str
    VOLUNTEER_AUTH_TOKEN: str
    STAFF_AUTH_TOKEN: str
    ENVIRONMENT: str = "production"
    MAX_TOKENS: int = 500
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8080"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()  # type: ignore[call-arg]

