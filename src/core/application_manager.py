"""
Application manager for handling MIME types and desktop applications
"""
import subprocess
import os
from pathlib import Path
import configparser
import mimetypes
import re
from typing import List, Dict, Optional, Tuple, Iterable
import glob


class DesktopApplication:
    """Represents a desktop application"""

    def __init__(self, desktop_file_path: str):
        self.path = desktop_file_path
        self.name = ""
        self.exec_command = ""
        self.icon = ""
        self.mime_types = []
        self.categories = []
        self.no_display = False
        self.hidden = False

        self._parse_desktop_file()

    def _parse_desktop_file(self):
        """Parse the .desktop file"""
        try:
            config = configparser.ConfigParser(interpolation=None)
            # Read with UTF-8 encoding and handle special characters
            config.read(self.path, encoding='utf-8')

            if 'Desktop Entry' not in config:
                return

            entry = config['Desktop Entry']

            self.name = entry.get('Name', '')
            self.exec_command = entry.get('Exec', '')
            self.icon = entry.get('Icon', '')

            # Handle boolean fields more carefully
            try:
                self.no_display = entry.getboolean('NoDisplay', False)
            except ValueError:
                self.no_display = entry.get('NoDisplay', '').lower() in ['true', '1', 'yes']

            try:
                self.hidden = entry.getboolean('Hidden', False)
            except ValueError:
                self.hidden = entry.get('Hidden', '').lower() in ['true', '1', 'yes']

            # Parse MIME types
            mime_types_str = entry.get('MimeType', '')
            if mime_types_str:
                self.mime_types = [mt.strip() for mt in mime_types_str.split(';') if mt.strip()]

            # Parse categories
            categories_str = entry.get('Categories', '')
            if categories_str:
                self.categories = [cat.strip() for cat in categories_str.split(';') if cat.strip()]

        except Exception as e:
            # If parsing fails, leave fields empty
            # Suppress common parsing errors for invalid desktop files
            pass

    def can_handle_mime_type(self, mime_type: str) -> bool:
        """Check if this application can handle the given MIME type"""
        return mime_type in self.mime_types

    def should_be_visible(self) -> bool:
        """Check if this application should be visible in menus"""
        return bool(not (self.no_display or self.hidden) and self.name and self.exec_command)

    def get_command_for_file(self, file_path: str) -> List[str]:
        """Get the command to run this application with the given file"""
        if not self.exec_command:
            return []

        # Parse the Exec field and substitute field codes
        # %f - single file, %F - multiple files, %u - single URL, %U - multiple URLs
        # For simplicity, we'll handle %f and %F, and treat URLs as files

        command = self.exec_command

        # Remove field codes we don't handle
        command = re.sub(r'%[icdnNvmkD]', '', command)

        # Handle file arguments
        if '%f' in command or '%F' in command:
            command = re.sub(r'%[fF]', f'"{file_path}"', command)
        elif '%u' in command or '%U' in command:
            command = re.sub(r'%[uU]', f'"{file_path}"', command)
        else:
            # If no field codes, append the file path
            command = f"{command} \"{file_path}\""

        # Split command into arguments (simple split, doesn't handle complex quoting)
        import shlex
        try:
            return shlex.split(command)
        except ValueError:
            # Fallback to simple split if shlex fails
            return command.split()


