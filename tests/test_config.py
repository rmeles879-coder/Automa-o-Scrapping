"""Testes da configuração sem depender do ambiente da máquina."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from video_production.config import Settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        # Isola apenas a configuração do projeto; não lê credenciais do host.
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_defaults(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.env, "development")
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.output_dir, Path("output"))
        self.assertEqual(settings.cache_dir, Path(".cache/video-production"))

    def test_environment_overrides_dotenv_and_explicit_values_override_environment(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("VIDEO_ENV=test\nVIDEO_LOG_LEVEL=WARNING\n", encoding="utf-8")
            os.environ["VIDEO_ENV"] = "production"
            settings = Settings(_env_file=env_file, log_level="DEBUG")
            self.assertEqual(settings.env, "production")
            self.assertEqual(settings.log_level, "DEBUG")

    def test_dotenv_and_unknown_values(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("VIDEO_ENV=test\nUNRELATED_SETTING=ignored\n", encoding="utf-8")
            self.assertEqual(Settings(_env_file=env_file).env, "test")

    def test_invalid_environment_is_rejected(self):
        os.environ["VIDEO_ENV"] = "invalid"
        with self.assertRaises(ValidationError):
            Settings(_env_file=None)

    def test_invalid_log_level_is_rejected(self):
        os.environ["VIDEO_LOG_LEVEL"] = "invalid"
        with self.assertRaises(ValidationError):
            Settings(_env_file=None)

    def test_paths_are_configurable_without_creating_directories(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "renders"
            cache = Path(directory) / "cache"
            os.environ["VIDEO_OUTPUT_DIR"] = str(output)
            os.environ["VIDEO_CACHE_DIR"] = str(cache)
            settings = Settings(_env_file=None)
            self.assertEqual(settings.output_dir, output)
            self.assertEqual(settings.cache_dir, cache)
            self.assertFalse(output.exists())
            self.assertFalse(cache.exists())

    def test_example_configuration_loads(self):
        example = Path(__file__).resolve().parents[1] / ".env.example"
        self.assertEqual(Settings(_env_file=example).log_level, "INFO")
