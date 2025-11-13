"""
Unit tests for PlacesButton integration with PlacesManager
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, 'src')

from ui.places_button import PlacesButton
from core.places_manager import PlaceItem


class TestPlacesButton:
    """Tests for PlacesButton"""

    def test_places_button_creation(self, qapp):
        """Test creating a PlacesButton"""
        button = PlacesButton()
        assert button is not None
        # Button should have a tooltip (icon may be null in test environment)
        assert button.toolTip() == "Places"

    def test_places_button_has_menu(self, qapp):
        """Test that PlacesButton has a menu"""
        button = PlacesButton()
        menu = button.menu()
        assert menu is not None
        # Menu should have at least Home and Root
        assert len(menu.actions()) >= 2

    def test_places_button_uses_places_manager(self, qapp):
        """Test that PlacesButton uses PlacesManager"""
        button = PlacesButton()
        assert button.places_manager is not None

    def test_places_button_includes_xdg_directories(self, qapp):
        """Test that menu includes XDG directories"""
        button = PlacesButton()
        menu = button.menu()
        actions = menu.actions()

        # Check that Home is included
        action_texts = [action.text() for action in actions if not action.isSeparator()]
        assert 'Home' in action_texts
        assert 'Root' in action_texts

    def test_places_button_emits_signal_on_selection(self, qapp):
        """Test that selecting a place emits the place_selected signal"""
        button = PlacesButton()

        # Mock the signal
        signal_emitted = []
        button.place_selected.connect(lambda path: signal_emitted.append(path))

        # Trigger the first non-separator action (should be Home)
        menu = button.menu()
        actions = [a for a in menu.actions() if not a.isSeparator()]
        if actions:
            actions[0].trigger()

            # Should have emitted a signal with a path
            assert len(signal_emitted) == 1
            assert signal_emitted[0]  # Should be a non-empty path

    def test_places_button_separates_builtin_and_bookmarks(self, qapp, tmp_path):
        """Test that menu separates builtin places from bookmarks"""
        # Create a test bookmark
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'

        test_dir = tmp_path / 'TestBookmark'
        test_dir.mkdir()

        bookmarks_file.write_text(f'file://{test_dir} Test Bookmark\n')

        with patch('pathlib.Path.home', return_value=tmp_path):
            button = PlacesButton()
            menu = button.menu()
            actions = menu.actions()

            # Should have at least one separator between builtin and bookmarks
            separators = [a for a in actions if a.isSeparator()]
            assert len(separators) >= 1

    def test_refresh_places_clears_cache(self, qapp):
        """Test that refresh_places clears the cache and rebuilds menu"""
        button = PlacesButton()

        # Get initial menu
        initial_menu = button.menu()
        initial_action_count = len(initial_menu.actions())

        # Set some cache
        button.places_manager._xdg_dirs_cache = []
        button.places_manager._bookmarks_cache = []

        # Refresh (this will rebuild the menu and repopulate cache)
        button.refresh_places()

        # After refresh, cache should be repopulated (not empty)
        # and menu should be rebuilt
        new_menu = button.menu()
        new_action_count = len(new_menu.actions())

        # Menu should still have content after refresh
        assert new_action_count > 0
        # XDG cache should be repopulated
        assert button.places_manager._xdg_dirs_cache is not None
        assert len(button.places_manager._xdg_dirs_cache) > 0

    def test_places_button_handles_no_bookmarks(self, qapp, tmp_path):
        """Test that PlacesButton works when there are no bookmarks"""
        with patch('pathlib.Path.home', return_value=tmp_path):
            button = PlacesButton()
            menu = button.menu()

            # Should still have XDG directories
            actions = [a for a in menu.actions() if not a.isSeparator()]
            assert len(actions) >= 2  # At least Home and Root

    def test_places_menu_items_have_icon_names(self, qapp):
        """Test that menu items attempt to set icons from PlaceItem icon names"""
        button = PlacesButton()
        menu = button.menu()

        # Get all places to check their icon names
        places = button.places_manager.get_all_places()

        # Verify that places have icon names defined
        home_place = next((p for p in places if p.name == 'Home'), None)
        assert home_place is not None
        assert home_place.icon == 'user-home'

        root_place = next((p for p in places if p.name == 'Root'), None)
        assert root_place is not None
        assert root_place.icon == 'drive-harddisk'
