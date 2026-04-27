"""Tests for Settings cache correctness — deep copy prevents mutation."""
import json
import os
from pathlib import Path

from utils.settings import Settings


class TestSettingsCacheDeepCopy:
    """Verify that Settings cache uses deep copies to prevent shared mutation."""

    def test_mutating_returned_list_does_not_corrupt_cache(self, tmp_path):
        """Modifying a returned list (e.g. column_widths) must NOT affect the cache."""
        config_dir = tmp_path / ".config" / "litterbox"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "settings.json"
        config_file.write_text(json.dumps({
            "column_widths": [200, 100, 150]
        }))

        # Patch settings to use tmp location
        s = Settings()
        s.config_dir = config_dir
        s.config_file = config_file

        # Invalidate class-level cache so it reads fresh
        Settings._cached_settings = None
        Settings._cache_file_mtime = None

        s.settings = s.load_settings()
        widths = s.settings.get("column_widths")
        assert widths == [200, 100, 150]

        # Mutate the returned list
        widths.append(999)
        widths[0] = 42

        # Load again — cache should be unaffected
        s2 = Settings()
        s2.config_dir = config_dir
        s2.config_file = config_file
        s2.settings = s2.load_settings()
        cached_widths = s2.settings.get("column_widths")

        assert cached_widths == [200, 100, 150], (
            f"Cache was corrupted by caller mutation: got {cached_widths}"
        )

    def test_mutating_returned_dict_does_not_corrupt_cache(self, tmp_path):
        """Modifying the returned settings dict must NOT affect subsequent loads."""
        config_dir = tmp_path / ".config" / "litterbox"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "settings.json"
        config_file.write_text(json.dumps({
            "show_hidden": True,
            "sort_column": 0
        }))

        Settings._cached_settings = None
        Settings._cache_file_mtime = None

        s = Settings()
        s.config_dir = config_dir
        s.config_file = config_file
        s.settings = s.load_settings()

        # Mutate returned dict
        s.settings["show_hidden"] = False
        s.settings["injected_key"] = "bad"

        # Fresh load should have original values
        Settings._cached_settings = None  # force re-read to be sure
        Settings._cache_file_mtime = None
        s2 = Settings()
        s2.config_dir = config_dir
        s2.config_file = config_file
        s2.settings = s2.load_settings()

        assert s2.settings["show_hidden"] is True
        assert "injected_key" not in s2.settings
