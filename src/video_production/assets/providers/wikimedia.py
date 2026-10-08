"""MediaWiki Action API para arquivos do Commons; não usa credenciais."""

import httpx

from video_production.assets.errors import ProviderConfigurationError, ProviderResponseError
from video_production.config import Settings
from video_production.domain.models import Asset, AssetKind, AssetLicense, AssetQuery

from ._base import HTTPAssetProvider, http_url, identifier, items, mapping, plain_text, positive_int


class WikimediaCommonsProvider(HTTPAssetProvider):
    source = "wikimedia_commons"
    supported_media = frozenset(AssetKind)

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ):
        if user_agent is not None and not user_agent.strip():
            raise ProviderConfigurationError("wikimedia_commons: User-Agent must not be blank")
        super().__init__(client=client, settings=settings)
        if user_agent is not None:
            self._user_agent = user_agent.strip()

    async def search(self, query: AssetQuery) -> tuple[Asset, ...]:
        self._check_kind(query.kind)
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": query.query,
            "gsrnamespace": 6,
            "gsrlimit": min(query.limit, 50),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|mediatype|extmetadata",
            "iiurlwidth": 320,
        }
        result: list[Asset] = []
        seen: set[str] = set()
        seen_cursors: set[str] = set()
        for _ in range(4):
            payload = await self._json("https://commons.wikimedia.org/w/api.php", params=params)
            if "error" in payload or "errors" in payload:
                raise ProviderResponseError("wikimedia_commons: MediaWiki API error")
            try:
                pages = items(mapping(payload.get("query", {})).get("pages", []))
                pages = sorted(pages, key=lambda page: mapping(page).get("index", 0))
                continuation = mapping(payload.get("continue", {}))
            except (ValueError, TypeError):
                raise ProviderResponseError("wikimedia_commons: invalid pages response") from None
            for asset in self._assets(pages, query, self._normalize):
                if asset.id not in seen:
                    result.append(asset)
                    seen.add(asset.id)
            cursor = str(continuation)
            if len(result) >= query.limit or not continuation or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
            params.update(
                {
                    key: value
                    for key, value in continuation.items()
                    if key in ("continue", "gsroffset")
                }
            )
        return tuple(result[: query.limit])

    def _normalize(self, page: dict) -> Asset | None:
        infos = items(page.get("imageinfo", []))
        if not infos:
            return None
        info = mapping(infos[0])
        url = http_url(info.get("url"))
        if not url:
            return None
        mime = info.get("mime") or ""
        if not isinstance(mime, str):
            raise ValueError("Invalid MIME type")
        kind = next((kind for kind in AssetKind if mime.startswith(kind.value + "/")), None)
        if kind is None:
            kind = {
                "BITMAP": AssetKind.IMAGE,
                "DRAWING": AssetKind.IMAGE,
                "VIDEO": AssetKind.VIDEO,
                "AUDIO": AssetKind.AUDIO,
            }.get(info.get("mediatype"))
        if kind is None:
            return None
        metadata = mapping(info.get("extmetadata", {}))

        def text(name: str) -> str | None:
            return plain_text(mapping(metadata.get(name, {})).get("value"))

        name = page.get("title", "").removeprefix("File:")
        author = text("Artist")
        attribution = (
            text("Attribution")
            or "; ".join(part for part in (author, text("Credit")) if part)
            or None
        )
        categories = text("Categories") or ""
        tags = tuple(dict.fromkeys(tag.strip() for tag in categories.split("|") if tag.strip()))
        return Asset(
            id=identifier(page["pageid"]),
            source=self.source,
            media_type=kind,
            download_url=url,
            title=text("ObjectName") or name or f"Commons {page['pageid']}",
            description=text("ImageDescription"),
            tags=tags,
            thumbnail_url=http_url(info.get("thumburl")),
            source_page_url=http_url(info.get("descriptionurl")),
            author=author,
            license=AssetLicense(
                name=text("LicenseShortName") or text("UsageTerms") or "Unknown",
                source_url=http_url(text("LicenseUrl")),
                attribution=attribution,
            ),
            width=positive_int(info.get("width")),
            height=positive_int(info.get("height")),
        )
