"""Configuração explícita; importação não faz chamadas de rede."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Carrega argumentos > ambiente > .env > padrões ao ser instanciada."""

    model_config = SettingsConfigDict(
        env_prefix="VIDEO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    output_dir: Path = Path("output")
    cache_dir: Path = Path(".cache/video-production")
    http_timeout_seconds: float = Field(default=30, gt=0, allow_inf_nan=False)
    user_agent: str = Field(
        default=("Automa-o-Scrapping/0.2 (+https://github.com/rmeles879-coder/Automa-o-Scrapping)"),
        min_length=1,
    )
    pixabay_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="PIXABAY_API_KEY",
        repr=False,
        exclude=True,
    )
    unsplash_access_key: SecretStr | None = Field(
        default=None,
        validation_alias="UNSPLASH_ACCESS_KEY",
        repr=False,
        exclude=True,
    )

    @field_validator("pixabay_api_key", "unsplash_access_key", mode="before")
    @classmethod
    def empty_credentials_are_absent(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("user_agent")
    @classmethod
    def non_blank_user_agent(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("User-Agent must not be blank")
        return value.strip()
