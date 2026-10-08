"""Smoke test opt-in: pesquisa real, sem imprimir URLs autenticadas ou segredos."""

import argparse
import asyncio
import json

from video_production.assets import PixabayProvider, UnsplashProvider, WikimediaCommonsProvider
from video_production.assets.errors import (
    AssetProviderError,
    ProviderConfigurationError,
    ProviderHTTPError,
    ProviderNetworkError,
)
from video_production.config import Settings
from video_production.domain.models import AssetKind, AssetQuery


async def check(factory, source: str, kind: AssetKind, query: str, settings: Settings) -> dict:
    result = {"source": source, "media_type": kind.value}
    try:
        async with factory(settings=settings) as provider:
            assets = await provider.search(AssetQuery(query=query, kind=kind, limit=1))
        result.update(status="ok", count=len(assets))
        if assets:
            result["sample"] = {
                "id": assets[0].id,
                "license": assets[0].license.name,
                "width": assets[0].width,
                "height": assets[0].height,
            }
    except ProviderConfigurationError:
        result["status"] = "skipped_missing_configuration"
    except ProviderNetworkError:
        result["status"] = "unavailable_network"
    except ProviderHTTPError as error:
        result.update(status="failed_http", status_code=error.status_code)
    except AssetProviderError:
        result["status"] = "failed_response"
    return result


async def main(query: str) -> int:
    settings = Settings()
    results = await asyncio.gather(
        check(PixabayProvider, "pixabay", AssetKind.IMAGE, query, settings),
        check(PixabayProvider, "pixabay", AssetKind.VIDEO, query, settings),
        check(UnsplashProvider, "unsplash", AssetKind.IMAGE, query, settings),
        check(WikimediaCommonsProvider, "wikimedia_commons", AssetKind.IMAGE, query, settings),
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(result["status"].startswith("failed") for result in results):
        return 1
    if any(result["status"] == "unavailable_network" for result in results):
        return 2
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="nature")
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.query)))
