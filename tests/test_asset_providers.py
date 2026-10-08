"""Busca, normalização, autenticação e falhas com HTTP completamente simulado."""

import unittest

import httpx
from provider_fixtures import (
    PIXABAY_TEST_KEY,
    UNSPLASH_TEST_KEY,
    commons_page,
    config,
    pixabay_image,
    pixabay_video,
    unsplash_photo,
)

from video_production.assets import PixabayProvider, UnsplashProvider, WikimediaCommonsProvider
from video_production.assets.errors import (
    ProviderConfigurationError,
    ProviderHTTPError,
    ProviderNetworkError,
    ProviderResponseError,
    UnsupportedMediaTypeError,
)
from video_production.domain.models import AssetKind, AssetQuery


def providers(client):
    return (
        PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config()),
        UnsplashProvider(UNSPLASH_TEST_KEY, client=client, settings=config()),
        WikimediaCommonsProvider(client=client, settings=config()),
    )


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_pixabay_normalizes_images_and_uses_query_key(self):
        def handler(request):
            self.assertEqual(str(request.url).split("?")[0], "https://pixabay.com/api/")
            self.assertEqual(request.url.params["key"], PIXABAY_TEST_KEY)
            self.assertEqual(request.url.params["q"], "forest & trees")
            self.assertEqual(request.url.params["per_page"], "3")
            self.assertNotIn("authorization", request.headers)
            return httpx.Response(200, json={"hits": [pixabay_image(), pixabay_image(102)]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config())
            assets = await provider.search(AssetQuery(query="forest & trees", limit=1))
        self.assertEqual(len(assets), 1)
        asset = assets[0]
        self.assertEqual((asset.id, asset.source, asset.media_type), ("101", "pixabay", "image"))
        self.assertEqual(asset.tags, ("forest", "nature"))
        self.assertEqual(asset.title, "forest, nature")
        self.assertEqual(asset.description, "forest, nature")
        self.assertEqual(asset.author, "Example Photographer")
        self.assertEqual((asset.width, asset.height), (4000, 3000))
        self.assertEqual(asset.download_url, "https://cdn.pixabay.com/photo/forest.jpg")
        self.assertEqual(str(asset.thumbnail_url), "https://cdn.pixabay.com/photo/forest-small.jpg")
        self.assertEqual(str(asset.source_page_url), "https://pixabay.com/photos/forest-101/")
        self.assertEqual(asset.license.name, "Pixabay Content License")
        self.assertEqual(asset.provider, asset.source)
        self.assertEqual(asset.kind, asset.media_type)
        self.assertEqual(asset.uri, asset.download_url)

    async def test_pixabay_video_selects_largest_available_variant(self):
        def handler(request):
            self.assertEqual(request.url.path, "/api/videos/")
            return httpx.Response(200, json={"hits": [pixabay_video()]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config())
            assets = await provider.search(AssetQuery(query="forest", kind="video"))
        asset = assets[0]
        self.assertEqual(asset.media_type, AssetKind.VIDEO)
        self.assertEqual((asset.width, asset.height, asset.duration_seconds), (1920, 1080, 12))
        self.assertTrue(asset.download_url.endswith("forest-large.mp4"))
        self.assertTrue(str(asset.thumbnail_url).endswith("forest.jpg"))

    async def test_unsplash_normalizes_fields_and_uses_authorization_header(self):
        def handler(request):
            self.assertEqual(request.url.host, "api.unsplash.com")
            self.assertEqual(request.url.path, "/search/photos")
            self.assertEqual(request.headers["Authorization"], f"Client-ID {UNSPLASH_TEST_KEY}")
            self.assertEqual(request.headers["Accept-Version"], "v1")
            self.assertNotIn("client_id", request.url.params)
            return httpx.Response(200, json={"results": [unsplash_photo()], "total_pages": 1})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = UnsplashProvider(UNSPLASH_TEST_KEY, client=client, settings=config())
            assets = await provider.search(AssetQuery(query="forest"))
        asset = assets[0]
        self.assertEqual(asset.source, "unsplash")
        self.assertEqual(asset.id, "photo-1")
        self.assertEqual(asset.media_type, AssetKind.IMAGE)
        self.assertEqual(asset.title, "Forest at sunrise")
        self.assertEqual(asset.description, "Forest at sunrise")
        self.assertEqual(asset.tags, ("forest", "nature"))
        self.assertEqual(asset.author, "Example Photographer")
        self.assertEqual((asset.width, asset.height), (6000, 4000))
        self.assertEqual(asset.license.name, "Unsplash License")
        self.assertIn("Example Photographer", asset.license.attribution)
        self.assertEqual(asset.download_url, "https://images.unsplash.com/photo-1?ixid=example")
        self.assertTrue(str(asset.download_tracking_url).startswith("https://api.unsplash.com/"))
        self.assertTrue(str(asset.source_page_url).startswith("https://unsplash.com/"))

    async def test_unsplash_paginates_for_limits_above_thirty(self):
        requested_pages = []

        def handler(request):
            self.assertEqual(request.url.params["per_page"], "30")
            page = int(request.url.params["page"])
            requested_pages.append(page)
            start = (page - 1) * 30
            return httpx.Response(
                200,
                json={
                    "results": [
                        unsplash_photo(f"photo-{number}") for number in range(start, start + 30)
                    ],
                    "total_pages": 2,
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = UnsplashProvider(UNSPLASH_TEST_KEY, client=client, settings=config())
            result = await provider.search(AssetQuery(query="forest", limit=35))
        self.assertEqual(len(result), 35)
        self.assertEqual(requested_pages, [1, 2])
        self.assertEqual(len({asset.id for asset in result}), 35)

    async def test_commons_normalizes_html_license_and_orders_by_search_rank(self):
        def handler(request):
            self.assertEqual(request.url.host, "commons.wikimedia.org")
            self.assertEqual(request.url.params["gsrnamespace"], "6")
            self.assertEqual(request.url.params["formatversion"], "2")
            self.assertIn("extmetadata", request.url.params["iiprop"])
            self.assertEqual(request.headers["User-Agent"], "VideoTest/1 (+https://example.org)")
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("key", request.url.params)
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": [
                            commons_page(304, index=2),
                            commons_page(303, index=1),
                        ]
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = WikimediaCommonsProvider(
                client=client,
                settings=config(),
                user_agent="VideoTest/1 (+https://example.org)",
            )
            result = await provider.search(AssetQuery(query="forest", limit=2))
        self.assertEqual([asset.id for asset in result], ["303", "304"])
        asset = result[0]
        self.assertEqual(asset.source, "wikimedia_commons")
        self.assertEqual(asset.title, "Forest & trees")
        self.assertEqual(asset.description, "Morning in the forest.")
        self.assertEqual(asset.author, "Example Author")
        self.assertEqual(asset.tags, ("Forests", "Nature"))
        self.assertEqual(asset.license.name, "CC BY-SA 4.0")
        self.assertEqual(
            str(asset.license.source_url),
            "https://creativecommons.org/licenses/by-sa/4.0/",
        )
        self.assertEqual(asset.license.attribution, "Example Author; Own work")
        self.assertEqual((asset.width, asset.height), (3200, 2400))
        self.assertIsNotNone(asset.thumbnail_url)
        self.assertIsNotNone(asset.source_page_url)

    async def test_commons_continuation_filters_media_and_deduplicates(self):
        requested_offsets = []

        def handler(request):
            offset = request.url.params.get("gsroffset")
            requested_offsets.append(offset)
            if offset is None:
                return httpx.Response(
                    200,
                    json={
                        "query": {
                            "pages": [commons_page(1, mime="application/pdf"), commons_page(2)]
                        },
                        "continue": {"gsroffset": 2, "continue": "gsroffset||"},
                    },
                )
            return httpx.Response(
                200,
                json={"query": {"pages": [commons_page(2), commons_page(3)]}},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = WikimediaCommonsProvider(client=client, settings=config())
            assets = await provider.search(AssetQuery(query="forest", limit=2))
        self.assertEqual([asset.id for asset in assets], ["2", "3"])
        self.assertEqual(requested_offsets, [None, "2"])

    async def test_commons_supports_video_and_audio_without_assuming_image(self):
        for kind in (AssetKind.VIDEO, AssetKind.AUDIO):
            with self.subTest(kind=kind):
                raw = commons_page(mime="application/ogg")
                raw["imageinfo"][0]["mediatype"] = kind.value.upper()
                raw["imageinfo"][0].pop("width")
                raw["imageinfo"][0].pop("height")
                transport = httpx.MockTransport(
                    lambda request, raw=raw: httpx.Response(200, json={"query": {"pages": [raw]}})
                )
                async with httpx.AsyncClient(transport=transport) as client:
                    provider = WikimediaCommonsProvider(client=client, settings=config())
                    assets = await provider.search(AssetQuery(query="forest", kind=kind))
                self.assertEqual(assets[0].media_type, kind)
                self.assertIsNone(assets[0].width)
                self.assertIsNone(assets[0].height)

    async def test_commons_preserves_unknown_license_when_metadata_is_absent(self):
        raw = commons_page()
        raw["imageinfo"][0].pop("extmetadata")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request, raw=raw: httpx.Response(200, json={"query": {"pages": [raw]}})
            )
        ) as client:
            result = await WikimediaCommonsProvider(client=client, settings=config()).search(
                AssetQuery(query="forest")
            )
        self.assertEqual(result[0].license.name, "Unknown")
        self.assertIsNone(result[0].license.source_url)
        self.assertEqual(result[0].title, "Forest.jpg")
        self.assertEqual(result[0].tags, ())

    async def test_searches_with_no_results_return_empty_tuples(self):
        payloads = {
            "pixabay.com": {"hits": []},
            "api.unsplash.com": {"results": []},
            "commons.wikimedia.org": {"batchcomplete": True},
        }
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payloads[request.url.host])
            )
        ) as client:
            for provider in providers(client):
                with self.subTest(provider=provider.source):
                    self.assertEqual(await provider.search(AssetQuery(query="no results")), ())

    async def test_missing_urls_are_skipped_and_optional_metadata_may_be_absent(self):
        raw = unsplash_photo()
        raw.update(description=None, alt_description=None, tags=None, width=0, height=None)
        raw["user"] = {}
        missing = unsplash_photo("missing")
        missing["urls"] = {}
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"results": [missing, raw]})
            )
        ) as client:
            result = await UnsplashProvider(
                UNSPLASH_TEST_KEY,
                client=client,
                settings=config(),
            ).search(AssetQuery(query="forest"))
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].author)
        self.assertIsNone(result[0].width)
        self.assertEqual(result[0].tags, ())

    async def test_unsupported_media_and_missing_credentials_fail_before_http(self):
        def handler(request):
            self.fail("HTTP should not be called")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for provider, kind in (
                (providers(client)[0], AssetKind.AUDIO),
                (providers(client)[1], AssetKind.VIDEO),
            ):
                with self.assertRaises(UnsupportedMediaTypeError):
                    await provider.search(AssetQuery(query="forest", kind=kind))
            with self.assertRaises(ProviderConfigurationError):
                PixabayProvider(client=client, settings=config())
            with self.assertRaises(ProviderConfigurationError):
                UnsplashProvider(client=client, settings=config())
            with self.assertRaises(ProviderConfigurationError):
                WikimediaCommonsProvider(client=client, settings=config(), user_agent="  ")

    async def test_http_status_errors_are_safe_for_all_providers(self):
        for status in (401, 429, 500):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request, status=status: httpx.Response(
                        status, text=PIXABAY_TEST_KEY + UNSPLASH_TEST_KEY
                    )
                )
            ) as client:
                for provider in providers(client):
                    with self.subTest(status=status, provider=provider.source):
                        with self.assertRaises(ProviderHTTPError) as caught:
                            await provider.search(AssetQuery(query="forest"))
                        self.assertEqual(caught.exception.status_code, status)
                        self.assertNotIn(PIXABAY_TEST_KEY, str(caught.exception))
                        self.assertNotIn(UNSPLASH_TEST_KEY, str(caught.exception))

    async def test_timeout_messages_do_not_expose_request_urls_or_credentials(self):
        def handler(request):
            raise httpx.ReadTimeout(str(request.url) + UNSPLASH_TEST_KEY, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for provider in providers(client):
                with self.subTest(provider=provider.source):
                    with self.assertRaises(ProviderNetworkError) as caught:
                        await provider.search(AssetQuery(query="forest"))
                    self.assertNotIn(PIXABAY_TEST_KEY, str(caught.exception))
                    self.assertNotIn(UNSPLASH_TEST_KEY, str(caught.exception))
                    self.assertTrue(caught.exception.__suppress_context__)

    async def test_invalid_json_and_invalid_root_raise_response_errors(self):
        for response in (httpx.Response(200, content=b"not JSON"), httpx.Response(200, json=[])):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request, response=response: response)
            ) as client:
                for provider in providers(client):
                    with self.subTest(provider=provider.source):
                        with self.assertRaises(ProviderResponseError):
                            await provider.search(AssetQuery(query="forest"))

    async def test_malformed_metadata_is_not_silently_accepted(self):
        raw = pixabay_image()
        raw["id"] = None
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"hits": [raw]}))
        ) as client:
            with self.assertRaises(ProviderResponseError):
                await PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config()).search(
                    AssetQuery(query="forest")
                )

    async def test_mediawiki_api_errors_are_detected_even_with_http_200(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"error": {"code": "badvalue"}})
            )
        ) as client:
            with self.assertRaises(ProviderResponseError):
                await WikimediaCommonsProvider(client=client, settings=config()).search(
                    AssetQuery(query="forest")
                )

    async def test_client_lifecycle_respects_ownership(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
        ) as client:
            async with WikimediaCommonsProvider(client=client, settings=config()):
                pass
            self.assertFalse(client.is_closed)
        provider = WikimediaCommonsProvider(settings=config())
        await provider.aclose()
        self.assertTrue(provider._client.is_closed)
