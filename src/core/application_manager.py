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
            config = configparser.ConfigParser(interpolation=None, strict=False)
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

        except (configparser.DuplicateOptionError, configparser.Error):
            # Handle parsing errors by parsing manually
            self._parse_desktop_file_manual()
        except Exception as e:
            # If parsing fails, leave fields empty
            # Suppress common parsing errors for invalid desktop files
            pass

    def _parse_desktop_file_manual(self):
        """Manual parsing for problematic desktop files"""
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            in_desktop_entry = False
            for line in lines:
                line = line.strip()

                if line == '[Desktop Entry]':
                    in_desktop_entry = True
                    continue
                elif line.startswith('[') and line.endswith(']'):
                    in_desktop_entry = False
                    continue

                if not in_desktop_entry or not line or line.startswith('#'):
                    continue

                if '=' not in line:
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                if key == 'Name' and not self.name:
                    self.name = value
                elif key == 'Exec' and not self.exec_command:
                    self.exec_command = value
                elif key == 'Icon' and not self.icon:
                    self.icon = value
                elif key == 'NoDisplay' and not hasattr(self, '_no_display_set'):
                    self.no_display = value.lower() in ['true', '1', 'yes']
                    self._no_display_set = True
                elif key == 'Hidden' and not hasattr(self, '_hidden_set'):
                    self.hidden = value.lower() in ['true', '1', 'yes']
                    self._hidden_set = True
                elif key == 'MimeType' and not self.mime_types:
                    self.mime_types = [mt.strip() for mt in value.split(';') if mt.strip()]
                elif key == 'Categories' and not self.categories:
                    self.categories = [cat.strip() for cat in value.split(';') if cat.strip()]

        except Exception:
            # If manual parsing also fails, leave fields empty
            pass

    def can_handle_mime_type(self, mime_type: str) -> bool:
        """Check if this application can handle the given MIME type"""
        return mime_type in self.mime_types

    def should_be_visible(self) -> bool:
        """Check if this application should be visible in menus"""
        return bool(not self.hidden and self.name and self.exec_command)

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

    Enhanced implementation with intelligent MIME type expansion and ranking:

    Key Features:
    - Intelligent MIME type fallback system via _get_mime_types_for_file()
    - Prioritizes XDG system defaults in application ranking
    - Handles text-like application/* files (e.g., application/x-php) with text/plain fallbacks
    - Enhanced support for OpenDocument and Microsoft Office formats
    - Smart application ranking based on MIME type priority and system defaults

    The system works by:
    1. Determining a primary MIME type for a file
    2. Generating logical fallback MIME types (e.g., text/plain for text-like files)
    3. Querying applications for all MIME types in priority order
    4. Ranking applications with XDG defaults getting highest priority
    5. Using heuristics for better application discovery (editor detection, etc.)
    """

    def __init__(self, extra_desktop_dirs: Optional[Iterable[str]] = None):
            self._applications_cache: Optional[List[DesktopApplication]] = None
            self._mime_cache: Dict[str, List[DesktopApplication]] = {}
            self._rank_cache: Dict[Tuple, List[DesktopApplication]] = {}
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

    def _get_mime_types_for_file(self, file_path: str) -> List[str]:
        """Get an ordered list of MIME types for a file.

        Returns a list starting with the primary MIME type, followed by logical
        fallbacks that applications might also support. This enables more
        intelligent application discovery and ranking.

        Args:
            file_path: Path to the file to analyze

        Returns:
            List of MIME types in priority order (most specific first)
        """
        primary_mime = self.get_mime_type(file_path)
        mime_types = [primary_mime]

        # Parse the MIME type components
        if '/' in primary_mime:
            primary_type, sub_type = primary_mime.split('/', 1)
        else:
            return mime_types

        # Handle text/* files - most should also work with text/plain applications
        if primary_type == 'text':
            if primary_mime != 'text/plain':
                mime_types.append('text/plain')

        # Handle known text-like application/* MIME types
        text_like_apps = {
            'application/json': ['text/json', 'text/plain'],
            'application/javascript': ['text/javascript', 'text/plain'],
            'application/xml': ['text/xml', 'text/plain'],
            'application/yaml': ['text/yaml', 'text/x-yaml', 'text/plain'],
            'application/x-yaml': ['application/yaml', 'text/yaml', 'text/plain'],
            'application/x-php': ['text/php', 'text/x-php', 'application/php', 'text/plain'],
            'application/x-python': ['text/python', 'text/x-python', 'text/plain'],
            'application/x-ruby': ['text/ruby', 'text/x-ruby', 'text/plain'],
            'application/x-perl': ['text/perl', 'text/x-perl', 'text/plain'],
            'application/x-shellscript': ['text/x-shellscript', 'application/x-sh', 'text/plain'],
            'application/x-sh': ['text/x-shellscript', 'application/x-shellscript', 'text/plain'],
            'application/x-powershell': ['text/x-powershell', 'text/plain'],
        }

        if primary_mime in text_like_apps:
            for fallback in text_like_apps[primary_mime]:
                if fallback not in mime_types:
                    mime_types.append(fallback)

        # Handle OpenDocument formats - add related ODF variants
        if primary_mime.startswith('application/vnd.oasis.opendocument'):
            base_parts = primary_mime.split('.')
            if len(base_parts) >= 4:
                # For odt files, also try related text document formats
                if 'text' in base_parts[-1]:
                    odf_variants = [
                        'application/vnd.oasis.opendocument.text',
                        'application/vnd.oasis.opendocument.text-template',
                        'application/vnd.oasis.opendocument.text-master',
                        'application/x-extension-odt',
                        'application/x-extension-ott'
                    ]
                    for variant in odf_variants:
                        if variant != primary_mime and variant not in mime_types:
                            mime_types.append(variant)

        # Handle Microsoft Office formats
        office_mappings = {
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': [
                'application/msword', 'application/x-doc'
            ],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': [
                'application/vnd.ms-excel', 'application/x-excel'
            ],
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': [
                'application/vnd.ms-powerpoint', 'application/x-powerpoint'
            ],
            'application/msword': [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ],
            'application/vnd.ms-excel': [
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ],
            'application/vnd.ms-powerpoint': [
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            ],
        }

        if primary_mime in office_mappings:
            for variant in office_mappings[primary_mime]:
                if variant not in mime_types:
                    mime_types.append(variant)

        # Handle PDF and document formats
        if primary_mime == 'application/pdf':
            pdf_variants = [
                'application/x-pdf',
                'application/x-bzpdf',
                'application/x-gzpdf'
            ]
            for variant in pdf_variants:
                if variant not in mime_types:
                    mime_types.append(variant)

        # Handle image formats - add common related formats
        if primary_type == 'image':
            common_image_formats = {
                'image/jpeg': ['image/jpg'],
                'image/png': [],
                'image/gif': [],
                'image/webp': ['image/png'],  # Fallback for compatibility
                'image/bmp': ['image/x-bmp'],
                'image/tiff': ['image/tif'],
                'image/svg+xml': ['image/svg'],
            }
            if primary_mime in common_image_formats:
                for variant in common_image_formats[primary_mime]:
                    if variant not in mime_types:
                        mime_types.append(variant)

        # Handle video formats - add common related formats
        if primary_type == 'video':
            common_video_formats = {
                'video/mp4': ['video/mpeg4'],
                'video/avi': ['video/x-avi', 'video/msvideo'],
                'video/quicktime': ['video/mov'],
                'video/x-msvideo': ['video/avi'],
                'video/webm': [],
                'video/mkv': ['video/x-matroska'],
                'video/x-matroska': ['video/mkv'],
            }
            if primary_mime in common_video_formats:
                for variant in common_video_formats[primary_mime]:
                    if variant not in mime_types:
                        mime_types.append(variant)

        # Handle audio formats - add common related formats
        if primary_type == 'audio':
            common_audio_formats = {
                'audio/mpeg': ['audio/mp3', 'audio/x-mp3'],
                'audio/mp3': ['audio/mpeg'],
                'audio/ogg': ['audio/x-ogg'],
                'audio/wav': ['audio/x-wav', 'audio/wave'],
                'audio/vnd.wave': ['audio/wav', 'audio/x-wav'],
                'audio/flac': ['audio/x-flac'],
                'audio/aac': ['audio/x-aac'],
                'audio/x-ms-wma': ['audio/wma'],
            }
            if primary_mime in common_audio_formats:
                for variant in common_audio_formats[primary_mime]:
                    if variant not in mime_types:
                        mime_types.append(variant)

        return mime_types

    def get_default_application(self, file_path: str) -> Optional[DesktopApplication]:
        """Get the default application for a file.

        Uses the new MIME type expansion system to find defaults. Tries each
        MIME type from _get_mime_types_for_file() in order until a system
        default is found via xdg-mime.
        """
        mime_types = self._get_mime_types_for_file(file_path)

        # Try each MIME type in priority order to find a system default
        for mime_type in mime_types:
            app = self._get_system_default_for_mime_type(mime_type)
            if app:
                return app

        # Final fallback: use highest-ranked application from our heuristic system
        ranked_apps = self.get_ranked_applications_for_file(file_path)
        if ranked_apps:
            return ranked_apps[0]

        return None

    def _get_system_default_for_mime_type(self, mime_type: str) -> Optional[DesktopApplication]:
        """Get the system's explicit default application for a MIME type"""
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
        """Get applications that can handle a file.

        Now enhanced to use the MIME type expansion system, returning all
        applications that support any of the file's MIME types.
        """
        mime_types = self._get_mime_types_for_file(file_path)
        all_apps = set()

        for mime_type in mime_types:
            apps = self.get_applications_for_mime_type(mime_type)
            all_apps.update(apps)

        # Return sorted by name for consistency
        return sorted(all_apps, key=lambda a: a.name.lower())

    # --- Enhanced ranking / heuristic discovery ---------------------------------
    def get_ranked_applications_for_file(self, file_path: str) -> List[DesktopApplication]:
        """Return a ranked list of suitable applications using the new MIME type system.

        Strategy:
        1. Get the ordered list of MIME types for the file using _get_mime_types_for_file()
        2. Query applications for each MIME type in the list
        3. Score applications based on:
           - +100: XDG system default for any of the MIME types
           - +50: Exact match for primary MIME type
           - +30: Match for secondary MIME type (first fallback)
           - +15: Match for tertiary MIME type (subsequent fallbacks)
           - +10: Office category for office documents
           - +5: Editor heuristic for text files
        4. Sort by score (descending) then by name, deduplicating while preserving highest score
        """
        mime_types = self._get_mime_types_for_file(file_path)
        if not mime_types:
            return []

        primary_mime = mime_types[0]
        file_ext = os.path.splitext(file_path)[1].lower()
        cache_key = (primary_mime, file_ext, tuple(mime_types))

        if cache_key in self._rank_cache:
            return self._rank_cache[cache_key]

        # Build candidate set with scoring
        candidates: Dict[str, Tuple[DesktopApplication, int]] = {}
        all_apps = self._get_all_applications()

        def add_with_score(app: DesktopApplication, score: int):
            prev = candidates.get(app.path)
            if prev is None or score > prev[1]:  # keep best score
                candidates[app.path] = (app, score)

        # Check for XDG system defaults for any MIME type
        default_apps = {}
        for i, mime_type in enumerate(mime_types):
            default_app = self._get_system_default_for_mime_type(mime_type)
            if default_app and default_app.path not in default_apps:
                default_apps[default_app.path] = (default_app, i)

        # Score applications based on MIME type matches
        for app in all_apps:
            if not app.should_be_visible():
                continue

            max_score = 0
            mt_set = set(app.mime_types)

            # Check if this app is a system default
            if app.path in default_apps:
                max_score = max(max_score, 100)

            # Score based on MIME type priority
            for i, mime_type in enumerate(mime_types):
                if mime_type in mt_set:
                    if i == 0:  # Primary MIME type
                        max_score = max(max_score, 50)
                    elif i == 1:  # First fallback
                        max_score = max(max_score, 30)
                    else:  # Subsequent fallbacks
                        max_score = max(max_score, 15)

            # Additional heuristic bonuses
            primary_type = primary_mime.split('/')[0] if '/' in primary_mime else ''

            # Office category bonus for office documents
            if primary_mime.startswith(('application/vnd.oasis.opendocument',
                                      'application/vnd.openxmlformats-officedocument',
                                      'application/msword', 'application/vnd.ms-')):
                if ('Office' in app.categories) or ('WordProcessor' in app.categories):
                    max_score = max(max_score, max_score + 10)

            # Editor heuristic bonus for text files
            if primary_type == 'text' or primary_mime in [
                'application/json', 'application/javascript', 'application/xml',
                'application/x-php', 'application/x-python'
            ]:
                editor_tokens = self._get_editor_exec_tokens()
                exec_base = os.path.basename(app.exec_command.split()[0]) if app.exec_command else ''
                lowered = exec_base.lower()
                if any(tok in lowered for tok in editor_tokens):
                    max_score = max(max_score, max_score + 5)

            if max_score > 0:
                add_with_score(app, max_score)

        # Build ranked list
        ranked = sorted(
            (a for a, s in candidates.values()),
            key=lambda a: (-candidates[a.path][1], a.name.lower())
        )

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
