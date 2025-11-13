"""
Unit tests for PlacesManager
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, 'src')

from core.places_manager import PlacesManager, PlaceItem


class TestPlaceItem:
    """Tests for PlaceItem class"""

    def test_place_item_creation(self):
        """Test creating a PlaceItem"""
        place = PlaceItem('Home', '/home/user', 'user-home', builtin=True)
        assert place.name == 'Home'
        assert place.path == '/home/user'
        assert place.icon == 'user-home'
        assert place.builtin is True

    def test_place_item_exists_true(self, tmp_path):
        """Test exists() returns True for existing directory"""
        place = PlaceItem('Test', str(tmp_path), builtin=False)
        assert place.exists() is True

    def test_place_item_exists_false(self):
        """Test exists() returns False for non-existent directory"""
        place = PlaceItem('Test', '/nonexistent/path', builtin=False)
        assert place.exists() is False

    def test_place_item_repr(self):
        """Test string representation"""
        place = PlaceItem('Home', '/home/user', builtin=True)
        repr_str = repr(place)
        assert 'PlaceItem' in repr_str
        assert 'Home' in repr_str
        assert '/home/user' in repr_str


class TestPlacesManager:
    """Tests for PlacesManager class"""

    def test_initialization(self):
        """Test PlacesManager initialization"""
        manager = PlacesManager()
        assert manager._xdg_dirs_cache is None
        assert manager._bookmarks_cache is None

    @patch('subprocess.run')
    def test_get_xdg_user_dir_success(self, mock_run):
        """Test getting XDG directory via xdg-user-dir command"""
        mock_run.return_value = MagicMock(returncode=0, stdout='/home/user/Desktop\n')

        manager = PlacesManager()
        result = manager.get_xdg_user_dir('DESKTOP')

        assert result == '/home/user/Desktop'
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_xdg_user_dir_returns_home(self, mock_run):
        """Test that xdg-user-dir returning HOME is filtered out"""
        home = str(Path.home())
        mock_run.return_value = MagicMock(returncode=0, stdout=f'{home}\n')

        manager = PlacesManager()
        result = manager.get_xdg_user_dir('DESKTOP')

        # Should return None since it's just HOME
        assert result is None

    @patch('subprocess.run')
    def test_get_xdg_user_dir_command_fails(self, mock_run):
        """Test handling xdg-user-dir command failure"""
        mock_run.return_value = MagicMock(returncode=1, stdout='')

        manager = PlacesManager()
        result = manager.get_xdg_user_dir('DESKTOP')

        assert result is None

    @patch('subprocess.run')
    def test_get_xdg_user_dir_timeout(self, mock_run):
        """Test handling xdg-user-dir timeout"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('xdg-user-dir', 2)

        manager = PlacesManager()
        result = manager.get_xdg_user_dir('DESKTOP')

        assert result is None

    def test_parse_user_dirs_file(self, tmp_path):
        """Test parsing user-dirs.dirs file"""
        # Create a temporary config file
        config_dir = tmp_path / '.config'
        config_dir.mkdir()
        user_dirs_file = config_dir / 'user-dirs.dirs'

        user_dirs_file.write_text("""
# Test config file
XDG_DESKTOP_DIR="$HOME/Desktop"
XDG_DOWNLOAD_DIR="$HOME/Downloads"
XDG_DOCUMENTS_DIR="/absolute/path/Documents"

# Comment line
XDG_MUSIC_DIR="$HOME/Music"
""")

        manager = PlacesManager()

        # Mock Path.home() to return our tmp_path
        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager._parse_user_dirs_file()

        assert 'XDG_DESKTOP_DIR' in result
        assert result['XDG_DESKTOP_DIR'] == str(tmp_path / 'Desktop')
        assert result['XDG_DOWNLOAD_DIR'] == str(tmp_path / 'Downloads')
        assert result['XDG_DOCUMENTS_DIR'] == '/absolute/path/Documents'
        assert 'XDG_MUSIC_DIR' in result

    def test_parse_user_dirs_file_missing(self):
        """Test parsing when user-dirs.dirs doesn't exist"""
        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=Path('/nonexistent')):
            result = manager._parse_user_dirs_file()

        assert result == {}

    def test_get_xdg_directories_includes_home(self):
        """Test that get_xdg_directories always includes Home"""
        manager = PlacesManager()
        places = manager.get_xdg_directories()

        # Should have at least Home and Root
        assert len(places) >= 2
        assert places[0].name == 'Home'
        assert places[0].path == str(Path.home())
        assert places[0].builtin is True

    def test_get_xdg_directories_includes_root(self):
        """Test that get_xdg_directories always includes Root"""
        manager = PlacesManager()
        places = manager.get_xdg_directories()

        # Root should be the last item
        assert places[-1].name == 'Root'
        assert places[-1].path == '/'
        assert places[-1].builtin is True

    def test_get_xdg_directories_caching(self):
        """Test that get_xdg_directories uses cache"""
        manager = PlacesManager()

        # First call
        places1 = manager.get_xdg_directories()

        # Second call should return same object (cached)
        places2 = manager.get_xdg_directories()

        assert places1 is places2

    def test_get_xdg_directories_force_refresh(self):
        """Test force_refresh bypasses cache"""
        manager = PlacesManager()

        # First call
        places1 = manager.get_xdg_directories()

        # Force refresh should return new object
        places2 = manager.get_xdg_directories(force_refresh=True)

        assert places1 is not places2

    def test_parse_gtk_bookmarks_simple(self, tmp_path):
        """Test parsing GTK bookmarks file"""
        # Create temporary bookmarks file
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'

        # Create some test directories
        test_dir1 = tmp_path / 'Project1'
        test_dir2 = tmp_path / 'Project2'
        test_dir1.mkdir()
        test_dir2.mkdir()

        bookmarks_file.write_text(f"""file://{test_dir1} My Project
file://{test_dir2}
""")

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            bookmarks = manager._parse_gtk_bookmarks()

        assert len(bookmarks) == 2
        assert bookmarks[0].name == 'My Project'
        assert bookmarks[0].path == str(test_dir1)
        assert bookmarks[0].builtin is False
        assert bookmarks[1].name == 'Project2'  # Uses directory name
        assert bookmarks[1].path == str(test_dir2)

    def test_parse_gtk_bookmarks_missing_file(self):
        """Test parsing when bookmarks file doesn't exist"""
        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=Path('/nonexistent')):
            bookmarks = manager._parse_gtk_bookmarks()

        assert bookmarks == []

    def test_parse_gtk_bookmarks_ignores_nonexistent(self, tmp_path):
        """Test that bookmarks for non-existent directories are ignored"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'

        bookmarks_file.write_text("""file:///nonexistent/path1 Test1