class ApplicationManager:
    """Manages desktop applications and MIME types.

    Improvements vs initial implementation:
    - Ranking & heuristic expansion: For certain MIME families (e.g. text/*) also
        propose apps that handle generic text/plain when specific subtype list is small.
    - Office documents: If ODF document types return very few matches, also include
        Office / WordProcessor category apps that can generally handle them.
    - Dependency injection of extra desktop directories (useful for testing) to allow
        constructing ephemeral .desktop files without touching system paths.
    """

    def __init__(self, extra_desktop_dirs: Optional[Iterable[str]] = None):
            self._applications_cache: Optional[List[DesktopApplication]] = None
            self._mime_cache: Dict[str, List[DesktopApplication]] = {}
            self._rank_cache: Dict[Tuple[str, Optional[str]], List[DesktopApplication]] = {}
            self._extra_desktop_dirs = list(extra_desktop_dirs) if extra_desktop_dirs else []
            mimetypes.init()

    def get_mime_type(self, file_path: str) -> str:
        """Get MIME type for a file"""
        try:
            # Try using xdg-mime first (more accurate)
            result = subprocess.run(
                ['xdg-mime', 'query', 'filetype', file_path],
                capture_output=True, text=True, check=True
            )
            mime_type = result.stdout.strip()
            if mime_type and mime_type != 'application/octet-stream':
                return mime_type
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Fallback to Python's mimetypes module
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type

        # Default fallback
        return 'application/octet-stream'

    def get_default_application(self, file_path: str) -> Optional[DesktopApplication]:
        """Get the default application for a file"""
        mime_type = self.get_mime_type(file_path)

        try:
            # Query xdg-mime for default application
            result = subprocess.run(
                ['xdg-mime', 'query', 'default', mime_type],
                capture_output=True, text=True, check=True
            )
            desktop_file = result.stdout.strip()

            if desktop_file:
                # Find the full path to the desktop file
                desktop_paths = [
                    '/usr/share/applications',
                    '/usr/local/share/applications',
                    os.path.expanduser('~/.local/share/applications')
                ]

                for desktop_dir in desktop_paths:
                    desktop_path = os.path.join(desktop_dir, desktop_file)
                    if os.path.exists(desktop_path):
                        app = DesktopApplication(desktop_path)
                        if app.should_be_visible():
                            return app

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def get_applications_for_mime_type(self, mime_type: str) -> List[DesktopApplication]:
        """Get all applications that explicitly declare support for a MIME type.

        (Exact matches only, no heuristics.)
        """
        if mime_type in self._mime_cache:
            return self._mime_cache[mime_type]

        apps: List[DesktopApplication] = []
        for app in self._get_all_applications():
            if app.should_be_visible() and app.can_handle_mime_type(mime_type):
                apps.append(app)
        apps.sort(key=lambda a: a.name.lower())
        self._mime_cache[mime_type] = apps
        return apps

    def get_applications_for_file(self, file_path: str) -> List[DesktopApplication]:
        """Backward compatible: returns ONLY exact MIME matches for the file."""
        mime_type = self.get_mime_type(file_path)
        return self.get_applications_for_mime_type(mime_type)

    # --- Enhanced ranking / heuristic discovery ---------------------------------
    def get_ranked_applications_for_file(self, file_path: str) -> List[DesktopApplication]:
        """Return a richer, ranked list of suitable applications.

        Strategy:
        1. Start with exact MIME matches.
        2. If result set is small, expand with heuristics:
           - text/* files: include apps advertising text/plain or other text/* subtypes.
           - ODF documents (application/vnd.oasis.opendocument.*): include Office / WordProcessor
             category apps that advertise ANY ODF text/document MIME.
        3. Score apps (higher = better):
           +50 exact match
           +15 same primary type (e.g. text/) match of any subtype
           +20 generic text/plain when file is text/* and no exact support
           +15 Office category for ODF docs
           +5  Editor heuristic (exec contains one of known editor names) for text/*
        4. Stable sort by (-score, name). Deduplicate while preserving highest score.
        """
        mime_type = self.get_mime_type(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        cache_key = (mime_type, file_ext)
        if cache_key in self._rank_cache:
            return self._rank_cache[cache_key]

        primary = mime_type.split('/')[0]
        exact_apps = {app.path: app for app in self.get_applications_for_mime_type(mime_type)}
        all_apps = self._get_all_applications()

        # Build candidate set (start with exact)
        candidates: Dict[str, Tuple[DesktopApplication, int]] = {}

        def add_with_score(app: DesktopApplication, score: int):
            prev = candidates.get(app.path)
            if prev is None or score > prev[1]:  # keep best score
                candidates[app.path] = (app, score)

        # Seed with exact matches
        for app in exact_apps.values():
            add_with_score(app, 50)

        # Heuristics triggers
        is_text = primary == 'text'
        is_odf = mime_type.startswith('application/vnd.oasis.opendocument')
        # Collect family of ODF text mime variants we consider equivalent for ranking
        odf_related = set()
        if is_odf:
            base_parts = mime_type.split('.')[:4]  # ['application/vnd', 'oasis', 'opendocument', 'text']
            if len(base_parts) >= 4:
                # Accept any application/vnd.oasis.opendocument.* where last token in {'text','text-template'}
                odf_related.update([
                    'application/vnd.oasis.opendocument.text',
                    'application/vnd.oasis.opendocument.text-template',
                    'application/vnd.oasis.opendocument.text-master'
                ])
            # Some apps (older) might advertise generic OO mime or x-extension
            odf_related.update([
                'application/x-extension-odt',
                'application/x-extension-ott'
            ])

        # Examine all apps for heuristic inclusion
        editor_name_tokens = self._get_editor_exec_tokens()

        for app in all_apps:
            if not app.should_be_visible():
                continue
            mt_set = set(app.mime_types)
            score = 0
            if mime_type in mt_set:
                # already added as exact -> skip (will merge scoring below)
                continue

            # Same primary type (e.g. any text/* when file is text/x-python)
            if is_text and any(mt.startswith('text/') for mt in mt_set):
                score += 15
            # Generic text/plain support bonus (esp if extension is typical code file)
            if is_text and 'text/plain' in mt_set:
                score += 20
            # Office category & related mime bonus for ODF documents
            if is_odf:
                if (('Office' in app.categories) or ('WordProcessor' in app.categories)):
                    score += 10
                if odf_related.intersection(mt_set):
                    score += 10
            # Editor heuristic (use Exec field name tokens)
            if is_text:
                exec_base = os.path.basename(app.exec_command.split()[0]) if app.exec_command else ''
                lowered = exec_base.lower()
                if any(tok in lowered for tok in editor_name_tokens):
                    score += 5
            if score > 0:
                add_with_score(app, score)

        # Build ranked list
        ranked = sorted((a for a, s in candidates.values()), key=lambda a: (-candidates[a.path][1], a.name.lower()))
        self._rank_cache[cache_key] = ranked
        return ranked

    # --- Helper discovery routines -------------------------------------------------
    def _get_editor_exec_tokens(self) -> set:
        """Dynamically discover probable editor executable name tokens.

        Rationale: Previously this was a static set. We now scan available desktop
        applications and collect executable basenames for those that plausibly act
        as text editors so heuristic scoring adapts to the user's system.

        Heuristic rules (union of):
        - Declares support for at least one text/* MIME type
        - OR has Categories including one of {'Development', 'Utility', 'TextEditor'}
        Additionally we seed with a small fallback list if discovery yields nothing.

        Returned tokens are lower‑cased executable basenames with common suffixes
        trimmed ("-bin").
        """
        if hasattr(self, '_editor_tokens_cache') and self._editor_tokens_cache is not None:
            return self._editor_tokens_cache

        candidates = set()
        probable_categories = {'development', 'utility', 'texteditor'}
        for app in self._get_all_applications():
            if not app.should_be_visible():
                continue
            # Exec basename
            exec_cmd = app.exec_command.split()[0] if app.exec_command else ''
            exec_base = os.path.basename(exec_cmd).lower()
            if not exec_base:
                continue
            cats = {c.lower() for c in app.categories}
            has_text_mime = any(mt.startswith('text/') for mt in app.mime_types)
            category_match = bool(probable_categories & cats)
            if has_text_mime or category_match:
                # Normalize: strip typical suffix like "-bin" (e.g., code-insiders)
                cleaned = re.sub(r'(?:-bin)$', '', exec_base)
                candidates.add(cleaned)

        # Fallback seeds if discovery failed (minimal common editors)
        if not candidates:
            candidates.update({'code', 'vim', 'nvim', 'nano', 'gedit', 'kate', 'emacs'})

        self._editor_tokens_cache = candidates
        return candidates

    def _get_all_applications(self) -> List[DesktopApplication]:
        """Get all desktop applications (cached)."""
        if self._applications_cache is not None:
            return self._applications_cache

        applications: List[DesktopApplication] = []

        # Base XDG data dirs (spec: defaults to /usr/local/share:/usr/share)
        xdg_data_dirs = os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')
        xdg_app_dirs = [os.path.join(d, 'applications') for d in xdg_data_dirs if d]

        # User local share
        user_local_app = os.path.expanduser('~/.local/share/applications')

        # Flatpak exported application directories (system + user)
        flatpak_app_dirs = [
            '/var/lib/flatpak/exports/share/applications',
            os.path.expanduser('~/.local/share/flatpak/exports/share/applications')
        ]

        # Snap applications directory
        snap_app_dir = '/var/lib/snapd/desktop/applications'

        # Discover snap package specific application dirs
        snap_specific_dirs = []
        for path in glob.glob('/snap/*/current/usr/share/applications'):
            snap_specific_dirs.append(path)

        desktop_dirs = (
            xdg_app_dirs
            + [user_local_app]
            + flatpak_app_dirs
            + [snap_app_dir]
            + snap_specific_dirs
            + self._extra_desktop_dirs
        )

        seen_paths = set()
        for desktop_dir in desktop_dirs:
            if not os.path.isdir(desktop_dir):
                continue
            try:
                for filename in os.listdir(desktop_dir):
                    if not filename.endswith('.desktop'):
                        continue
                    desktop_path = os.path.join(desktop_dir, filename)
                    if desktop_path in seen_paths:
                        continue
                    try:
                        app = DesktopApplication(desktop_path)
                        # Don't filter here; filtering & scoring happens later
                        applications.append(app)
                        seen_paths.add(desktop_path)
                    except Exception:
                        continue
            except OSError:
                continue
        self._applications_cache = applications
        return applications

    def set_default_application(self, mime_type: str, desktop_file: str) -> bool:
        """Set the default application for a MIME type"""
        try:
            subprocess.run(
                ['xdg-mime', 'default', desktop_file, mime_type],
                check=True, capture_output=True
            )

            # Clear cache
            if mime_type in self._mime_cache:
                del self._mime_cache[mime_type]

            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def set_default_application_for_file(self, file_path: str, desktop_file: str) -> bool:
        """Set the default application for a file type"""
        mime_type = self.get_mime_type(file_path)
        return self.set_default_application(mime_type, desktop_file)

    def open_with_application(self, file_path: str, application: DesktopApplication) -> Tuple[bool, str]:
        """Open a file with a specific application"""
        try:
            command = application.get_command_for_file(file_path)
            if not command:
                return False, "No command available for application"

            subprocess.Popen(command)
            return True, ""
        except Exception as e:
            return False, str(e)

    def get_application_by_desktop_file(self, desktop_file: str) -> Optional[DesktopApplication]:
        """Get application by desktop file name"""
        desktop_paths = [
            '/usr/share/applications',
            '/usr/local/share/applications',
            os.path.expanduser('~/.local/share/applications')
        ]

        for desktop_dir in desktop_paths:
            desktop_path = os.path.join(desktop_dir, desktop_file)
            if os.path.exists(desktop_path):
                app = DesktopApplication(desktop_path)
                if app.should_be_visible():
                    return app

        return None
