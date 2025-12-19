"""
Unit tests for .desktop file icon extraction in FileListView
"""
import pytest
import tempfile
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.file_list_view import FileListView


class TestDesktopFileIcon:
    """Test .desktop file icon extraction and display"""

    @pytest.fixture
    def file_list_view(self, qapp):
        """Create a FileListView instance for testing"""
        view = FileListView()
        return view

    def test_get_desktop_file_icon_valid(self, file_list_view, tmp_path):
        """Test extraction of valid Icon property from .desktop file"""
        # Create a test .desktop file with a common theme icon
        desktop_file = tmp_path / "test.desktop"
        desktop_content = """[Desktop Entry]
Name=Test Application
Exec=test-app
Icon=folder
Type=Application
"""
        desktop_file.write_text(desktop_content)

        # Get icon from the .desktop file
        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        # Icon might be None if theme icon isn't available, but method shouldn't crash
        # If icon is found, it should be valid
        assert icon is None or (isinstance(icon, QIcon) and not icon.isNull())

    def test_get_desktop_file_icon_theme_icon(self, file_list_view, tmp_path):
        """Test extraction of theme-based icon from .desktop file"""
        desktop_file = tmp_path / "firefox.desktop"
        desktop_content = """[Desktop Entry]
Name=Firefox
Exec=firefox
Icon=firefox
Type=Application
"""
        desktop_file.write_text(desktop_content)

        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        # Icon might be None if firefox icon isn't available, but method shouldn't crash
        assert icon is None or isinstance(icon, QIcon)

    def test_get_desktop_file_icon_absolute_path(self, file_list_view, tmp_path):
        """Test extraction of absolute path icon from .desktop file"""
        # Create a simple icon file (1x1 PNG)
        icon_file = tmp_path / "icon.png"
        # Minimal valid PNG (1x1 transparent)
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        icon_file.write_bytes(png_data)

        desktop_file = tmp_path / "test-abs.desktop"
        desktop_content = f"""[Desktop Entry]
Name=Test Application
Exec=test-app
Icon={icon_file}
Type=Application
"""
        desktop_file.write_text(desktop_content)

        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        # Should find the icon file
        assert icon is not None
        assert not icon.isNull()

    def test_get_desktop_file_icon_no_icon_property(self, file_list_view, tmp_path):
        """Test .desktop file without Icon property returns None"""
        desktop_file = tmp_path / "no-icon.desktop"
        desktop_content = """[Desktop Entry]
Name=Test Application
Exec=test-app
Type=Application
"""
        desktop_file.write_text(desktop_content)

        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        assert icon is None

    def test_get_desktop_file_icon_empty_icon(self, file_list_view, tmp_path):
        """Test .desktop file with empty Icon property returns None"""
        desktop_file = tmp_path / "empty-icon.desktop"
        desktop_content = """[Desktop Entry]
Name=Test Application
Exec=test-app
Icon=
Type=Application
"""
        desktop_file.write_text(desktop_content)

        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        assert icon is None

    def test_get_desktop_file_icon_invalid_file(self, file_list_view, tmp_path):
        """Test invalid .desktop file doesn't crash"""
        desktop_file = tmp_path / "invalid.desktop"
        desktop_file.write_text("This is not a valid .desktop file")

        # Should not raise an exception
        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        assert icon is None

    def test_get_desktop_file_icon_non_desktop_file(self, file_list_view, tmp_path):
        """Test non-.desktop file returns None immediately"""
        text_file = tmp_path / "test.txt"
        text_file.write_text("Some text")

        icon = file_list_view._get_desktop_file_icon(str(text_file))

        assert icon is None

    def test_get_desktop_file_icon_nonexistent_icon_path(self, file_list_view, tmp_path):
        """Test .desktop file with nonexistent absolute icon path returns None"""
        desktop_file = tmp_path / "bad-path.desktop"
        desktop_content = """[Desktop Entry]
Name=Test Application
Exec=test-app
Icon=/nonexistent/path/to/icon.png
Type=Application
"""
        desktop_file.write_text(desktop_content)

        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        # Should return None since icon file doesn't exist
        assert icon is None

    def test_file_icon_from_mime_uses_desktop_icon(self, file_list_view, tmp_path):
        """Test that _file_icon_from_mime uses .desktop file icon when available"""
        desktop_file = tmp_path / "app.desktop"
        desktop_content = """[Desktop Entry]
Name=Test App
Exec=test
Icon=folder
Type=Application
"""
        desktop_file.write_text(desktop_content)

        # Get icon through the mime method
        icon = file_list_view._file_icon_from_mime(str(desktop_file), False)

        # Should return a valid icon (folder theme icon)
        assert not icon.isNull()

    def test_file_icon_from_mime_fallback_for_desktop_without_icon(self, file_list_view, tmp_path):
        """Test that _file_icon_from_mime falls back to default for .desktop without Icon"""
        desktop_file = tmp_path / "no-icon-app.desktop"
        desktop_content = """[Desktop Entry]
Name=Test App
Exec=test
Type=Application
"""
        desktop_file.write_text(desktop_content)

        # Get icon through the mime method
        icon = file_list_view._file_icon_from_mime(str(desktop_file), False)

        # Should return some icon (fallback behavior)
        assert not icon.isNull()

    def test_desktop_file_with_multiple_sections(self, file_list_view, tmp_path):
        """Test .desktop file with multiple sections (only [Desktop Entry] matters)"""
        desktop_file = tmp_path / "multi-section.desktop"
        desktop_content = """[Desktop Entry]
Name=Test Application
Exec=test-app
Icon=folder
Type=Application

[Desktop Action Gallery]
Name=Open Gallery
Exec=test-app --gallery
"""
        desktop_file.write_text(desktop_content)

        icon = file_list_view._get_desktop_file_icon(str(desktop_file))

        # Icon might be None if theme icon isn't available, but should parse correctly
        # If icon is found, it should be valid
        assert icon is None or (isinstance(icon, QIcon) and not icon.isNull())
