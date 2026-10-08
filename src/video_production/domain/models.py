"""Dados que atravessam as fronteiras dos módulos."""

from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

NonEmptyText = Annotated[str, Field(min_length=1)]
PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class DomainModel(BaseModel):
    """Modelos imutáveis, serializáveis e com campos desconhecidos rejeitados."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AssetQuery(DomainModel):
    query: NonEmptyText
    kind: AssetKind = AssetKind.IMAGE
    limit: int = Field(default=10, gt=0, le=100)


class AssetLicense(DomainModel):
    """Metadados de licença; não representam autorização automática de uso."""

    name: NonEmptyText
    source_url: HttpUrl | None = None
    attribution: str | None = None


class Asset(DomainModel):
    id: NonEmptyText
    provider: NonEmptyText
    kind: AssetKind
    uri: NonEmptyText
    license: AssetLicense
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_seconds: PositiveSeconds | None = None


class VisualReference(DomainModel):
    """Entrada local; o modelo não abre nem baixa o arquivo."""

    id: NonEmptyText
    path: Path


class ReferenceAnalysis(DomainModel):
    reference_id: NonEmptyText
    summary: NonEmptyText
    style: str = ""
    palette: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


class VideoSpec(DomainModel):
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: int = Field(default=30, gt=0)


class VideoBrief(DomainModel):
    title: NonEmptyText
    script: NonEmptyText
    target_duration_seconds: PositiveSeconds
    spec: VideoSpec = Field(default_factory=VideoSpec)


class ScenePlan(DomainModel):
    id: NonEmptyText
    duration_seconds: PositiveSeconds
    visual_description: NonEmptyText
    narration: str = ""
    asset_queries: tuple[AssetQuery, ...] = ()


class VisualPlan(DomainModel):
    """A ordem das cenas define uma timeline sequencial, sem sobreposições."""

    spec: VideoSpec = Field(default_factory=VideoSpec)
    scenes: tuple[ScenePlan, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_scene_ids(self) -> Self:
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("Scene IDs must be unique")
        return self

    @property
    def duration_seconds(self) -> float:
        return sum(scene.duration_seconds for scene in self.scenes)


class LLMMessage(DomainModel):
    role: Literal["system", "user", "assistant"]
    content: NonEmptyText


class LLMRequest(DomainModel):
    messages: tuple[LLMMessage, ...] = Field(min_length=1)
    model: NonEmptyText | None = None
    temperature: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    max_tokens: int = Field(default=1024, gt=0)


class LLMResponse(DomainModel):
    text: NonEmptyText
    model: NonEmptyText
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class NarrationRequest(DomainModel):
    text: NonEmptyText
    language: NonEmptyText
    voice: NonEmptyText | None = None


class AudioTrack(DomainModel):
    path: Path
    duration_seconds: PositiveSeconds


class SceneMedia(DomainModel):
    scene_id: NonEmptyText
    asset: Asset
    local_path: Path


class CompositionRequest(DomainModel):
    plan: VisualPlan
    media: tuple[SceneMedia, ...] = ()
    narration: AudioTrack | None = None
    output_path: Path

    @model_validator(mode="after")
    def validate_media_scene_ids(self) -> Self:
        scene_ids = {scene.id for scene in self.plan.scenes}
        media_ids = [item.scene_id for item in self.media]
        if any(scene_id not in scene_ids for scene_id in media_ids):
            raise ValueError("Media must reference a scene in the plan")
        if len(media_ids) != len(set(media_ids)):
            raise ValueError("Only one media entry per scene is supported")
        return self


class VideoArtifact(DomainModel):
    path: Path
    duration_seconds: PositiveSeconds
    spec: VideoSpec
