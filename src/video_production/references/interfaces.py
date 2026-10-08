"""Contrato para análise futura de imagens ou vídeos locais."""

from typing import Protocol

from video_production.domain.models import ReferenceAnalysis, VisualReference


class ReferenceAnalyzer(Protocol):
    async def analyze(self, reference: VisualReference) -> ReferenceAnalysis:
        """Descreve estilo e conteúdo preservando o identificador da referência."""
        ...
