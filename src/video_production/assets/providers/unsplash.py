"""Provider de imagens Unsplash com rastreamento de download obrigatório."""

from pathlib import Path
from urllib.parse import quote, urlsplit

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


class UnsplashProvider(HTTPAssetProvider):
    source = "unsplash"
    supported_media = frozenset((AssetKind.IMAGE,))

    def __init__(
        self,
        access_key: str | SecretStr | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ):
        config = settings if settings is not None else Settings()
        self._access_key = require_api_key(
            access_key if access_key is not None else config.unsplash_access_key,
            self.source,
            "UNSPLASH_ACCESS_KEY",
        )
        super().__init__(client=client, settings=config)

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Client-ID {self._access_key}", "Accept-Version": "v1"}

    async def search(self, query: AssetQuery) -> tuple[Asset, ...]:
        self._check_kind(query.kind)
        result: list[Asset] = []
        seen: set[str] = set()
        page = 1
        while len(result) < query.limit:
            payload = await self._json(
                "https://api.unsplash.com/search/photos",
                headers=self._headers,
                params={"query": query.query, "per_page": min(query.limit, 30), "page": page},
            )
            try:
                photos = items(payload["results"])
                total_pages = int(payload.get("total_pages", 1))
            except (KeyError, ValueError, TypeError):
                raise ProviderResponseError("unsplash: invalid search response") from None
            batch = self._assets(photos, query, self._normalize)
            for asset in batch:
                if asset.id not in seen:
                    result.append(asset)
                    seen.add(asset.id)
            if not photos or page >= total_pages or page >= 4:
                break
            page += 1
        return tuple(result[: query.limit])

    def _normalize(self, photo: dict) -> Asset | None:
        urls = mapping(photo.get("urls", {}))
        links = mapping(photo.get("links", {}))
        user = mapping(photo.get("user", {}))
        url = http_url(urls.get("full")) or http_url(urls.get("regular"))
        if url is None:
            return None
        tags = tuple(
            dict.fromkeys(
                tag
                for raw in items(photo.get("tags") or [])
                if (tag := plain_text(mapping(raw).get("title")))
            )
        )
        description = plain_text(photo.get("description"))
        alt = plain_text(photo.get("alt_description"))
        author = plain_text(user.get("name")) or plain_text(user.get("username"))
        return Asset(
            id=identifier(photo["id"]),
            source=self.source,
            media_type=AssetKind.IMAGE,
            title=alt or description or f"Unsplash {photo['id']}",
            description=description or alt,
            tags=tags,
            download_url=url,
            thumbnail_url=http_url(urls.get("thumb")) or http_url(urls.get("small")),
            source_page_url=http_url(links.get("html")),
            author=author,
            license=AssetLicense(
                name="Unsplash License",
                source_url="https://unsplash.com/license",
                attribution=f"Photo by {author} on Unsplash" if author else None,
            ),
            width=positive_int(photo.get("width")),
            height=positive_int(photo.get("height")),
            download_tracking_url=http_url(links.get("download_location")),
        )

    async def download(self, asset: Asset, destination: Path) -> Path:
        self._check_asset(asset)
        tracking_url = (
            str(asset.download_tracking_url)
            if asset.download_tracking_url
            else (f"https://api.unsplash.com/photos/{quote(asset.id, safe='')}/download")
        )
        parsed = urlsplit(tracking_url)
        if parsed.scheme != "https" or parsed.hostname != "api.unsplash.com" or parsed.username:
            raise ProviderResponseError("unsplash: invalid download tracking endpoint")
        payload = await self._json(tracking_url, headers=self._headers)
        url = http_url(payload.get("url"))
        if url is None:
            raise ProviderResponseError("unsplash: missing tracked download URL")
        return await self._save(url, destination)
