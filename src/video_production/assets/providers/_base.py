"""HTTP compartilhado, normalização e gerenciamento de clientes/arquivos."""

import os
import tempfile
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from video_production.assets.errors import (
    AssetDownloadError,
    ProviderConfigurationError,
    ProviderHTTPError,
    ProviderNetworkError,
    ProviderResponseError,
    UnsupportedMediaTypeError,
)
from video_production.config import Settings
from video_production.domain.models import Asset, AssetKind, AssetQuery


def require_api_key(value: str | SecretStr | None, source: str, variable: str) -> str:
    raw = value.get_secret_value() if isinstance(value, SecretStr) else value
    if not raw or not raw.strip():
        raise ProviderConfigurationError(f"{source}: configure {variable}")
    return raw.strip()


def identifier(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError("Missing asset identifier")
    return str(value).strip()


def mapping(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    return value


def items(value: Any) -> list:
    if not isinstance(value, list):
        raise ValueError("Expected an array")
    return value


def http_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return None


def positive_int(value: Any) -> int | None:
    try:
        number = int(value)
        return number if number > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("p", "div", "li"):
            self.parts.append(" ")


def plain_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parser = _TextParser()
    parser.feed(value)
    return " ".join("".join(parser.parts).split()) or None


class HTTPAssetProvider:
    """Fecha apenas clientes próprios; clientes injetados pertencem ao chamador."""

    source: str
    supported_media: frozenset[AssetKind]

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ):
        config = settings if settings is not None else Settings()
        self._user_agent = config.user_agent
        self._owns_client = client is None
        self._client = (
            client
            if client is not None
            else httpx.AsyncClient(
                timeout=config.http_timeout_seconds,
                follow_redirects=True,
            )
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _check_kind(self, kind: AssetKind) -> None:
        if kind not in self.supported_media:
            raise UnsupportedMediaTypeError(f"{self.source}: unsupported media type {kind.value}")

    def _check_asset(self, asset: Asset) -> None:
        if asset.source != self.source:
            raise ProviderConfigurationError(f"{self.source}: asset belongs to a different source")
        self._check_kind(asset.media_type)

    def _check_status(self, response: httpx.Response) -> None:
        if not response.is_success:
            raise ProviderHTTPError(self.source, response.status_code)

    async def _json(self, url: str, *, params=None, headers=None) -> dict:
        try:
            response = await self._client.get(
                url,
                params=params,
                headers={"User-Agent": self._user_agent, **(headers or {})},
                follow_redirects=True,
            )
            self._check_status(response)
            return mapping(response.json())
        except httpx.RequestError:
            # A URL do Pixabay carrega uma chave; não encadear a exceção original.
            raise ProviderNetworkError(f"{self.source}: HTTP transport failed") from None
        except (ValueError, TypeError):
            raise ProviderResponseError(f"{self.source}: invalid JSON response") from None

    def _assets(
        self,
        raw_items: list,
        query: AssetQuery,
        normalize: Callable[[dict], Asset | None],
    ) -> tuple[Asset, ...]:
        result: list[Asset] = []
        seen: set[str] = set()
        try:
            for raw in raw_items:
                asset = normalize(mapping(raw))
                if asset is not None and asset.media_type == query.kind and asset.id not in seen:
                    result.append(asset)
                    seen.add(asset.id)
                if len(result) == query.limit:
                    break
        except (KeyError, ValueError, TypeError):
            raise ProviderResponseError(f"{self.source}: invalid asset metadata") from None
        return tuple(result)

    async def download(self, asset: Asset, destination: Path) -> Path:
        self._check_asset(asset)
        return await self._save(asset.download_url, destination)

    async def _save(self, url: str, destination: Path) -> Path:
        download_url = http_url(url)
        if download_url is None:
            raise ProviderResponseError(f"{self.source}: invalid download URL")
        destination = Path(destination)
        temporary: Path | None = None
        try:
            async with self._client.stream(
                "GET",
                download_url,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            ) as response:
                self._check_status(response)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent,
                    prefix=".asset-",
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    size = 0
                    async for chunk in response.aiter_bytes():
                        handle.write(chunk)
                        size += len(chunk)
                if not size:
                    raise AssetDownloadError(f"{self.source}: empty download")
                os.replace(temporary, destination)
                temporary = None
        except httpx.RequestError:
            raise ProviderNetworkError(f"{self.source}: download transport failed") from None
        except OSError:
            raise AssetDownloadError(f"{self.source}: could not save download") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return destination
