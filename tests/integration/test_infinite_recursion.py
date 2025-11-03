"""Test infinite recursion detection for file transfers."""
import os
import tempfile
import shutil
from pathlib import Path
import pytest

from src.core.file_transfer import check_infinite_recursion


class TestInfiniteRecursionDetection:
    """Test suite for detecting infinite recursion scenarios in file transfers."""

    def test_copy_into_self(self, tmp_path):
        """Test that copying a directory into itself is detected."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        error = check_infinite_recursion([str(source_dir)], str(source_dir))
        assert error is not None
        assert "into itself" in error.lower()

    def test_copy_into_subdirectory(self, tmp_path):
        """Test that copying a directory into its own subdirectory is detected."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        subdir = source_dir / "subdir"
        subdir.mkdir()

        error = check_infinite_recursion([str(source_dir)], str(subdir))
        assert error is not None
        assert "subdirectory" in error.lower() or "infinite loop" in error.lower()

    def test_copy_into_nested_subdirectory(self, tmp_path):
        """Test that copying into deeply nested subdirectory is detected."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        nested = source_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)

        error = check_infinite_recursion([str(source_dir)], str(nested))
        assert error is not None
        assert "subdirectory" in error.lower() or "infinite loop" in error.lower()

    def test_safe_copy_to_sibling(self, tmp_path):
        """Test that copying to a sibling directory is allowed."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "destination"
        dest_dir.mkdir()

        error = check_infinite_recursion([str(source_dir)], str(dest_dir))
        assert error is None

    def test_safe_copy_to_parent(self, tmp_path):
        """Test that copying to a parent directory is allowed."""
        source_dir = tmp_path / "parent" / "child"
        source_dir.mkdir(parents=True)
        parent_dir = tmp_path / "parent"

        error = check_infinite_recursion([str(source_dir)], str(parent_dir))
        assert error is None

    def test_safe_copy_to_unrelated(self, tmp_path):
        """Test that copying to an unrelated directory is allowed."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "completely" / "different" / "path"
        dest_dir.mkdir(parents=True)

        error = check_infinite_recursion([str(source_dir)], str(dest_dir))
        assert error is None

    def test_file_source_is_safe(self, tmp_path):
        """Test that file sources (not directories) don't trigger recursion."""
        source_file = tmp_path / "file.txt"
        source_file.write_text("test")
        dest_dir = tmp_path / "destination"
        dest_dir.mkdir()

        error = check_infinite_recursion([str(source_file)], str(dest_dir))
        assert error is None

    def test_multiple_sources_one_problematic(self, tmp_path):
        """Test detection when one of multiple sources would cause recursion."""
        source1 = tmp_path / "source1"
        source1.mkdir()
        source2 = tmp_path / "source2"
        source2.mkdir()
        subdir = source1 / "subdir"
        subdir.mkdir()

        # source2 is safe, but source1 into its own subdir is not
        error = check_infinite_recursion(
            [str(source1), str(source2)],
            str(subdir)
        )
        assert error is not None

    def test_nonexistent_source(self, tmp_path):
        """Test that nonexistent sources are handled gracefully."""
        nonexistent = tmp_path / "nonexistent"
        dest_dir = tmp_path / "destination"
        dest_dir.mkdir()

        error = check_infinite_recursion([str(nonexistent)], str(dest_dir))
        assert error is None  # Should not error on nonexistent sources

    def test_symlink_handling(self, tmp_path):
        """Test that symlinks are resolved correctly."""
        # Create a directory structure with symlinks
        real_source = tmp_path / "real_source"
        real_source.mkdir()

        link_to_source = tmp_path / "link_to_source"
        link_to_source.symlink_to(real_source)

        subdir = real_source / "subdir"
        subdir.mkdir()

        # Try to copy via symlink into the real subdirectory
        error = check_infinite_recursion([str(link_to_source)], str(subdir))
        assert error is not None

    def test_absolute_vs_relative_paths(self, tmp_path):
        """Test that both absolute and relative paths are handled correctly."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        subdir = source_dir / "subdir"
        subdir.mkdir()

        # Change to tmp_path to test relative paths
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            error = check_infinite_recursion(["source"], "source/subdir")
            assert error is not None
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
