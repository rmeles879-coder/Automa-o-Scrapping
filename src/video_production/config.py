"""Configuração explícita, sem chamadas de rede ou criação de diretórios."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Carrega valores explícitos > ambiente > .env > padrões ao ser instanciada."""

    model_config = SettingsConfigDict(
        env_prefix="VIDEO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    output_dir: Path = Path("output")
    cache_dir: Path = Path(".cache/video-production")
