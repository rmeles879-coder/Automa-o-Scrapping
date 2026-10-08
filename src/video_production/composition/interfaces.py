"""Extensão futura; não executa FFmpeg nem renderiza vídeo nesta etapa."""

from typing import Protocol

from video_production.domain.models import CompositionRequest, VideoArtifact


class VideoComposer(Protocol):
    async def compose(self, request: CompositionRequest) -> VideoArtifact:
        """Compõe arquivos locais seguindo a ordem e duração das cenas do plano."""
        ...
