"""
Places management for LitterBox

Implements XDG User Directories standard and GTK bookmarks support,
following the same patterns used by Nautilus, Dolphin, and other Linux file managers.
"""
import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from urllib.parse import unquote, urlparse


class PlaceItem:
    """Represents a place (directory) in the sidebar"""

    def __init__(self, name: str, path: str, icon: Optional[str] = None, builtin: bool = False):
        """
        Args:
            name: Display name for the place
            path: Absolute path to the directory
            icon: Optional icon name (for future use)
            builtin: True if this is a standard XDG directory
        """
        self.name = name
        self.path = path
        self.icon = icon
        self.builtin = builtin

    def exists(self) -> bool:
        """Check if the place directory exists"""
        return Path(self.path).exists()

    def __repr__(self):
        return f"PlaceItem(name={self.name!r}, path={self.path!r}, builtin={self.builtin})"


class PlacesManager:
    """
    Manages the Places sidebar entries using XDG standards.

    This follows the freedesktop.org XDG User Directories specification:
    - Uses xdg-user-dir command to get standard directories
    - Reads ~/.config/user-dirs.dirs as fallback
    - Supports GTK bookmarks from ~/.config/gtk-3.0/bookmarks
    - Allows custom bookmarks (planned for future)

    Standard XDG directories include:
    - DESKTOP
    - DOCUMENTS
    - DOWNLOAD
    - MUSIC
    - PICTURES
    - VIDEOS
    - TEMPLATES (optional)
    - PUBLICSHARE (optional)
    """

    # Standard XDG directory types in the order they should appear
    XDG_DIRS = [
        ('DESKTOP', 'Desktop', 'user-desktop'),
        ('DOCUMENTS', 'Documents', 'folder-documents'),
        ('DOWNLOAD', 'Downloads', 'folder-downloads'),
        ('MUSIC', 'Music', 'folder-music'),
        ('PICTURES', 'Pictures', 'folder-pictures'),
        ('VIDEOS', 'Videos', 'folder-videos'),
        ('TEMPLATES', 'Templates', 'folder-templates'),
        ('PUBLICSHARE', 'Public', 'folder-publicshare'),
    ]

    def __init__(self):
        self._xdg_dirs_cache: Optional[List[PlaceItem]] = None
        self._bookmarks_cache: Optional[List[PlaceItem]] = None

    def get_xdg_user_dir(self, dir_type: str) -> Optional[str]:
        """
        Get an XDG user directory path using xdg-user-dir command.

        Args:
            dir_type: XDG directory type (e.g., 'DESKTOP', 'DOCUMENTS')

        Returns:
            Absolute path to the directory, or None if not available
        """
        try:
            result = subprocess.run(
                ['xdg-user-dir', dir_type],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )

            if result.returncode == 0:
                path = result.stdout.strip()
                # xdg-user-dir returns the home directory if the type is not configured
                # We check if it's different from HOME to avoid duplicates
                home = str(Path.home())
                if path and path != home:
                    return path

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        return None

    def _parse_user_dirs_file(self) -> dict:
        """
        Parse ~/.config/user-dirs.dirs file as fallback.

        Returns:
            Dictionary mapping XDG_*_DIR to paths
        """
        dirs = {}
        config_file = Path.home() / '.config' / 'user-dirs.dirs'

        if not config_file.exists():
            return dirs

        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Parse lines like: XDG_DESKTOP_DIR="$HOME/Desktop"
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')

                        # Expand $HOME
                        if value.startswith('$HOME/'):
                            value = str(Path.home() / value[6:])

                        dirs[key] = value

        except (OSError, IOError):
            pass

        return dirs

    def get_xdg_directories(self, force_refresh: bool = False) -> List[PlaceItem]:
        """
        Get all XDG user directories.

        Args:
            force_refresh: If True, bypass cache and re-fetch directories

        Returns:
            List of PlaceItem objects for XDG directories that exist
        """
        if self._xdg_dirs_cache is not None and not force_refresh:
            return self._xdg_dirs_cache

        places = []

        # Always include Home first
        home = str(Path.home())
        places.append(PlaceItem('Home', home, 'user-home', builtin=True))

        # Try xdg-user-dir command first, fall back to parsing config file
        user_dirs_config = self._parse_user_dirs_file()

        for dir_type, default_name, icon in self.XDG_DIRS:
            # Try xdg-user-dir command
            path = self.get_xdg_user_dir(dir_type)

            # Fallback to config file
            if not path:
                config_key = f'XDG_{dir_type}_DIR'
                path = user_dirs_config.get(config_key)

            # Fallback to default location
            if not path:
                path = str(Path.home() / default_name)

            # Only include if directory exists and is not the home directory
            if path and path != home and Path(path).exists():
                # Use the actual directory name, not the default name
                actual_name = Path(path).name
                places.append(PlaceItem(actual_name, path, icon, builtin=True))

        # Always include Root at the end
        places.append(PlaceItem('Root', '/', 'drive-harddisk', builtin=True))

        self._xdg_dirs_cache = places
        return places

    def _parse_gtk_bookmarks(self) -> List[PlaceItem]:
        """
        Parse GTK bookmarks file (~/.config/gtk-3.0/bookmarks).

        GTK bookmarks format is one bookmark per line:
        file:///path/to/directory [optional label]

        Returns:
            List of PlaceItem objects from bookmarks
        """
        bookmarks = []
        bookmarks_file = Path.home() / '.config' / 'gtk-3.0' / 'bookmarks'

        if not bookmarks_file.exists():
            return bookmarks

        try:
            with open(bookmarks_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Split into URI and optional label
                    parts = line.split(None, 1)
                    uri = parts[0]
                    label = parts[1] if len(parts) > 1 else None

                    # Parse file:// URI
                    if uri.startswith('file://'):
                        try:
                            parsed = urlparse(uri)
                            path = unquote(parsed.path)

                            # Use label if provided, otherwise use directory name
                            if not label:
                                label = Path(path).name

                            # Only add if directory exists
                            if Path(path).is_dir():
                                bookmarks.append(PlaceItem(label, path, 'folder', builtin=False))

                        except (ValueError, OSError):
                            continue

        except (OSError, IOError):
            pass

        return bookmarks

    def get_bookmarks(self, force_refresh: bool = False) -> List[PlaceItem]:
        """
        Get user bookmarks from GTK bookmarks file.

        Args:
            force_refresh: If True, bypass cache and re-read bookmarks

        Returns:
            List of PlaceItem objects from bookmarks
        """
        if self._bookmarks_cache is not None and not force_refresh:
            return self._bookmarks_cache

        self._bookmarks_cache = self._parse_gtk_bookmarks()
        return self._bookmarks_cache

    def get_all_places(self, force_refresh: bool = False) -> List[PlaceItem]:
        """
        Get all places: XDG directories + bookmarks.

        Args:
            force_refresh: If True, bypass cache and re-fetch all places

        Returns:
            List of all PlaceItem objects
        """
        places = []

        # XDG directories first
        places.extend(self.get_xdg_directories(force_refresh))

        # Then bookmarks
        bookmarks = self.get_bookmarks(force_refresh)
        if bookmarks:
            places.extend(bookmarks)

        return places

    def add_bookmark(self, path: str, label: Optional[str] = None) -> bool:
        """
        Add a bookmark to GTK bookmarks file.

        Args:
            path: Absolute path to directory
            label: Optional custom label (defaults to directory name)

        Returns:
            True if bookmark was added successfully
        """
        path_obj = Path(path)

        # Validate path
        if not path_obj.exists() or not path_obj.is_dir():
            return False

        # Make sure we have an absolute path
        path = str(path_obj.resolve())

        # Determine label
        if not label:
            label = path_obj.name

        # Create bookmarks directory if needed
        bookmarks_dir = Path.home() / '.config' / 'gtk-3.0'
        bookmarks_dir.mkdir(parents=True, exist_ok=True)

        bookmarks_file = bookmarks_dir / 'bookmarks'

        try:
            # Check if bookmark already exists
            existing_bookmarks = []
            if bookmarks_file.exists():
                with open(bookmarks_file, 'r') as f:
                    existing_bookmarks = [line.strip() for line in f if line.strip()]

            # Create new bookmark entry
            new_bookmark = f"file://{path} {label}"

            # Check if this path is already bookmarked
            for bookmark in existing_bookmarks:
                if bookmark.startswith(f"file://{path} ") or bookmark == f"file://{path}":
                    return False  # Already exists

            # Append new bookmark
            with open(bookmarks_file, 'a') as f:
                if existing_bookmarks and not existing_bookmarks[-1].endswith('\n'):
                    f.write('\n')
                f.write(new_bookmark + '\n')

            # Clear cache to force refresh
            self._bookmarks_cache = None

            return True

        except (OSError, IOError):
            return False

    def remove_bookmark(self, path: str) -> bool:
        """
        Remove a bookmark from GTK bookmarks file.

        Args:
            path: Absolute path to the bookmarked directory

        Returns:
            True if bookmark was removed successfully
        """
        bookmarks_file = Path.home() / '.config' / 'gtk-3.0' / 'bookmarks'

        if not bookmarks_file.exists():
            return False

        try:
            # Read all bookmarks
            with open(bookmarks_file, 'r') as f:
                bookmarks = [line.strip() for line in f if line.strip()]

            # Filter out the bookmark to remove
            path = str(Path(path).resolve())
            new_bookmarks = [
                b for b in bookmarks
                if not (b.startswith(f"file://{path} ") or b == f"file://{path}")
            ]

            # If nothing changed, bookmark wasn't found
            if len(new_bookmarks) == len(bookmarks):
                return False

            # Write back the filtered bookmarks
            with open(bookmarks_file, 'w') as f:
                for bookmark in new_bookmarks:
                    f.write(bookmark + '\n')

            # Clear cache to force refresh
            self._bookmarks_cache = None

            return True

        except (OSError, IOError):
            return False

    def clear_cache(self):
        """Clear all cached data"""
        self._xdg_dirs_cache = None
        self._bookmarks_cache = None
