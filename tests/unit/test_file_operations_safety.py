"""Regression tests for FileOperations safety fixes.

Covers:
- Bug #5: ``delete_item`` must remove a symlink-to-directory by unlinking the
  symlink (NOT recursing into the target via ``rmtree``).
- Bug #8: ``move_to_trash`` must pass ``--`` so filenames starting with ``-``
  are not parsed as options by ``gio``/``trash``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.file_operations import FileOperations  # noqa: E402


# ---------------------------------------------------------------------------
# Bug #5: deleting a symlink-to-directory must unlink the symlink only.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unsupported")
class TestDeleteSymlink:
    def test_dir_symlink_unlinked_target_preserved(self, tmp_path):
        target = tmp_path / "real_dir"
        target.mkdir()
        important = target / "important.txt"
        important.write_text("DO NOT DELETE")

        link = tmp_path / "link_to_dir"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("cannot create symlink")

        ok, msg = FileOperations.delete_item(str(link))
        assert ok, f"delete_item failed: {msg}"
        assert not link.exists() and not link.is_symlink(), (
            "symlink should be removed"
        )
        # CRITICAL: the target directory and its contents must be untouched.
        assert target.is_dir(), "Bug #5: deleting dir-symlink removed target dir"
        assert important.read_text() == "DO NOT DELETE"

    def test_file_symlink_unlinked_target_preserved(self, tmp_path):
        target = tmp_path / "real.txt"
        target.write_text("keep")
        link = tmp_path / "link.txt"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("cannot create symlink")

        ok, _ = FileOperations.delete_item(str(link))
        assert ok
        assert not link.exists()
        assert target.read_text() == "keep"


# ---------------------------------------------------------------------------
# Bug #8: leading-dash filenames must not be parsed as flags by trash tools.
# ---------------------------------------------------------------------------
class TestTrashLeadingDash:
    def test_gio_trash_uses_double_dash(self):
        with patch("core.file_operations.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0)
            ok, _ = FileOperations.move_to_trash("-rf")
            assert ok
            args, _kwargs = run.call_args
            cmd = args[0]
            assert cmd[0] == "gio"
            assert cmd[1] == "trash"
            assert "--" in cmd, (
                "Bug #8: gio trash must be invoked with '--' before the path"
            )
            assert cmd.index("--") < cmd.index("-rf")

    def test_trash_cli_fallback_uses_double_dash(self):
        # Make gio fail, then verify the trash-cli fallback also uses '--'.
        calls = []

        def fake_run(cmd, check=False, **kwargs):
            calls.append(cmd)
            if cmd[0] == "gio":
                raise FileNotFoundError("no gio")
            return subprocess.CompletedProcess(cmd, 0)

        with patch("core.file_operations.subprocess.run", side_effect=fake_run):
            ok, _ = FileOperations.move_to_trash("--force")
            assert ok
            # Last call should be the fallback.
            cmd = calls[-1]
            assert cmd[0] == "trash"
            assert "--" in cmd
            assert cmd.index("--") < cmd.index("--force")
