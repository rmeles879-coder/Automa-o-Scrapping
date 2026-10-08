"""Provider para APIs de imagens e vídeos do Pixabay."""

import httpx
from pydantic import SecretStr

from video_production.assets.errors import ProviderResponseError
from video_production.config import Settings
from video_production.domain.models import Asset, AssetKind, AssetLicense, AssetQuery

from ._base import (
    HTTPAssetProvider,
    http_url,
    identifier,
    items,
    mapping,
    plain_text,
    positive_int,
    require_api_key,
)


class PixabayProvider(HTTPAssetProvider):
    source = "pixabay"
    supported_media = frozenset((AssetKind.IMAGE, AssetKind.VIDEO))

    def __init__(
        self,
        api_key: str | SecretStr | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ):
        config = settings if settings is not None else Settings()
        self._api_key = require_api_key(
            api_key if api_key is not None else config.pixabay_api_key,
            self.source,
            "PIXABAY_API_KEY",
        )
        super().__init__(client=client, settings=config)

    async def search(self, query: AssetQuery) -> tuple[Asset, ...]:
        self._check_kind(query.kind)
        endpoint = "https://pixabay.com/api/"
        if query.kind == AssetKind.VIDEO:
            endpoint += "videos/"
        payload = await self._json(
            endpoint,
            params={
                "key": self._api_key,
                "q": query.query,
                "per_page": max(3, query.limit),
                "safesearch": "true",
            },
        )
        try:
            hits = items(payload["hits"])
        except (KeyError, ValueError):
            raise ProviderResponseError("pixabay: missing hits array") from None
        return self._assets(hits, query, lambda hit: self._normalize(hit, query.kind))

    def _normalize(self, hit: dict, kind: AssetKind) -> Asset | None:
        raw_tags = hit.get("tags") or ""
        if not isinstance(raw_tags, str):
            raise ValueError("Invalid tags")
        tags = tuple(dict.fromkeys(tag.strip() for tag in raw_tags.split(",") if tag.strip()))
        width, height = hit.get("imageWidth"), hit.get("imageHeight")
        thumbnail = http_url(hit.get("previewURL")) or http_url(hit.get("webformatURL"))
        duration = None
        if kind == AssetKind.VIDEO:
            variants = [
                mapping(value)
                for value in mapping(hit.get("videos", {})).values()
                if isinstance(value, dict) and http_url(value.get("url"))
            ]
            if not variants:
                return None
            video = max(variants, key=lambda value: positive_int(value.get("width")) or 0)
            url = http_url(video["url"])
            width, height = video.get("width"), video.get("height")
            thumbnail = thumbnail or http_url(video.get("thumbnail"))
            duration = hit.get("duration") or None
        else:
            url = next(
                (
                    url
                    for name in ("imageURL", "largeImageURL", "webformatURL", "previewURL")
                    if (url := http_url(hit.get(name)))
                ),
                None,
            )
        if url is None:
            return None
        return Asset(
            id=identifier(hit["id"]),
            source=self.source,
            media_type=kind,
            download_url=url,
            title=plain_text(hit.get("title")) or ", ".join(tags) or f"Pixabay {hit['id']}",
            description=plain_text(hit.get("description")) or ", ".join(tags) or None,
            tags=tags,
            thumbnail_url=thumbnail,
            source_page_url=http_url(hit.get("pageURL")),
            author=plain_text(hit.get("user")),
            license=AssetLicense(
                name="Pixabay Content License",
                source_url="https://pixabay.com/service/license-summary/",
            ),
            width=positive_int(width),
            height=positive_int(height),
            duration_seconds=duration,
        )