file:///nonexistent/path2
""")

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            bookmarks = manager._parse_gtk_bookmarks()

        # Should be empty since directories don't exist
        assert bookmarks == []

    def test_get_bookmarks_caching(self, tmp_path):
        """Test that get_bookmarks uses cache"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'
        bookmarks_file.write_text("")

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            bookmarks1 = manager.get_bookmarks()
            bookmarks2 = manager.get_bookmarks()

        assert bookmarks1 is bookmarks2

    def test_get_all_places_combines_xdg_and_bookmarks(self, tmp_path):
        """Test that get_all_places returns both XDG dirs and bookmarks"""
        manager = PlacesManager()

        # Mock both methods
        mock_xdg = [PlaceItem('Home', '/home/user', builtin=True)]
        mock_bookmarks = [PlaceItem('Project', '/home/user/project', builtin=False)]

        manager._xdg_dirs_cache = mock_xdg
        manager._bookmarks_cache = mock_bookmarks

        places = manager.get_all_places()

        assert len(places) == 2
        assert places[0] == mock_xdg[0]
        assert places[1] == mock_bookmarks[0]

    def test_add_bookmark_success(self, tmp_path):
        """Test adding a bookmark successfully"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)

        test_dir = tmp_path / 'TestProject'
        test_dir.mkdir()

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager.add_bookmark(str(test_dir), 'My Test Project')

        assert result is True

        # Verify bookmark was written
        bookmarks_file = config_dir / 'bookmarks'
        assert bookmarks_file.exists()
        content = bookmarks_file.read_text()
        assert f'file://{test_dir} My Test Project' in content

    def test_add_bookmark_uses_directory_name_if_no_label(self, tmp_path):
        """Test adding bookmark without label uses directory name"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)

        test_dir = tmp_path / 'ProjectName'
        test_dir.mkdir()

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager.add_bookmark(str(test_dir))

        assert result is True

        bookmarks_file = config_dir / 'bookmarks'
        content = bookmarks_file.read_text()
        assert f'file://{test_dir} ProjectName' in content

    def test_add_bookmark_fails_for_nonexistent(self, tmp_path):
        """Test adding bookmark for non-existent directory fails"""
        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager.add_bookmark('/nonexistent/path')

        assert result is False

    def test_add_bookmark_prevents_duplicates(self, tmp_path):
        """Test that duplicate bookmarks are not added"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'

        test_dir = tmp_path / 'TestProject'
        test_dir.mkdir()

        # Add initial bookmark
        bookmarks_file.write_text(f'file://{test_dir} Existing\n')

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager.add_bookmark(str(test_dir), 'New Label')

        # Should return False (already exists)
        assert result is False

    def test_remove_bookmark_success(self, tmp_path):
        """Test removing a bookmark successfully"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'

        test_dir1 = tmp_path / 'Project1'
        test_dir2 = tmp_path / 'Project2'
        test_dir1.mkdir()
        test_dir2.mkdir()

        # Create bookmarks
        bookmarks_file.write_text(f"""file://{test_dir1} Project 1
file://{test_dir2} Project 2
""")

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager.remove_bookmark(str(test_dir1))

        assert result is True

        # Verify bookmark was removed
        content = bookmarks_file.read_text()
        assert str(test_dir1) not in content
        assert str(test_dir2) in content

    def test_remove_bookmark_not_found(self, tmp_path):
        """Test removing non-existent bookmark returns False"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'
        bookmarks_file.write_text("")

        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=tmp_path):
            result = manager.remove_bookmark('/some/path')

        assert result is False

    def test_remove_bookmark_no_file(self):
        """Test removing bookmark when file doesn't exist"""
        manager = PlacesManager()

        with patch('pathlib.Path.home', return_value=Path('/nonexistent')):
            result = manager.remove_bookmark('/some/path')

        assert result is False

    def test_clear_cache(self):
        """Test that clear_cache resets all caches"""
        manager = PlacesManager()

        # Set up some cache data
        manager._xdg_dirs_cache = [PlaceItem('Test', '/test', builtin=True)]
        manager._bookmarks_cache = [PlaceItem('Bookmark', '/bookmark', builtin=False)]

        # Clear cache
        manager.clear_cache()

        assert manager._xdg_dirs_cache is None
        assert manager._bookmarks_cache is None

    def test_add_bookmark_clears_cache(self, tmp_path):
        """Test that adding a bookmark clears the cache"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)

        test_dir = tmp_path / 'TestProject'
        test_dir.mkdir()

        manager = PlacesManager()
        manager._bookmarks_cache = []  # Set some cached data

        with patch('pathlib.Path.home', return_value=tmp_path):
            manager.add_bookmark(str(test_dir))

        # Cache should be cleared
        assert manager._bookmarks_cache is None

    def test_remove_bookmark_clears_cache(self, tmp_path):
        """Test that removing a bookmark clears the cache"""
        config_dir = tmp_path / '.config' / 'gtk-3.0'
        config_dir.mkdir(parents=True)
        bookmarks_file = config_dir / 'bookmarks'

        test_dir = tmp_path / 'TestProject'
        test_dir.mkdir()

        bookmarks_file.write_text(f'file://{test_dir} Test\n')

        manager = PlacesManager()
        manager._bookmarks_cache = []  # Set some cached data

        with patch('pathlib.Path.home', return_value=tmp_path):
            manager.remove_bookmark(str(test_dir))

        # Cache should be cleared
        assert manager._bookmarks_cache is None
