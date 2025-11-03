"""Tests for warning label behavior in ConflictDialog after style update."""
import tempfile
from pathlib import Path

from ui.conflict_dialog import ConflictDialog
from PyQt6.QtCore import QCoreApplication


def _process():
    QCoreApplication.processEvents()


def test_warning_visibility_for_existing_alternate_name(qapp):
    """Warning shows when a different existing name is entered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()
        (Path(tmpdir) / "foo (1).txt").touch()

        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )
        dlg.show(); _process()

        # Suggested should skip existing numbers -> foo (2).txt
        assert dlg.rename_edit.text() == "foo (2).txt"
        assert not dlg.name_conflict_warning.isVisible()

        # Enter an existing alternate name
        dlg.rename_edit.setText("foo (1).txt"); _process()
        assert dlg.name_conflict_warning.isVisible()
        assert not dlg.ok_btn.isEnabled()


def test_warning_not_shown_for_original_or_empty(qapp):
    """Original name or empty input disables OK but does not show warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "bar.txt"
        existing.touch()

        dlg = ConflictDialog(
            filename="bar.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )
        dlg.show(); _process()

        dlg.rename_edit.setText("bar.txt"); _process()
        assert not dlg.name_conflict_warning.isVisible()
        assert not dlg.ok_btn.isEnabled()

        dlg.rename_edit.setText(""); _process()
        assert not dlg.name_conflict_warning.isVisible()
        assert not dlg.ok_btn.isEnabled()


def test_warning_style_sheet_has_box(qapp):
    """Ensure style uses background, border and not bold red legacy style."""
    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "baz.txt"
        existing.touch()
        dlg = ConflictDialog(
            filename="baz.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )
        # We expect new style properties
        ss = dlg.name_conflict_warning.styleSheet()
        assert "background-color" in ss
        assert "border-radius" in ss
        assert "padding" in ss
        # Old bold red markers should be absent
        assert "font-weight: bold" not in ss
        assert "#d32f2f" not in ss
