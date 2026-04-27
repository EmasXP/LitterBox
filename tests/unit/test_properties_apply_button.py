"""
Tests for the "Set as Default" (Apply) button placement and behavior in
the Properties dialog. The button used to live in the dialog's main button
row, where its purpose was unclear. It now belongs to the "Open With"
group box and is only enabled when a different application is selected.
"""
from unittest.mock import patch, MagicMock

import pytest

from core.application_manager import DesktopApplication
from ui.properties_dialog import PropertiesDialog


def _make_app(name: str, path: str) -> DesktopApplication:
    """Build a minimal DesktopApplication for tests."""
    app = MagicMock(spec=DesktopApplication)
    app.name = name
    app.path = path
    # Make equality based on .path so `app == default_app` works as in code
    app.__eq__ = lambda self, other: getattr(other, "path", None) == self.path
    app.__hash__ = lambda self: hash(self.path)
    return app


@pytest.fixture
def html_file(tmp_path):
    f = tmp_path / "test.html"
    f.write_text("<html></html>")
    return str(f)


def test_apply_button_lives_inside_open_with_group(qapp, qtbot, html_file):
    """The Apply/'Set as Default' button must be a child of the dialog
    (inside the Open With group), not in the bottom button row."""
    default_app = _make_app("Firefox", "/usr/share/applications/firefox.desktop")

    with patch("ui.properties_dialog.ApplicationManager") as MockMgr:
        mgr = MockMgr.return_value
        mgr.get_mime_type.return_value = "text/html"
        mgr.get_default_application.return_value = default_app
        mgr.get_ranked_applications_for_file.return_value = [default_app]

        dialog = PropertiesDialog(html_file)
        qtbot.addWidget(dialog)

        # The new button attribute exists for files
        assert hasattr(dialog, "apply_app_btn"), \
            "Files should expose apply_app_btn inside the Open With group"

        # Button label communicates intent clearly
        assert dialog.apply_app_btn.text() == "Set as Default"

        # Initial state: selection equals current default => disabled
        assert not dialog.apply_app_btn.isEnabled(), \
            "Apply button should start disabled when selection matches default"


def test_apply_button_not_present_for_folders(qapp, qtbot, tmp_path):
    """Folders have no Open With section, so no apply button should exist."""
    folder = tmp_path / "somedir"
    folder.mkdir()

    dialog = PropertiesDialog(str(folder))
    qtbot.addWidget(dialog)

    assert not hasattr(dialog, "apply_app_btn"), \
        "Folders should not have an apply_app_btn"


def test_apply_button_enables_when_different_app_selected(qapp, qtbot, html_file):
    """Selecting a non-default application enables the Apply button."""
    default_app = _make_app("Firefox", "/usr/share/applications/firefox.desktop")
    other_app = _make_app("Chromium", "/usr/share/applications/chromium.desktop")

    with patch("ui.properties_dialog.ApplicationManager") as MockMgr:
        mgr = MockMgr.return_value
        mgr.get_mime_type.return_value = "text/html"
        mgr.get_default_application.return_value = default_app
        mgr.get_ranked_applications_for_file.return_value = [default_app, other_app]

        dialog = PropertiesDialog(html_file)
        qtbot.addWidget(dialog)

        assert not dialog.apply_app_btn.isEnabled()

        # Select the non-default app -> button should enable
        idx = dialog.open_with_combo.findText("Chromium")
        assert idx != -1, "Chromium should be in the dropdown"
        dialog.open_with_combo.setCurrentIndex(idx)

        assert dialog.apply_app_btn.isEnabled(), \
            "Apply button should enable when a different application is selected"

        # Switch back to the default -> disabled again
        default_idx = dialog.open_with_combo.findText("Firefox (default)")
        dialog.open_with_combo.setCurrentIndex(default_idx)
        assert not dialog.apply_app_btn.isEnabled()
