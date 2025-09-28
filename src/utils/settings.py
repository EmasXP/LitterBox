"""
Settings management for LitterBox
"""
import json
import os
import base64
from pathlib import Path
from PyQt6.QtCore import QByteArray

class Settings:
    # Class-level cache to share data between instances
    _cached_settings = None
    _cache_file_mtime = None

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "litterbox"
        self.config_file = self.config_dir / "settings.json"
        self.settings = self.load_settings()

    def load_settings(self):
        """Load settings from config file with caching"""
        default_settings = {
            "window_geometry": None,
            "sort_column": 0,  # Name column
            "sort_order": 0,   # Ascending
            "show_hidden": True,
            "column_widths": [200, 100, 150]  # Default widths for Name, Size, Modified columns
        }

        if not self.config_file.exists():
            return default_settings

        try:
            # Check file modification time for cache invalidation
            current_mtime = self.config_file.stat().st_mtime

            # Use cached settings if file hasn't changed
            if (Settings._cached_settings is not None and
                Settings._cache_file_mtime == current_mtime):
                return Settings._cached_settings.copy()

            # Load from file
            with open(self.config_file, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults to handle new settings
                default_settings.update(loaded)

                # Cache the result
                Settings._cached_settings = default_settings.copy()
                Settings._cache_file_mtime = current_mtime

                return default_settings
        except (json.JSONDecodeError, IOError, OSError):
            return default_settings

    def save_settings(self):
        """Save current settings to config file"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)

            # Invalidate cache after saving
            Settings._cached_settings = None
            Settings._cache_file_mtime = None
        except IOError:
            pass  # Silently fail if we can't save

    def get(self, key, default=None):
        """Get a setting value"""
        value = self.settings.get(key, default)

        # Convert base64 string back to QByteArray for geometry-related keys
        if ("geometry" in key.lower() or "state" in key.lower()) and isinstance(value, str) and value:
            try:
                data = base64.b64decode(value.encode('utf-8'))
                return QByteArray(data)
            except Exception:
                return default

        return value

    def set(self, key, value):
        """Set a setting value"""
        # Convert QByteArray to base64 string for JSON serialization
        if isinstance(value, QByteArray):
            value = base64.b64encode(value.data()).decode('utf-8')

        # Always reload settings before modifying to get latest data
        self.settings = self.load_settings()
        self.settings[key] = value
        self.save_settings()

    def get_column_widths(self, default_widths=None):
        """Get column widths with fallback to defaults, always reload from file"""
        if default_widths is None:
            default_widths = [200, 100, 150]  # Name, Size, Modified

        # Always reload from file to get the latest values
        self.settings = self.load_settings()
        return self.settings.get("column_widths", default_widths)

    def set_column_widths(self, widths):
        """Set column widths"""
        self.settings["column_widths"] = list(widths)
        self.save_settings()
