"""
File operations and utilities
"""
import os
import shutil
import subprocess
import shlex
from pathlib import Path
from datetime import datetime
import stat

class FileOperations:
    @staticmethod
    def get_file_info(path):
        """Get comprehensive file information"""
        path_obj = Path(path)
        if not path_obj.exists():
            return None

        stat_info = path_obj.stat()

        return {
            'name': path_obj.name,
            'path': str(path_obj),
            'is_dir': path_obj.is_dir(),
            'is_file': path_obj.is_file(),
            'is_symlink': path_obj.is_symlink(),
            'size': stat_info.st_size,
            'modified': datetime.fromtimestamp(stat_info.st_mtime),
            'created': datetime.fromtimestamp(stat_info.st_ctime),
            'permissions': stat.filemode(stat_info.st_mode),
            'owner_read': bool(stat_info.st_mode & stat.S_IRUSR),
            'owner_write': bool(stat_info.st_mode & stat.S_IWUSR),
            'owner_execute': bool(stat_info.st_mode & stat.S_IXUSR),
            'group_read': bool(stat_info.st_mode & stat.S_IRGRP),
            'group_write': bool(stat_info.st_mode & stat.S_IWGRP),
            'group_execute': bool(stat_info.st_mode & stat.S_IXGRP),
            'other_read': bool(stat_info.st_mode & stat.S_IROTH),
            'other_write': bool(stat_info.st_mode & stat.S_IWOTH),
            'other_execute': bool(stat_info.st_mode & stat.S_IXOTH),
        }

    @staticmethod
    def list_directory(path, show_hidden=True):
        """List directory contents"""
        try:
            path_obj = Path(path)
            if not path_obj.is_dir():
                return []

            entries = []
            for item in path_obj.iterdir():
                if not show_hidden and item.name.startswith('.'):
                    continue

                info = FileOperations.get_file_info(item)
                if info:
                    entries.append(info)

            # Sort: directories first, then by name
            entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return entries

        except (PermissionError, OSError):
            return []

    @staticmethod
    def create_folder(parent_path, name):
        """Create a new folder"""
        try:
            new_path = Path(parent_path) / name
            new_path.mkdir()
            return True, str(new_path)
        except (OSError, IOError) as e:
            return False, str(e)

    @staticmethod
    def create_file(parent_path, name):
        """Create a new empty file"""
        try:
            new_path = Path(parent_path) / name
            new_path.touch()
            return True, str(new_path)
        except (OSError, IOError) as e:
            return False, str(e)

    @staticmethod
    def rename_item(old_path, new_name):
        """Rename a file or folder"""
        try:
            old_path_obj = Path(old_path)
            new_path = old_path_obj.parent / new_name

            # Check if the new name is the same as the old name (no change)
            if new_path.samefile(old_path_obj) if new_path.exists() else new_name == old_path_obj.name:
                return True, str(old_path_obj)  # No change needed

            # Check if a file/folder with the new name already exists
            if new_path.exists():
                return False, f"A file or folder named '{new_name}' already exists in this location."

            old_path_obj.rename(new_path)
            return True, str(new_path)
        except (OSError, IOError) as e:
            return False, str(e)

    @staticmethod
    def delete_item(path):
        """Delete a file or folder"""
        try:
            path_obj = Path(path)
            if path_obj.is_dir():
                shutil.rmtree(path_obj)
            else:
                path_obj.unlink()
            return True, ""
        except (OSError, IOError) as e:
            return False, str(e)

    @staticmethod
    def move_to_trash(path):
        """Move item to trash using system trash"""
        try:
            # Try to use gio trash command (most Linux desktops)
            subprocess.run(['gio', 'trash', path], check=True)
            return True, ""
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Fallback to trash-cli if available
                subprocess.run(['trash', path], check=True)
                return True, ""
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False, "Trash command not available"

    @staticmethod
    def is_executable(path):
        """Check if a file is executable"""
        try:
            path_obj = Path(path)
            if not path_obj.exists() or path_obj.is_dir():
                return False

            # Check if file has execute permissions
            stat_info = path_obj.stat()
            return bool(stat_info.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        except (OSError, IOError):
            return False

    @staticmethod
    def get_executable_type(path):
        """Determine the type of executable: 'gui', 'console', or 'script'"""
        try:
            path_obj = Path(path)
            if not path_obj.exists() or path_obj.is_dir():
                return None

            # Check if it's a script based on file extension or shebang
            if FileOperations._is_script(path_obj):
                return 'script'

            # Check if it's a GUI application
            if FileOperations._is_gui_executable(path_obj):
                return 'gui'

            # Default to console application
            return 'console'

        except (OSError, IOError):
            return None

    @staticmethod
    def _is_script(path_obj):
        """Check if file is a script based on extension or shebang"""
        # Check common script extensions
        script_extensions = {'.sh', '.bash', '.zsh', '.fish', '.py', '.pl', '.rb', '.js', '.lua'}
        if path_obj.suffix.lower() in script_extensions:
            return True

        # Check for shebang in files without extension or unknown extensions
        try:
            with open(path_obj, 'rb') as f:
                first_bytes = f.read(2)
                if first_bytes == b'#!':
                    return True
        except (OSError, IOError):
            pass

        return False

    @staticmethod
    def _is_gui_executable(path_obj):
        """Check if executable is likely a GUI application"""
        try:
            # First, check if it's linked against GUI libraries (most reliable method)
            try:
                ldd_result = subprocess.run(['ldd', str(path_obj)],
                                          capture_output=True, text=True, timeout=5)
                if ldd_result.returncode == 0:
                    ldd_output = ldd_result.stdout.lower()

                    # Strong GUI library indicators
                    gui_libs = [
                        'libgtk', 'libqt', 'libx11', 'libxcb', 'libwayland',
                        'libgdk', 'libgio-2.0', 'libcairo', 'libpango',
                        'libatk', 'libgdkpixbuf', 'libharfbuzz'
                    ]

                    gui_lib_count = sum(1 for lib in gui_libs if lib in ldd_output)

                    # If multiple GUI libraries are present, it's likely a GUI app
                    if gui_lib_count >= 2:
                        return True

                    # Special case: if it has X11 or Wayland, it's likely GUI
                    if any(lib in ldd_output for lib in ['libx11', 'libxcb', 'libwayland']):
                        return True

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Check the executable name for GUI patterns
            name = path_obj.name.lower()
            gui_name_patterns = [
                'gui', '-gui', 'window', 'desktop', 'browser', 'viewer',
                'studio', 'designer', 'player', 'editor'
            ]

            # Also check for known GUI applications
            known_gui_apps = {
                'firefox', 'chrome', 'chromium', 'gedit', 'kate', 'code', 'vscode',
                'nautilus', 'dolphin', 'thunar', 'pcmanfm', 'gimp', 'inkscape',
                'vlc', 'mpv', 'smplayer', 'rhythmbox', 'totem', 'evince',
                'libreoffice', 'calc', 'writer', 'impress', 'draw', 'math',
                'thunderbird', 'evolution', 'kmail', 'pidgin', 'discord',
                'steam', 'lutris', 'blender', 'krita', 'darktable'
            }

            if name in known_gui_apps:
                return True

            for pattern in gui_name_patterns:
                if pattern in name:
                    return True

            # Use file command as additional check
            try:
                result = subprocess.run(['file', str(path_obj)],
                                      capture_output=True, text=True, timeout=5)

                if result.returncode == 0:
                    file_output = result.stdout.lower()

                    # Look for specific GUI framework mentions
                    if any(framework in file_output for framework in ['gtk', 'qt', 'gnome', 'kde']):
                        return True

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                pass

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False

    @staticmethod
    def run_executable(path, force_terminal=False):
        """Run an executable file with smart detection

        Args:
            path: Path to the executable
            force_terminal: If True, always run in terminal regardless of type
        """
        try:
            # Get the directory containing the executable
            path_obj = Path(path)
            executable_dir = str(path_obj.parent)

            if force_terminal:
                # Force terminal execution
                return FileOperations._run_in_terminal(path, cwd=executable_dir)

            # Use smart detection
            executable_type = FileOperations.get_executable_type(path)

            if executable_type == 'gui':
                # GUI applications - run directly without terminal
                subprocess.Popen([path], cwd=executable_dir)
                return True, ""
            else:
                # Console applications and scripts - run in terminal by default
                return FileOperations._run_in_terminal(path, cwd=executable_dir)

        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            return False, str(e)

    @staticmethod
    def run_executable_direct(path):
        """Run an executable directly without terminal"""
        try:
            # Get the directory containing the executable
            path_obj = Path(path)
            executable_dir = str(path_obj.parent)

            subprocess.Popen([path], cwd=executable_dir)
            return True, ""
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            return False, str(e)

    @staticmethod
    def _run_in_terminal(path, cwd=None):
        """Run executable in a terminal window

        Args:
            path: Path to the executable
            cwd: Working directory for the executable (defaults to parent directory of executable)
        """
        try:
            # If no CWD specified, use the directory containing the executable
            if cwd is None:
                path_obj = Path(path)
                cwd = str(path_obj.parent)

            # Use gnome-terminal if available, otherwise try other common terminals
            # Use 'cd' command to change to the correct directory before running
            terminal_commands = [
                ['gnome-terminal', '--', 'bash', '-c', f'cd {shlex.quote(cwd)} && {path}; read -p "Press Enter to continue..."'],
                ['konsole', '-e', 'bash', '-c', f'cd {shlex.quote(cwd)} && {path}; read -p "Press Enter to continue..."'],
                ['xterm', '-e', 'bash', '-c', f'cd {shlex.quote(cwd)} && {path}; read -p "Press Enter to continue..."'],
                ['x-terminal-emulator', '-e', 'bash', '-c', f'cd {shlex.quote(cwd)} && {path}; read -p "Press Enter to continue..."']
            ]

            for terminal_cmd in terminal_commands:
                try:
                    subprocess.Popen(terminal_cmd)
                    return True, ""
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue

            # If no terminal found, try to run directly as fallback
            subprocess.Popen([path], cwd=cwd)
            return True, ""

        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            return False, str(e)

    @staticmethod
    def is_text_file(path):
        """Check if a file is likely a text file that can be edited"""
        try:
            path_obj = Path(path)
            if not path_obj.exists() or path_obj.is_dir():
                return False

            # Check file extension for common text file types
            text_extensions = {
                '.txt', '.py', '.sh', '.bash', '.zsh', '.fish', '.pl', '.rb', '.js', '.ts',
                '.html', '.htm', '.css', '.xml', '.json', '.yaml', '.yml', '.toml',
                '.ini', '.cfg', '.conf', '.md', '.rst', '.c', '.cpp', '.h', '.hpp',
                '.java', '.cs', '.go', '.rs', '.php', '.sql', '.log', '.desktop'
            }

            if path_obj.suffix.lower() in text_extensions:
                return True

            # For files without extension or unknown extensions, try to read first bytes
            try:
                with open(path_obj, 'rb') as f:
                    sample = f.read(1024)
                    # Check if the sample contains mostly text (no null bytes, mostly printable)
                    if b'\x00' not in sample:
                        try:
                            sample.decode('utf-8')
                            return True
                        except UnicodeDecodeError:
                            try:
                                sample.decode('latin-1')
                                return True
                            except UnicodeDecodeError:
                                pass
            except (OSError, IOError):
                pass

            return False
        except (OSError, IOError):
            return False

    @staticmethod
    def open_with_editor(path):
        """Open file with a text editor honoring the user's desktop defaults."""
        last_error = ""

        try:
            from core.application_manager import ApplicationManager

            app_mgr = ApplicationManager()

            def _launch(app):
                success, error = app_mgr.open_with_application(path, app)
                return success, error

            default_app = app_mgr.get_default_application(path)
            if default_app and app_mgr.is_probable_editor(default_app):
                success, error = _launch(default_app)
                if success:
                    return True, ""
                last_error = error or last_error

            try:
                ranked_apps = app_mgr.get_ranked_applications_for_file(path)
            except AttributeError:
                ranked_apps = app_mgr.get_applications_for_file(path)

            for app in ranked_apps:
                if default_app and app.path == default_app.path:
                    continue
                if not app_mgr.is_probable_editor(app):
                    continue
                success, error = _launch(app)
                if success:
                    return True, ""
                last_error = error or last_error

        except Exception as e:
            last_error = str(e) or last_error

        try:
            subprocess.run(['xdg-open', path], check=True)
            return True, ""

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            if not last_error:
                last_error = str(e)

        return False, last_error or "No suitable editor found."

    @staticmethod
    def open_with_default(path):
        try:
            from core.application_manager import ApplicationManager
            app_mgr = ApplicationManager()
            app = app_mgr.get_default_application(path)
            if app:
                # Use the same launch path as Open With (now includes CWD)
                return app_mgr.open_with_application(path, app)
            # Fallback to xdg-open if no default resolved
            # Get the directory containing the file to use as CWD
            path_obj = Path(path)
            file_dir = str(path_obj.parent)
            subprocess.run(['xdg-open', path], check=True, cwd=file_dir)
            return True, ""
        except Exception as e:
            return False, str(e)

    @staticmethod
    def format_size(size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
