"""Um provider de teste usa o contrato sem herdar de classes de SDKs."""

import unittest
from importlib import import_module
from pathlib import Path

from video_production.assets import AssetProvider
from video_production.domain.models import Asset, AssetKind, AssetLicense, AssetQuery


class InMemoryAssetProvider:
    """Implementação usada apenas nos testes; não acessa rede nem disco."""

    def __init__(self, assets: tuple[Asset, ...]):
        self.assets = assets

    async def search(self, query: AssetQuery) -> tuple[Asset, ...]:
        return tuple(item for item in self.assets if item.kind == query.kind)[: query.limit]

    async def download(self, asset: Asset, destination: Path) -> Path:
        raise NotImplementedError("Este provider de teste não baixa assets")


class InterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_consumer_accepts_an_injected_provider(self):
        image = Asset(
            id="image-1", provider="memory", kind=AssetKind.IMAGE,
            uri="file:///city.jpg", license=AssetLicense(name="CC0"),
        )
        video = Asset(
            id="video-1", provider="memory", kind=AssetKind.VIDEO,
            uri="file:///city.mp4", license=AssetLicense(name="CC0"),
        )
        provider: AssetProvider = InMemoryAssetProvider((video, image, image))
        results = await provider.search(AssetQuery(query="city", limit=1))
        self.assertEqual(results, (image,))

    async def test_all_extension_contracts_are_importable(self):
        for module, name in (
            ("assets", "AssetProvider"),
            ("llm", "LLMProvider"),
            ("planner", "VisualPlanner"),
            ("references", "ReferenceAnalyzer"),
            ("narration", "NarrationProvider"),
            ("composition", "VideoComposer"),
        ):
            with self.subTest(module=module):
                contract = getattr(import_module(f"video_production.{module}"), name)
                with self.assertRaises(TypeError):
                    contract()
