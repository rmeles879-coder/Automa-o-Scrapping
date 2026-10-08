"""Planejamento recebe dados do domínio, sem acoplamento aos providers."""

from typing import Protocol

from video_production.domain.models import ReferenceAnalysis, VideoBrief, VisualPlan


class VisualPlanner(Protocol):
    async def plan(
        self,
        brief: VideoBrief,
        references: tuple[ReferenceAnalysis, ...] = (),
    ) -> VisualPlan:
        """Transforma o roteiro e análises em cenas; não baixa nem compõe vídeo."""
        ...
