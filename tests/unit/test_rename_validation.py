"""Tests for filename validation in FileOperations.rename_item()."""
import os
import tempfile
from pathlib import Path

from core.file_operations import FileOperations


class TestRenameValidation:
    """Verify that rename_item rejects invalid filenames."""

    def test_rejects_slash_in_name(self, tmp_path):
        """Filenames containing '/' must be rejected."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, msg = FileOperations.rename_item(str(f), "bad/name.txt")
        assert not success
        assert "Invalid filename" in msg
        assert f.exists(), "Original file should still exist"

    def test_rejects_null_byte_in_name(self, tmp_path):
        """Filenames containing null bytes must be rejected."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, msg = FileOperations.rename_item(str(f), "bad\x00name.txt")
        assert not success
        assert "Invalid filename" in msg

    def test_rejects_empty_name(self, tmp_path):
        """Empty filenames must be rejected."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, msg = FileOperations.rename_item(str(f), "")
        assert not success
        assert "Invalid filename" in msg

    def test_accepts_valid_name(self, tmp_path):
        """Normal filenames should still work."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, result = FileOperations.rename_item(str(f), "renamed.txt")
        assert success
        assert (tmp_path / "renamed.txt").exists()

    def test_accepts_name_with_spaces(self, tmp_path):
        """Filenames with spaces are valid."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, result = FileOperations.rename_item(str(f), "my file name.txt")
        assert success
        assert (tmp_path / "my file name.txt").exists()

    def test_accepts_unicode_name(self, tmp_path):
        """Unicode filenames are valid."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, result = FileOperations.rename_item(str(f), "données_café.txt")
        assert success
        assert (tmp_path / "données_café.txt").exists()

    def test_same_name_returns_success(self, tmp_path):
        """Renaming to the same name is a no-op success."""
        f = tmp_path / "original.txt"
        f.write_text("data")
        success, result = FileOperations.rename_item(str(f), "original.txt")
        assert success

    def test_name_already_exists_returns_failure(self, tmp_path):
        """Renaming to a name that already exists should fail."""
        f1 = tmp_path / "first.txt"
        f2 = tmp_path / "second.txt"
        f1.write_text("data1")
        f2.write_text("data2")
        success, msg = FileOperations.rename_item(str(f1), "second.txt")
        assert not success
        assert "already exists" in msg
