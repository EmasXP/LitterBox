"""Regression tests for ``FileOperations.rename_item`` safety (bug #6).

Covers:
- Path traversal / invalid name rejection (defense in depth).
- Refusal to silently overwrite an existing entry (TOCTOU-safe).
- Case-only renames on case-insensitive filesystems.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.file_operations import FileOperations  # noqa: E402


class TestRenameValidation:
    @pytest.mark.parametrize(
        "name", ["", ".", "..", "a/b", "a\\b", "with\x00null"]
    )
    def test_rejects_invalid_names(self, tmp_path, name):
        f = tmp_path / "x.txt"
        f.write_text("data")
        ok, msg = FileOperations.rename_item(str(f), name)
        assert not ok
        assert f.read_text() == "data"  # unchanged


class TestRenameDoesNotClobber:
    def test_rename_to_existing_file_refuses(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("A")
        b.write_text("B")

        ok, msg = FileOperations.rename_item(str(a), "b.txt")
        assert not ok
        # Both files survive untouched.
        assert a.read_text() == "A"
        assert b.read_text() == "B"

    def test_rename_to_existing_dir_refuses(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        d = tmp_path / "dest"
        d.mkdir()
        (d / "important.txt").write_text("DO NOT TOUCH")

        ok, _ = FileOperations.rename_item(str(f), "dest")
        assert not ok
        assert (d / "important.txt").read_text() == "DO NOT TOUCH"
        assert f.read_text() == "data"

    def test_rename_uses_link_unlink_for_files(self, tmp_path):
        """The TOCTOU-safe path uses os.link + unlink for regular files."""
        f = tmp_path / "src.txt"
        f.write_text("data")

        with patch("core.file_operations.os.link", wraps=os.link) as link:
            ok, result = FileOperations.rename_item(str(f), "dst.txt")
            assert ok
            link.assert_called_once()

        new = tmp_path / "dst.txt"
        assert new.read_text() == "data"
        assert not f.exists()
        assert result == str(new)

    def test_rename_falls_back_when_link_unsupported(self, tmp_path):
        """If os.link raises (cross-FS, FUSE, ...) we still rename via os.rename."""
        f = tmp_path / "src.txt"
        f.write_text("data")

        original_link = os.link

        def boom(*args, **kwargs):
            raise OSError("EXDEV")

        with patch("core.file_operations.os.link", side_effect=boom):
            ok, _ = FileOperations.rename_item(str(f), "dst.txt")
            assert ok

        assert (tmp_path / "dst.txt").read_text() == "data"
        assert not f.exists()
        # Sanity: real os.link still works (we patched only the module-level binding).
        del original_link

    def test_rename_directory_works(self, tmp_path):
        d = tmp_path / "old"
        d.mkdir()
        (d / "child.txt").write_text("hi")

        ok, _ = FileOperations.rename_item(str(d), "new")
        assert ok
        assert not d.exists()
        assert (tmp_path / "new" / "child.txt").read_text() == "hi"


class TestRenameCaseOnly:
    def test_case_only_rename_succeeds(self, tmp_path):
        f = tmp_path / "Foo.txt"
        f.write_text("data")

        ok, result = FileOperations.rename_item(str(f), "FOO.TXT")
        assert ok, result
        # On case-sensitive FS the file is now named FOO.TXT (Foo.txt is gone).
        # On case-insensitive FS both names refer to the same inode but the
        # visible casing should be FOO.TXT.
        assert (tmp_path / "FOO.TXT").exists()
        assert (tmp_path / "FOO.TXT").read_text() == "data"
        # Listdir reflects the new casing.
        names = [p.name for p in tmp_path.iterdir()]
        assert "FOO.TXT" in names

    def test_identical_name_is_noop(self, tmp_path):
        f = tmp_path / "same.txt"
        f.write_text("data")

        ok, result = FileOperations.rename_item(str(f), "same.txt")
        assert ok
        assert result == str(f)
        assert f.read_text() == "data"
