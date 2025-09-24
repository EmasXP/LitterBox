"""
Application manager for handling MIME types and desktop applications
"""
import subprocess
import os
from pathlib import Path
import configparser
import mimetypes
import re
from typing import List, Dict, Optional, Tuple


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
        return not (self.no_display or self.hidden) and self.name and self.exec_command
    
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
    """Manages desktop applications and MIME types"""
    
    def __init__(self):
        self._applications_cache = None
        self._mime_cache = {}
        
        # Initialize mimetypes
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
        """Get all applications that can handle a MIME type"""
        if mime_type in self._mime_cache:
            return self._mime_cache[mime_type]
        
        applications = []
        
        # Get all desktop applications
        all_apps = self._get_all_applications()
        
        # Filter by MIME type
        for app in all_apps:
            if app.can_handle_mime_type(mime_type) and app.should_be_visible():
                applications.append(app)
        
        # Sort by name
        applications.sort(key=lambda app: app.name.lower())
        
        # Cache the result
        self._mime_cache[mime_type] = applications
        
        return applications
    
    def get_applications_for_file(self, file_path: str) -> List[DesktopApplication]:
        """Get all applications that can handle a file"""
        mime_type = self.get_mime_type(file_path)
        return self.get_applications_for_mime_type(mime_type)
    
    def _get_all_applications(self) -> List[DesktopApplication]:
        """Get all desktop applications"""
        if self._applications_cache is not None:
            return self._applications_cache
        
        applications = []
        
        # Desktop file directories in order of preference
        desktop_dirs = [
            '/usr/share/applications',
            '/usr/local/share/applications',
            os.path.expanduser('~/.local/share/applications')
        ]
        
        for desktop_dir in desktop_dirs:
            if not os.path.exists(desktop_dir):
                continue
            
            try:
                for filename in os.listdir(desktop_dir):
                    if filename.endswith('.desktop'):
                        desktop_path = os.path.join(desktop_dir, filename)
                        try:
                            app = DesktopApplication(desktop_path)
                            if app.should_be_visible():
                                applications.append(app)
                        except Exception:
                            # Skip invalid desktop files
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