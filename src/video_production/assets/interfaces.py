"""Contratos para futuros providers locais ou remotos de assets."""

from pathlib import Path
from typing import Protocol

from video_production.domain.models import Asset, AssetQuery


class AssetProvider(Protocol):
    async def search(self, query: AssetQuery) -> tuple[Asset, ...]:
        """Retorna metadados, incluindo licença, sem baixar os arquivos."""
        ...

    async def download(self, asset: Asset, destination: Path) -> Path:
        """Salva o asset no caminho completo destination e retorna o caminho local."""
        ...
