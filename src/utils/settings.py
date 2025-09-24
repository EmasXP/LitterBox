"""
Settings management for the file manager
"""
import json
import os
import base64
from pathlib import Path
from PyQt6.QtCore import QByteArray

class Settings:
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "filemanager"
        self.config_file = self.config_dir / "settings.json"
        self.settings = self.load_settings()

    def load_settings(self):
        """Load settings from config file"""
        default_settings = {
            "window_geometry": None,
            "sort_column": 0,  # Name column
            "sort_order": 0,   # Ascending
            "show_hidden": True
        }

        if not self.config_file.exists():
            return default_settings

        try:
            with open(self.config_file, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults to handle new settings
                default_settings.update(loaded)
                return default_settings
        except (json.JSONDecodeError, IOError):
            return default_settings

    def save_settings(self):
        """Save current settings to config file"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
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

        self.settings[key] = value
        self.save_settings()
