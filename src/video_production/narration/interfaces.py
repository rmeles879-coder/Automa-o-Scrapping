"""Extensão futura; nenhuma síntese de áudio é implementada nesta etapa."""

from pathlib import Path
from typing import Protocol

from video_production.domain.models import AudioTrack, NarrationRequest


class NarrationProvider(Protocol):
    async def synthesize(self, request: NarrationRequest, destination: Path) -> AudioTrack:
        """Gera áudio no caminho completo destination e retorna seus metadados."""
        ...
