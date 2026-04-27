"""Tests for command escaping in DesktopApplication.get_command_for_file() and _run_in_terminal."""
import shlex

from core.application_manager import DesktopApplication


class TestCommandEscaping:
    """Verify file paths with special characters are properly escaped."""

    def _make_app(self, exec_command: str) -> DesktopApplication:
        """Create a DesktopApplication with a given Exec command without needing a .desktop file."""
        app = object.__new__(DesktopApplication)
        app.path = "/dev/null"
        app.name = "TestApp"
        app.exec_command = exec_command
        app.icon = ""
        app.mime_types = []
        app.categories = []
        app.no_display = False
        app.hidden = False
        return app

    def test_path_with_spaces_is_escaped(self):
        """File paths containing spaces must be properly quoted."""
        app = self._make_app("gedit %f")
        cmd = app.get_command_for_file("/home/user/my documents/file.txt")
        # The path should be a single argument, not split on spaces
        assert cmd[0] == "gedit"
        assert len(cmd) == 2
        assert cmd[1] == "/home/user/my documents/file.txt"

    def test_path_with_dollar_sign_is_escaped(self):
        """File paths with $ should not be interpreted as shell variables."""
        app = self._make_app("gedit %f")
        cmd = app.get_command_for_file("/home/user/$pecial/file.txt")
        assert cmd[1] == "/home/user/$pecial/file.txt"

    def test_path_with_backticks_is_escaped(self):
        """File paths with backticks should not cause command substitution."""
        app = self._make_app("gedit %f")
        cmd = app.get_command_for_file("/home/user/`rm -rf`/file.txt")
        assert cmd[1] == "/home/user/`rm -rf`/file.txt"

    def test_path_with_single_quotes_is_escaped(self):
        """File paths with single quotes must be properly escaped."""
        app = self._make_app("gedit %f")
        cmd = app.get_command_for_file("/home/user/it's a file.txt")
        assert cmd[1] == "/home/user/it's a file.txt"

    def test_path_with_semicolon_is_escaped(self):
        """Semicolons in paths should not be treated as command separators."""
        app = self._make_app("gedit %f")
        cmd = app.get_command_for_file("/home/user/a;rm -rf /;b.txt")
        assert cmd[1] == "/home/user/a;rm -rf /;b.txt"

    def test_no_field_code_appends_path(self):
        """When no %f/%u field code exists, path is appended as a separate argument."""
        app = self._make_app("myapp")
        cmd = app.get_command_for_file("/home/user/test file.txt")
        assert cmd[0] == "myapp"
        assert cmd[1] == "/home/user/test file.txt"

    def test_url_field_code(self):
        """The %u field code should also be properly escaped."""
        app = self._make_app("browser %u")
        cmd = app.get_command_for_file("/home/user/my file.html")
        assert cmd[1] == "/home/user/my file.html"

    def test_field_codes_removed(self):
        """Unsupported field codes like %i, %c, %d should be removed."""
        app = self._make_app("myapp %i %c %f")
        cmd = app.get_command_for_file("/tmp/test.txt")
        # %i and %c should be stripped, leaving just myapp and the path
        assert cmd[0] == "myapp"
        assert "/tmp/test.txt" in cmd
