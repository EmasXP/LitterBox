"""
File operations and utilities
"""
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import stat

class FileOperations:
    @staticmethod
    def get_standard_places():
        """Get standard directory places for the places dropdown"""
        home = Path.home()
        places = [
            ("Home", str(home)),
            ("Desktop", str(home / "Desktop")),
            ("Documents", str(home / "Documents")),
            ("Downloads", str(home / "Downloads")),
            ("Music", str(home / "Music")),
            ("Pictures", str(home / "Pictures")),
            ("Videos", str(home / "Videos")),
            ("Root", "/"),
        ]

        # Only include directories that exist
        return [(name, path) for name, path in places if Path(path).exists()]

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
    def run_executable(path):
        """Run an executable file"""
        try:
            # Run the executable in the terminal
            # Use gnome-terminal if available, otherwise try other common terminals
            terminal_commands = [
                ['gnome-terminal', '--', 'bash', '-c', f'{path}; read -p "Press Enter to continue..."'],
                ['konsole', '-e', 'bash', '-c', f'{path}; read -p "Press Enter to continue..."'],
                ['xterm', '-e', 'bash', '-c', f'{path}; read -p "Press Enter to continue..."'],
                ['x-terminal-emulator', '-e', 'bash', '-c', f'{path}; read -p "Press Enter to continue..."']
            ]
            
            for terminal_cmd in terminal_commands:
                try:
                    subprocess.Popen(terminal_cmd)
                    return True, ""
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            # If no terminal found, try to run directly
            subprocess.Popen([path])
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
        """Open file with text editor"""
        try:
            # Try common text editors in order of preference
            editors = [
                ['gedit', path],
                ['kate', path],
                ['notepadqq', path],
                ['pluma', path],
                ['leafpad', path],
                ['mousepad', path],
                ['nano', path],  # This will open in terminal
                ['vi', path]     # This will open in terminal
            ]
            
            for editor_cmd in editors:
                try:
                    subprocess.Popen(editor_cmd)
                    return True, ""
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            # Fallback to xdg-open (which should work for text files)
            subprocess.run(['xdg-open', path], check=True)
            return True, ""
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return False, str(e)

    @staticmethod
    def open_with_default(path):
        """Open file with default application"""
        try:
            subprocess.run(['xdg-open', path], check=True)
            return True, ""
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return False, str(e)

    @staticmethod
    def format_size(size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
