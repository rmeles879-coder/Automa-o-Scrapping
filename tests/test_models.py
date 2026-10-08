"""Validação dos principais dados que cruzam fronteiras da arquitetura."""

import unittest
from pathlib import Path

from pydantic import ValidationError

from video_production.domain.models import (
    Asset,
    AssetKind,
    AssetLicense,
    AssetQuery,
    CompositionRequest,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    SceneMedia,
    ScenePlan,
    VideoBrief,
    VideoSpec,
    VisualPlan,
)


def scene(scene_id="opening", duration=5.0):
    return ScenePlan(id=scene_id, duration_seconds=duration, visual_description="Vista da cidade")


def asset():
    return Asset(
        id="local-1",
        provider="local",
        kind=AssetKind.IMAGE,
        uri="file:///assets/city.jpg",
        license=AssetLicense(name="CC0"),
    )


class ModelTests(unittest.TestCase):
    def test_plan_duration_and_order(self):
        plan = VisualPlan(scenes=(scene(), scene("closing", 2.5)))
        self.assertEqual(plan.duration_seconds, 7.5)
        self.assertEqual([item.id for item in plan.scenes], ["opening", "closing"])

    def test_plan_json_roundtrip(self):
        plan = VisualPlan(scenes=(scene(),))
        self.assertEqual(VisualPlan.model_validate_json(plan.model_dump_json()), plan)

    def test_empty_and_duplicate_scenes_are_rejected(self):
        for scenes in ((), (scene(), scene())):
            with self.subTest(scenes=scenes), self.assertRaises(ValidationError):
                VisualPlan(scenes=scenes)

    def test_invalid_scene_durations_are_rejected(self):
        for duration in (0, -1, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValidationError):
                scene(duration=duration)

    def test_blank_text_and_invalid_query_limits_are_rejected(self):
        for values in ({"query": "   "}, {"query": "city", "limit": 0}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                AssetQuery(**values)

    def test_video_spec_rejects_invalid_dimensions_and_fps(self):
        for values in ({"width": 0}, {"height": -1}, {"fps": 0}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                VideoSpec(**values)

    def test_video_brief_validates_target_duration(self):
        with self.assertRaises(ValidationError):
            VideoBrief(title="City", script="A city tour", target_duration_seconds=0)

    def test_unknown_fields_and_mutation_are_rejected(self):
        with self.assertRaises(ValidationError):
            VideoSpec(unknown="value")
        spec = VideoSpec()
        with self.assertRaises(ValidationError):
            spec.fps = 60

    def test_asset_requires_license_metadata(self):
        with self.assertRaises(ValidationError):
            Asset(id="1", provider="local", kind="image", uri="file:///image.jpg")
        self.assertEqual(asset().license.name, "CC0")

    def test_llm_request_and_response(self):
        message = LLMMessage(role="user", content="Descreva a cena")
        self.assertEqual(LLMRequest(messages=(message,)).max_tokens, 1024)
        self.assertEqual(LLMResponse(text="Vista ampla", model="local").text, "Vista ampla")

    def test_invalid_llm_requests_are_rejected(self):
        message = LLMMessage(role="user", content="Descreva a cena")
        for values in (
            {"messages": ()},
            {"messages": (message,), "temperature": 3},
            {"messages": (message,), "max_tokens": 0},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                LLMRequest(**values)
        with self.assertRaises(ValidationError):
            LLMMessage(role="invalid", content="text")

    def test_composition_uses_local_media_and_serializes_paths(self):
        request = CompositionRequest(
            plan=VisualPlan(scenes=(scene(),)),
            media=(SceneMedia(scene_id="opening", asset=asset(), local_path=Path("city.jpg")),),
            output_path=Path("output/video.mp4"),
        )
        self.assertEqual(CompositionRequest.model_validate_json(request.model_dump_json()), request)

    def test_composition_rejects_unknown_and_duplicate_scene_media(self):
        for ids in (("unknown",), ("opening", "opening")):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                CompositionRequest(
                    plan=VisualPlan(scenes=(scene(),)),
                    media=tuple(
                        SceneMedia(scene_id=item, asset=asset(), local_path=Path("city.jpg"))
                        for item in ids
                    ),
                    output_path=Path("video.mp4"),
                )

    def test_asset_serializes_new_canonical_fields_and_accepts_legacy_names(self):
        legacy = asset()
        payload = legacy.model_dump(mode="json")
        self.assertEqual(payload["source"], "local")
        self.assertEqual(payload["media_type"], "image")
        self.assertEqual(payload["download_url"], "file:///assets/city.jpg")
        self.assertTrue(
            {"title", "description", "tags", "thumbnail_url", "source_page_url", "author"}
            <= payload.keys()
        )
        self.assertNotIn("provider", payload)
        self.assertNotIn("kind", payload)
        self.assertNotIn("uri", payload)
        self.assertEqual(Asset.model_validate_json(legacy.model_dump_json()), legacy)
