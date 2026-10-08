"""Contrato sem dependência de SDKs ou fornecedores."""

from typing import Protocol

from video_production.domain.models import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Produz uma resposta textual; parsing do domínio cabe ao consumidor."""
        ...
