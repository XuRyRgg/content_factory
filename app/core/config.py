from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import AppError


class Settings(BaseSettings):
    app_name: str = Field(default="Content Factory", validation_alias="APP_NAME")
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    youtube_api_key: str | None = Field(default=None, validation_alias="YOUTUBE_API_KEY")
    session_secret_key: str | None = Field(default=None, validation_alias="SESSION_SECRET_KEY")
    session_https_only: bool = Field(default=False, validation_alias="SESSION_HTTPS_ONLY")
    database_url: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
    )
    google_client_id: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(
        default=None,
        validation_alias="GOOGLE_CLIENT_SECRET",
    )
    google_redirect_uri: str = Field(
        default="http://127.0.0.1:8000/api/auth/google/callback",
        validation_alias="GOOGLE_REDIRECT_URI",
    )
    lmstudio_base_url: str = Field(
        default="http://127.0.0.1:1234/v1",
        validation_alias="LMSTUDIO_BASE_URL",
    )
    lmstudio_model: str = Field(default="auto", validation_alias="LMSTUDIO_MODEL")
    lmstudio_max_tokens: int = Field(default=4096, validation_alias="LMSTUDIO_MAX_TOKENS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def require_youtube_api_key(self) -> str:
        if not self.youtube_api_key:
            raise AppError(
                status_code=500,
                code="youtube_api_key_missing",
                message="YOUTUBE_API_KEY is missing. Add it to .env.",
            )
        return self.youtube_api_key

    def require_google_oauth_credentials(self) -> tuple[str, str, str]:
        if not self.google_client_id or not self.google_client_secret:
            raise AppError(
                status_code=500,
                code="google_oauth_credentials_missing",
                message="GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are missing. Add them to .env.",
            )
        return self.google_client_id, self.google_client_secret, self.google_redirect_uri

    def require_session_secret_key(self) -> str:
        if not self.session_secret_key:
            raise RuntimeError("SESSION_SECRET_KEY is missing. Add it to .env.")
        return self.session_secret_key

    def require_database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is missing. Add PostgreSQL connection URL to .env.")
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
