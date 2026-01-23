"""
Tests for "Open (AppName)" feature in context menu
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import QPoint
from ui.main_window import FileTab


def test_open_shows_app_name_for_regular_file(qapp, monkeypatch, tmp_path):
    """Test that Open menu shows app name for regular files"""
    # Create a test file
    test_file = str(tmp_path / "test.txt")
    with open(test_file, 'w') as f:
        f.write("test content")

    # Create a mock application manager that returns a known app
    mock_app = MagicMock()
    mock_app.name = "Kate"

    mock_app_manager = MagicMock()
    mock_app_manager.get_default_application.return_value = mock_app

    # Patch ApplicationManager
    with patch('core.application_manager.ApplicationManager', return_value=mock_app_manager):
        tab = FileTab(tmp_path)

        # Get default app name
        app_name = tab.get_default_app_name(test_file)

        assert app_name == "Kate"


def test_open_does_not_show_app_name_for_folder(qapp, tmp_path):
    """Test that Open menu does NOT show app name for folders"""
    # Create a subfolder
    subfolder = str(tmp_path / "subfolder")
    os.makedirs(subfolder)

    tab = FileTab(tmp_path)

    # Get default app name - should be None for folders
    app_name = tab.get_default_app_name(subfolder)

    assert app_name is None


def test_open_does_not_show_app_name_for_executable(qapp, tmp_path):
    """Test that Open menu does NOT show app name for executable files"""
    # Create an executable script
    exec_file = str(tmp_path / "test.sh")
    with open(exec_file, 'w') as f:
        f.write("#!/bin/bash\necho test")
    os.chmod(exec_file, 0o755)

    tab = FileTab(tmp_path)

    # Get default app name - should be None for executables
    app_name = tab.get_default_app_name(exec_file)

    assert app_name is None


def test_app_name_cache_works(qapp, monkeypatch, tmp_path):
    """Test that the app name cache works properly"""
    # Create a test file
    test_file = str(tmp_path / "test.txt")
    with open(test_file, 'w') as f:
        f.write("test content")

    # Create a mock application manager
    mock_app = MagicMock()
    mock_app.name = "Kate"

    mock_app_manager = MagicMock()
    mock_app_manager.get_default_application.return_value = mock_app

    with patch('core.application_manager.ApplicationManager', return_value=mock_app_manager):
        tab = FileTab(tmp_path)

        # First call - should query ApplicationManager
        app_name1 = tab.get_default_app_name(test_file)
        assert app_name1 == "Kate"
        assert mock_app_manager.get_default_application.call_count == 1

        # Second call - should use cache
        app_name2 = tab.get_default_app_name(test_file)
        assert app_name2 == "Kate"
        # Should still be 1 - no additional call
        assert mock_app_manager.get_default_application.call_count == 1


def test_cache_cleared_on_navigation(qapp, monkeypatch, tmp_path):
    """Test that app name cache is cleared when navigating to a new directory"""
    # Create test files in two directories
    dir1 = str(tmp_path)
    test_file1 = str(tmp_path / "test1.txt")
    with open(test_file1, 'w') as f:
        f.write("test1")

    dir2 = str(tmp_path / "subdir")
    os.makedirs(dir2)
    test_file2 = str(Path(dir2) / "test2.txt")
    with open(test_file2, 'w') as f:
        f.write("test2")

    # Create mock
    mock_app = MagicMock()
    mock_app.name = "Kate"
    mock_app_manager = MagicMock()
    mock_app_manager.get_default_application.return_value = mock_app

    with patch('core.application_manager.ApplicationManager', return_value=mock_app_manager):
        tab = FileTab(dir1)

        # Get app name for file in dir1
        app_name1 = tab.get_default_app_name(test_file1)
        assert app_name1 == "Kate"
        assert len(tab._default_app_cache) == 1

        # Navigate to dir2
        tab.navigate_to(dir2)

        # Cache should be cleared
        assert len(tab._default_app_cache) == 0


def test_context_menu_shows_app_name(qapp, monkeypatch, tmp_path):
    """Test that context menu actually shows 'Open (AppName)' text"""
    # Create a test file
    test_file = str(tmp_path / "test.txt")
    with open(test_file, 'w') as f:
        f.write("test content")

    # Create a mock application manager
    mock_app = MagicMock()
    mock_app.name = "Kate"
    mock_app_manager = MagicMock()
    mock_app_manager.get_default_application.return_value = mock_app

    captured_menus = []

    # Capture the menu when it's shown
    original_exec = QMenu.exec
    def capture_exec(self, *args, **kwargs):
        captured_menus.append(self)
        # Don't actually show the menu
        return None

    monkeypatch.setattr(QMenu, 'exec', capture_exec)

    with patch('core.application_manager.ApplicationManager', return_value=mock_app_manager):
        tab = FileTab(tmp_path)

        # Trigger context menu
        tab.show_context_menu(test_file, QPoint(0, 0))

        # Check that a menu was shown
        assert len(captured_menus) > 0
        menu = captured_menus[-1]

        # Find the "Open" action
        actions = menu.actions()
        open_action = None
        for action in actions:
            if action.text().startswith("Open"):
                open_action = action
                break

        assert open_action is not None
        assert open_action.text() == "Open (Kate)"


def test_context_menu_plain_open_for_folder(qapp, monkeypatch, tmp_path):
    """Test that context menu shows plain 'Open' for folders"""
    # Create a subfolder
    subfolder = str(tmp_path / "subfolder")
    os.makedirs(subfolder)

    captured_menus = []

    # Capture the menu
    original_exec = QMenu.exec
    def capture_exec(self, *args, **kwargs):
        captured_menus.append(self)
        return None

    monkeypatch.setattr(QMenu, 'exec', capture_exec)

    tab = FileTab(tmp_path)

    # Trigger context menu
    tab.show_context_menu(subfolder, QPoint(0, 0))

    # Check that menu shows plain "Open"
    assert len(captured_menus) > 0
    menu = captured_menus[-1]

    actions = menu.actions()
    open_action = None
    for action in actions:
        if action.text().startswith("Open"):
            open_action = action
            break

    assert open_action is not None
    assert open_action.text() == "Open"


def test_context_menu_plain_open_for_executable(qapp, monkeypatch, tmp_path):
    """Test that context menu shows plain 'Open' for executable files"""
    # Create an executable script
    exec_file = str(tmp_path / "test.sh")
    with open(exec_file, 'w') as f:
        f.write("#!/bin/bash\necho test")
    os.chmod(exec_file, 0o755)

    captured_menus = []

    # Capture the menu
    def capture_exec(self, *args, **kwargs):
        captured_menus.append(self)
        return None

    monkeypatch.setattr(QMenu, 'exec', capture_exec)

    tab = FileTab(tmp_path)

    # Trigger context menu
    tab.show_context_menu(exec_file, QPoint(0, 0))

    # Check that menu shows plain "Open"
    assert len(captured_menus) > 0
    menu = captured_menus[-1]

    actions = menu.actions()
    open_action = None
    for action in actions:
        if action.text().startswith("Open"):
            open_action = action
            break

    assert open_action is not None
    assert open_action.text() == "Open"


def test_no_app_name_when_no_default_found(qapp, monkeypatch, tmp_path):
    """Test that Open shows plain text when no default app is found"""
    # Create a test file
    test_file = str(tmp_path / "test.xyz")
    with open(test_file, 'w') as f:
        f.write("test content")

    # Mock ApplicationManager to return None (no default app)
    mock_app_manager = MagicMock()
    mock_app_manager.get_default_application.return_value = None

    captured_menus = []

    def capture_exec(self, *args, **kwargs):
        captured_menus.append(self)
        return None

    monkeypatch.setattr(QMenu, 'exec', capture_exec)

    with patch('core.application_manager.ApplicationManager', return_value=mock_app_manager):
        tab = FileTab(tmp_path)

        # Trigger context menu
        tab.show_context_menu(test_file, QPoint(0, 0))

        # Check that menu shows plain "Open"
        assert len(captured_menus) > 0
        menu = captured_menus[-1]

        actions = menu.actions()
        open_action = None
        for action in actions:
            if action.text().startswith("Open"):
                open_action = action
                break

        assert open_action is not None
        assert open_action.text() == "Open"


def test_graceful_handling_of_app_manager_errors(qapp, monkeypatch, tmp_path):
    """Test that errors from ApplicationManager are handled gracefully"""
    # Create a test file
    test_file = str(tmp_path / "test.txt")
    with open(test_file, 'w') as f:
        f.write("test content")

    # Mock ApplicationManager to raise an exception
    mock_app_manager = MagicMock()
    mock_app_manager.get_default_application.side_effect = Exception("Test error")

    with patch('core.application_manager.ApplicationManager', return_value=mock_app_manager):
        tab = FileTab(tmp_path)

        # Should not raise an exception
        app_name = tab.get_default_app_name(test_file)

        # Should return None and cache the None value
        assert app_name is None
        assert test_file in tab._default_app_cache
        assert tab._default_app_cache[test_file] is None
