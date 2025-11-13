import pytest
from unittest.mock import patch, MagicMock
from src.core.application_manager import ApplicationManager, DesktopApplication

@pytest.fixture
def mock_desktop_application_factory():
    """Factory to create mock DesktopApplication objects."""
    def _create_mock_app(path, name, exec_cmd, mimetypes, categories=None):
        app = MagicMock(spec=DesktopApplication)
        app.path = path
        app.name = name
        app.exec_command = exec_cmd
        app.mime_types = mimetypes
        app.categories = categories if categories is not None else []
        app.should_be_visible.return_value = True
        # Make the mock hashable by its path, which is unique
        app.__hash__ = lambda: hash(app.path)
        app.__eq__ = lambda other: isinstance(other, MagicMock) and app.path == other.path
        return app
    return _create_mock_app

def test_duplicate_applications_are_removed(mock_desktop_application_factory):
    """
    Test that get_ranked_applications_for_file removes duplicate applications
    that have different .desktop paths but the same name and exec command.
    """
    # Arrange
    app1_path = "/usr/share/applications/app.desktop"
    app2_path = "/home/user/.local/share/applications/app.desktop" # Same app, different path
    app3_path = "/usr/share/applications/another_app.desktop"

    # Create mock applications
    app1 = mock_desktop_application_factory(
        app1_path, "Awesome Editor", "awesome-editor %f", ["text/plain"]
    )
    # This is a duplicate of app1 (same name and exec)
    app2 = mock_desktop_application_factory(
        app2_path, "Awesome Editor", "awesome-editor %f", ["text/plain"]
    )
    # This is a different application
    app3 = mock_desktop_application_factory(
        app3_path, "Another App", "another-app %f", ["text/plain"]
    )

    mock_apps = [app1, app2, app3]

    manager = ApplicationManager()

    # Act
    with patch.object(manager, '_get_all_applications', return_value=mock_apps):
        with patch.object(manager, '_get_mime_types_for_file', return_value=["text/plain"]):
            with patch.object(manager, '_get_system_default_for_mime_type', return_value=None):
                ranked_apps = manager.get_ranked_applications_for_file("dummy.txt")

    # Assert
    assert len(ranked_apps) == 2, "Duplicate applications should have been removed"

    app_names = [app.name for app in ranked_apps]
    assert "Awesome Editor" in app_names
    assert "Another App" in app_names

    # Check that only one instance of "Awesome Editor" is present
    awesome_editor_instances = [app for app in ranked_apps if app.name == "Awesome Editor"]
    assert len(awesome_editor_instances) == 1
