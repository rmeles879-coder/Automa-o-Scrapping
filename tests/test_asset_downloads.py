"""Downloads com HTTP simulado: rastreamento, gravação atômica e limpeza de falhas."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from provider_fixtures import PIXABAY_TEST_KEY, UNSPLASH_TEST_KEY, config

from video_production.assets import PixabayProvider, UnsplashProvider, WikimediaCommonsProvider
from video_production.assets.errors import (
    AssetDownloadError,
    ProviderConfigurationError,
    ProviderHTTPError,
    ProviderNetworkError,
    ProviderResponseError,
)
from video_production.domain.models import Asset, AssetLicense


def asset(source="pixabay", **updates):
    return Asset(
        id="photo-1",
        source=source,
        media_type="image",
        download_url="https://images.example.org/photo.jpg",
        license=AssetLicense(name="Test fixture license"),
        **updates,
    )


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"partial data"
        raise httpx.ReadError("simulated interrupted download")


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_pixabay_and_commons_stream_download_to_requested_destination(self):
        def handler(request):
            self.assertEqual(request.url.host, "images.example.org")
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("key", request.url.params)
            self.assertIn("Automa-o-Scrapping", request.headers["User-Agent"])
            return httpx.Response(200, content=b"image bytes")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            providers = (
                PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config()),
                WikimediaCommonsProvider(client=client, settings=config()),
            )
            for provider in providers:
                with self.subTest(provider=provider.source), TemporaryDirectory() as directory:
                    destination = Path(directory) / "nested" / "photo.jpg"
                    result = await provider.download(asset(provider.source), destination)
                    self.assertEqual(result, destination)
                    self.assertEqual(destination.read_bytes(), b"image bytes")
                    self.assertEqual(list(destination.parent.iterdir()), [destination])

    async def test_unsplash_tracks_download_and_keeps_authorization_off_cdn(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.host == "api.unsplash.com":
                self.assertEqual(request.url.path, "/photos/photo-1/download")
                self.assertEqual(request.headers["Authorization"], f"Client-ID {UNSPLASH_TEST_KEY}")
                return httpx.Response(200, json={"url": "https://images.unsplash.com/tracked.jpg"})
            self.assertEqual(request.url.host, "images.unsplash.com")
            self.assertNotIn("authorization", request.headers)
            return httpx.Response(200, content=b"tracked image")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = UnsplashProvider(UNSPLASH_TEST_KEY, client=client, settings=config())
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "photo.jpg"
                await provider.download(asset("unsplash"), destination)
                self.assertEqual(destination.read_bytes(), b"tracked image")
        self.assertEqual(len(requests), 2)

    async def test_unsplash_uses_provided_download_location_and_rejects_other_hosts(self):
        location = "https://api.unsplash.com/photos/photo-1/download?ixid=example"
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.host == "api.unsplash.com":
                return httpx.Response(200, json={"url": "https://images.unsplash.com/tracked.jpg"})
            return httpx.Response(200, content=b"image")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = UnsplashProvider(UNSPLASH_TEST_KEY, client=client, settings=config())
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "image.jpg"
                await provider.download(
                    asset("unsplash", download_tracking_url=location),
                    destination,
                )
                self.assertEqual(calls[0], location)
                with self.assertRaises(ProviderResponseError):
                    await provider.download(
                        asset(
                            "unsplash",
                            download_tracking_url="https://example.org/track",
                        ),
                        destination,
                    )
                self.assertEqual(len(calls), 2)

    async def test_unsplash_missing_tracking_url_response_does_not_download(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
        ) as client:
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "image.jpg"
                provider = UnsplashProvider(UNSPLASH_TEST_KEY, client=client, settings=config())
                with self.assertRaises(ProviderResponseError):
                    await provider.download(asset("unsplash"), destination)
                self.assertFalse(destination.exists())

    async def test_download_http_errors_leave_existing_file_intact(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(404, content=b"missing"))
        ) as client:
            provider = PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config())
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "image.jpg"
                destination.write_bytes(b"original")
                with self.assertRaises(ProviderHTTPError):
                    await provider.download(asset(), destination)
                self.assertEqual(destination.read_bytes(), b"original")
                self.assertEqual(list(Path(directory).iterdir()), [destination])

    async def test_interrupted_stream_preserves_existing_file_and_removes_temporary(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, stream=BrokenStream())
            )
        ) as client:
            provider = PixabayProvider(PIXABAY_TEST_KEY, client=client, settings=config())
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "image.jpg"
                destination.write_bytes(b"original")
                with self.assertRaises(ProviderNetworkError):
                    await provider.download(asset(), destination)
                self.assertEqual(destination.read_bytes(), b"original")
                self.assertEqual(list(Path(directory).iterdir()), [destination])

    async def test_empty_download_is_rejected_without_partial_file(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b""))
        ) as client:
            provider = WikimediaCommonsProvider(client=client, settings=config())
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "image.jpg"
                with self.assertRaises(AssetDownloadError):
                    await provider.download(asset("wikimedia_commons"), destination)
                self.assertFalse(destination.exists())
                self.assertEqual(list(Path(directory).iterdir()), [])

    async def test_filesystem_error_cleans_temporary_file(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"image bytes")
            )
        ) as client:
            provider = WikimediaCommonsProvider(client=client, settings=config())
            with TemporaryDirectory() as directory:
                destination = Path(directory) / "existing-directory"
                destination.mkdir()
                with self.assertRaises(AssetDownloadError):
                    await provider.download(asset("wikimedia_commons"), destination)
                self.assertEqual(list(Path(directory).iterdir()), [destination])

    async def test_wrong_source_and_non_http_urls_fail_before_download(self):
        def handler(request):
            self.fail("HTTP should not be called")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = WikimediaCommonsProvider(client=client, settings=config())
            with self.assertRaises(ProviderConfigurationError):
                await provider.download(asset(), Path("unused.jpg"))
            local = asset("wikimedia_commons").model_copy(update={"download_url": "file:///local"})
            with self.assertRaises(ProviderResponseError):
                await provider.download(local, Path("unused.jpg"))
