"""Regression tests for ConflictDialog input validation (bug #4).

The rename tab must reject names that could escape the destination directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.conflict_dialog import ConflictDialog  # noqa: E402


class TestFilenameValidation:
    @pytest.mark.parametrize(
        "name",
        [
            "",
            ".",
            "..",
            "foo/bar",
            "../escape",
            "../../etc/passwd",
            "sub\\file",
            "with\x00null",
            "/abs/path",
            "~/in-home",
        ],
    )
    def test_rejects_unsafe_names(self, name):
        assert not ConflictDialog._is_valid_filename(name), (
            f"Bug #4: dialog accepted unsafe name {name!r}"
        )

    @pytest.mark.parametrize(
        "name",
        ["foo.txt", "foo (1).txt", "archive.tar.gz", ".hidden", "a-b_c.d"],
    )
    def test_accepts_safe_names(self, name):
        assert ConflictDialog._is_valid_filename(name)

    def test_dialog_disables_ok_for_traversal(self, qapp, tmp_path):
        existing = tmp_path / "doc.txt"
        existing.write_text("x")
        source = tmp_path / "src.txt"
        source.write_text("y")

        dlg = ConflictDialog(
            "doc.txt", parent=None, source_path=str(source), existing_path=str(existing)
        )
        try:
            dlg.rename_edit.setText("../evil.txt")
            dlg._update_ok_state()
            assert not dlg.ok_btn.isEnabled(), (
                "Bug #4: OK button enabled for traversal name"
            )

            dlg.rename_edit.setText("doc-renamed.txt")
            dlg._update_ok_state()
            assert dlg.ok_btn.isEnabled()
        finally:
            dlg.deleteLater()
