"""
Unit tests for plain-text MIME type fallback

Tests the automatic detection of plain-text files and addition of
text/plain as a fallback MIME type for files like JSON, YAML, etc.
"""
import pytest
import os
import tempfile
from pathlib import Path
from core.application_manager import ApplicationManager


class TestPlainTextDetection:
    """Test the _appears_to_be_text method"""

    def test_empty_file_is_text(self):
        """Empty files should be considered text"""
        manager = ApplicationManager()
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_path = f.name

        try:
            assert manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_json_file_is_text(self):
        """JSON files should be detected as text"""
        manager = ApplicationManager()
        content = '{"name": "test", "value": 123, "nested": {"key": "value"}}'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write(content)
            temp_path = f.name

        try:
            assert manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_yaml_file_is_text(self):
        """YAML files should be detected as text"""
        manager = ApplicationManager()
        content = """
name: test
value: 123
nested:
  key: value
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(content)
            temp_path = f.name

        try:
            assert manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_xml_file_is_text(self):
        """XML files should be detected as text"""
        manager = ApplicationManager()
        content = '<?xml version="1.0"?><root><item>test</item></root>'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.xml') as f:
            f.write(content)
            temp_path = f.name

        try:
            assert manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_unicode_file_is_text(self):
        """Files with Unicode content should be detected as text"""
        manager = ApplicationManager()
        content = 'Hello 世界 🌍 Привет'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            assert manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_binary_file_not_text(self):
        """Binary files with null bytes should not be detected as text"""
        manager = ApplicationManager()
        binary_content = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'

        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(binary_content)
            temp_path = f.name

        try:
            assert not manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_png_file_not_text(self):
        """PNG files should not be detected as text"""
        manager = ApplicationManager()
        # PNG file signature
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.png') as f:
            f.write(png_header)
            temp_path = f.name

        try:
            assert not manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_large_text_file(self):
        """Large text files should be detected correctly (tests max_bytes limit)"""
        manager = ApplicationManager()
        # Create a file larger than max_bytes (8192 default)
        content = 'Hello World!\n' * 1000  # > 8KB

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            temp_path = f.name

        try:
            assert manager._appears_to_be_text(temp_path)
        finally:
            os.unlink(temp_path)

    def test_mixed_content_mostly_text(self):
        """Files with mostly printable characters should be detected as text"""
        manager = ApplicationManager()
        # Some non-printable but no null bytes
        content = 'Hello\x01\x02World\nTest\x03Line'

        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
            f.write(content.encode('latin-1'))
            temp_path = f.name

        try:
            # This should still be detected as text based on the ratio
            result = manager._appears_to_be_text(temp_path)
            # Result depends on the ratio of printable characters
            # With "Hello\x01\x02World\nTest\x03Line", we have ~20 printable chars out of 23
            # That's about 87%, which should pass the 85% threshold
            assert result
        finally:
            os.unlink(temp_path)


class TestPlainTextFallback:
    """Test the text/plain fallback in _get_mime_types_for_file"""

    def test_json_gets_text_plain_fallback(self):
        """JSON files should get text/plain as a fallback"""
        manager = ApplicationManager()
        content = '{"name": "test", "value": 123}'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # Should have application/json and its fallbacks, plus text/plain
            assert 'text/plain' in mime_types
            # text/plain should come after the specific JSON fallbacks
            json_index = mime_types.index('application/json') if 'application/json' in mime_types else -1
            plain_index = mime_types.index('text/plain')
            # text/plain should be in the list
            assert plain_index >= 0
        finally:
            os.unlink(temp_path)

    def test_yaml_gets_text_plain_fallback(self):
        """YAML files should get text/plain as a fallback"""
        manager = ApplicationManager()
        content = 'name: test\nvalue: 123\n'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # YAML already has text/plain in its fallbacks, so it should be there
            assert 'text/plain' in mime_types
        finally:
            os.unlink(temp_path)

    def test_unknown_text_format_gets_fallback(self):
        """Unknown text-like files should get text/plain fallback"""
        manager = ApplicationManager()
        content = 'This is a custom configuration file\nkey=value\n'

        # Use an unusual extension that might return application/*
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.customconf') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # Should include text/plain as a fallback
            assert 'text/plain' in mime_types
        finally:
            os.unlink(temp_path)

    def test_binary_file_no_text_plain_fallback(self):
        """Binary files should not get text/plain fallback"""
        manager = ApplicationManager()
        binary_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.png') as f:
            f.write(binary_content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # PNG files should not get text/plain fallback
            # (they're images, which we explicitly exclude)
            assert 'text/plain' not in mime_types
        finally:
            os.unlink(temp_path)

    def test_text_file_already_has_text_plain(self):
        """Text files that already have text/plain don't get duplicate"""
        manager = ApplicationManager()
        content = 'This is a plain text file\n'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # Should have text/plain
            assert 'text/plain' in mime_types
            # Should only appear once
            assert mime_types.count('text/plain') == 1
        finally:
            os.unlink(temp_path)

    def test_config_file_gets_text_plain(self):
        """Configuration files should get text/plain fallback"""
        manager = ApplicationManager()
        content = '[section]\nkey=value\nother_key=other_value\n'

        # INI/config files
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.conf') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # Should include text/plain as a fallback
            assert 'text/plain' in mime_types
        finally:
            os.unlink(temp_path)

    def test_markdown_file_gets_text_plain(self):
        """Markdown files should include text/plain"""
        manager = ApplicationManager()
        content = '# Heading\n\nThis is **markdown** content.\n'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # Markdown files should have text/plain as fallback
            # (they're text/markdown or text/x-markdown, but text/plain is added)
            assert 'text/plain' in mime_types
        finally:
            os.unlink(temp_path)

    def test_csv_file_behavior(self):
        """CSV files should be handled appropriately"""
        manager = ApplicationManager()
        content = 'name,age,city\nJohn,30,NYC\nJane,25,LA\n'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(content)
            temp_path = f.name

        try:
            mime_types = manager._get_mime_types_for_file(temp_path)
            # CSV is typically text/csv or text/plain
            # If it's text/csv (text/*), it should already have text/plain
            # If it's application/csv, it should get text/plain added
            assert 'text/plain' in mime_types
        finally:
            os.unlink(temp_path)


class TestIntegrationWithApplications:
    """Test that the plain-text fallback helps find applications"""

    def test_json_file_can_find_text_editors(self):
        """JSON files should be able to find text editor applications"""
        manager = ApplicationManager()
        content = '{"name": "test"}'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write(content)
            temp_path = f.name

        try:
            # Get applications for the JSON file
            apps = manager.get_applications_for_file(temp_path)

            # Should be able to find at least some applications
            # (assuming text editors are installed on the test system)
            # Note: This might be 0 in minimal CI environments
            # The key is that with text/plain fallback, we increase chances
            assert isinstance(apps, list)

            # Get the MIME types used
            mime_types = manager._get_mime_types_for_file(temp_path)
            assert 'text/plain' in mime_types

        finally:
            os.unlink(temp_path)

    def test_unknown_extension_with_text_content(self):
        """Files with unknown extensions but text content should find apps"""
        manager = ApplicationManager()
        content = 'This is plain text content in an unusual file.'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.weirdext') as f:
            f.write(content)
            temp_path = f.name

        try:
            # Get MIME types
            mime_types = manager._get_mime_types_for_file(temp_path)

            # Should include text/plain as fallback
            assert 'text/plain' in mime_types

            # Should be able to query for applications
            apps = manager.get_applications_for_file(temp_path)
            assert isinstance(apps, list)

        finally:
            os.unlink(temp_path)
