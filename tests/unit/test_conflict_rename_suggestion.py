"""Test conflict dialog's smart rename suggestions."""
import tempfile
from pathlib import Path

from ui.conflict_dialog import ConflictDialog


def test_suggest_rename_simple(qapp):
    """Test that ConflictDialog suggests 'foo (1).txt' when 'foo.txt' exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing file
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()

        # Create dialog
        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Check the suggested rename
        suggested = dlg.rename_edit.text()
        assert suggested == "foo (1).txt"


def test_suggest_rename_skips_occupied_numbers(qapp):
    """Test that ConflictDialog skips to next available number when (1) is also taken."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing files: foo.txt and foo (1).txt
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()

        existing_1 = Path(tmpdir) / "foo (1).txt"
        existing_1.touch()

        # Create dialog for foo.txt conflict
        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Should suggest foo (2).txt since foo (1).txt exists
        suggested = dlg.rename_edit.text()
        assert suggested == "foo (2).txt"


def test_suggest_rename_multiple_conflicts(qapp):
    """Test that ConflictDialog finds the first available number among multiple conflicts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing files: foo.txt, foo (1).txt, foo (2).txt
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()

        for i in range(1, 3):
            (Path(tmpdir) / f"foo ({i}).txt").touch()

        # Create dialog for foo.txt conflict
        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Should suggest foo (3).txt
        suggested = dlg.rename_edit.text()
        assert suggested == "foo (3).txt"


def test_suggest_rename_no_extension(qapp):
    """Test rename suggestion for files without extension."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing file without extension
        existing = Path(tmpdir) / "README"
        existing.touch()

        # Create dialog
        dlg = ConflictDialog(
            filename="README",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Should suggest README (1)
        suggested = dlg.rename_edit.text()
        assert suggested == "README (1)"


def test_suggest_rename_directory(qapp):
    """Test rename suggestion for directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing directory
        existing = Path(tmpdir) / "myfolder"
        existing.mkdir()

        # Create dialog
        dlg = ConflictDialog(
            filename="myfolder",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Should suggest myfolder (1)
        suggested = dlg.rename_edit.text()
        assert suggested == "myfolder (1)"


def test_suggest_rename_directory_with_conflicts(qapp):
    """Test rename suggestion for directories when conflicts exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing directories
        existing = Path(tmpdir) / "myfolder"
        existing.mkdir()

        (Path(tmpdir) / "myfolder (1)").mkdir()
        (Path(tmpdir) / "myfolder (2)").mkdir()

        # Create dialog
        dlg = ConflictDialog(
            filename="myfolder",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Should suggest myfolder (3)
        suggested = dlg.rename_edit.text()
        assert suggested == "myfolder (3)"


def test_suggest_rename_complex_filename(qapp):
    """Test rename suggestion with complex filenames containing dots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing file with multiple dots
        existing = Path(tmpdir) / "archive.tar.gz"
        existing.touch()

        (Path(tmpdir) / "archive.tar (1).gz").touch()

        # Create dialog
        dlg = ConflictDialog(
            filename="archive.tar.gz",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Should suggest archive.tar (2).gz (stem is "archive.tar", suffix is ".gz")
        suggested = dlg.rename_edit.text()
        assert suggested == "archive.tar (2).gz"


def test_rename_button_disabled_when_name_exists(qapp):
    """Test that the Rename button is disabled when entered name already exists."""
    from PyQt6.QtCore import QCoreApplication

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing files
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()

        conflict = Path(tmpdir) / "foo (1).txt"
        conflict.touch()

        # Create dialog
        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )
        dlg.show()  # Must show dialog for visibility to work properly
        QCoreApplication.processEvents()

        # Initially suggests foo (2).txt which doesn't exist - button should be enabled
        assert dlg.rename_edit.text() == "foo (2).txt"
        assert dlg.ok_btn.isEnabled()
        assert not dlg.name_conflict_warning.isVisible()

        # User changes to existing name - button should be disabled
        dlg.rename_edit.setText("foo (1).txt")
        QCoreApplication.processEvents()
        assert not dlg.ok_btn.isEnabled()
        assert dlg.name_conflict_warning.isVisible()

        # User changes to available name - button should be enabled again
        dlg.rename_edit.setText("foo (3).txt")
        QCoreApplication.processEvents()
        assert dlg.ok_btn.isEnabled()
        assert not dlg.name_conflict_warning.isVisible()


def test_warning_shows_for_existing_name(qapp):
    """Test that warning label appears when user enters existing name."""
    from PyQt6.QtCore import QCoreApplication

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing files
        existing = Path(tmpdir) / "test.txt"
        existing.touch()

        (Path(tmpdir) / "test (1).txt").touch()

        # Create dialog
        dlg = ConflictDialog(
            filename="test.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )
        dlg.show()  # Must show dialog for visibility to work properly
        QCoreApplication.processEvents()

        # Warning should not be visible initially (suggested name is available)
        assert not dlg.name_conflict_warning.isVisible()

        # Type an existing filename
        dlg.rename_edit.setText("test (1).txt")
        QCoreApplication.processEvents()

        # Warning should now be visible
        assert dlg.name_conflict_warning.isVisible()
        assert "already exists" in dlg.name_conflict_warning.text()


def test_rename_button_disabled_for_original_name(qapp):
    """Test that Rename button is disabled when entering the original conflicting name."""
    from PyQt6.QtCore import QCoreApplication

    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()

        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )
        dlg.show()  # Must show dialog for visibility to work properly
        QCoreApplication.processEvents()

        # Change to original name
        dlg.rename_edit.setText("foo.txt")
        QCoreApplication.processEvents()

        # Button should be disabled (can't rename to same name)
        assert not dlg.ok_btn.isEnabled()
        # Warning should NOT be visible (disabled for different reason - same as original)
        # The warning only shows when name != original but does exist
        assert not dlg.name_conflict_warning.isVisible()


def test_rename_button_disabled_for_empty_name(qapp):
    """Test that Rename button is disabled for empty input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "foo.txt"
        existing.touch()

        dlg = ConflictDialog(
            filename="foo.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing)
        )

        # Clear the field
        dlg.rename_edit.setText("")

        # Button should be disabled
        assert not dlg.ok_btn.isEnabled()
        # Warning should not be visible (different validation issue)
        assert not dlg.name_conflict_warning.isVisible()

