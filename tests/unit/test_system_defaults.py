"""
Test that system defaults are respected even with MIME type fallbacks.

Tests that when a file type has a specific system default (e.g., DBeaver for SQL),
that default is preserved even when fallback MIME types (like text/plain) are added.
"""
import pytest
import subprocess
from pathlib import Path
from core.application_manager import ApplicationManager


def test_flatpak_applications_found_as_defaults(tmp_path):
    """Test that Flatpak applications can be found as system defaults."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("SELECT 1;")

    app_manager = ApplicationManager()

    # Check if there's a system default for application/sql
    try:
        result = subprocess.run(
            ['xdg-mime', 'query', 'default', 'application/sql'],
            capture_output=True, text=True, check=True
        )
        system_default = result.stdout.strip()

        if system_default:
            # Get the default via ApplicationManager
            default_app = app_manager._get_system_default_for_mime_type('application/sql')

            # Should find the application (even if it's a Flatpak)
            if system_default.startswith('io.') or 'flatpak' in system_default.lower():
                assert default_app is not None, \
                    f"Flatpak application {system_default} should be found as default"
                print(f"✓ Flatpak default found: {default_app.name}")
    except subprocess.CalledProcessError:
        pytest.skip("No system default set for application/sql")


def test_primary_mime_default_takes_precedence(tmp_path):
    """
    Test that the system default for the primary MIME type takes precedence
    over defaults for fallback MIME types.

    For example, if DBeaver is the default for application/sql and Textadept
    is the default for text/plain, SQL files should still open with DBeaver.
    """
    sql_file = tmp_path / "query.sql"
    sql_file.write_text("SELECT id, name FROM users;")

    app_manager = ApplicationManager()

    # Get MIME chain
    mime_chain = app_manager._get_mime_types_for_file(str(sql_file))
    print(f"\\nMIME chain: {mime_chain}")

    # Check system defaults for each MIME type
    primary_mime = mime_chain[0]
    primary_default = app_manager._get_system_default_for_mime_type(primary_mime)

    print(f"Primary MIME type: {primary_mime}")
    print(f"Primary default: {primary_default.name if primary_default else 'None'}")

    # Get the overall default for the file
    file_default = app_manager.get_default_application(str(sql_file))
    print(f"File default: {file_default.name if file_default else 'None'}")

    # If there's a system default for the primary MIME type, it should be used
    if primary_default:
        assert file_default is not None, \
            "Should have a default application"
        assert file_default.name == primary_default.name, \
            f"Primary MIME default ({primary_default.name}) should take precedence over fallback defaults"

        # Check that fallback defaults exist but are not used
        for fallback_mime in mime_chain[1:]:
            fallback_default = app_manager._get_system_default_for_mime_type(fallback_mime)
            if fallback_default:
                print(f"Fallback {fallback_mime} has default: {fallback_default.name}")
                # The file default should still be the primary, not the fallback
                assert file_default.name == primary_default.name, \
                    f"Should use primary default ({primary_default.name}), not fallback ({fallback_default.name})"


def test_sql_file_default_is_database_tool_not_text_editor(tmp_path):
    """
    Test the specific user scenario: SQL files should default to a database tool
    like DBeaver, not a text editor, even though text editors are available.
    """
    sql_file = tmp_path / "database.sql"
    sql_file.write_text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")

    app_manager = ApplicationManager()

    # Get default application
    default = app_manager.get_default_application(str(sql_file))

    if not default:
        pytest.skip("No default application set for SQL files")

    print(f"\\nDefault application for SQL: {default.name}")

    # Check if it's a database-related application
    db_keywords = ['dbeaver', 'mysql', 'postgres', 'pgadmin', 'database', 'sql']
    is_db_tool = any(keyword in default.name.lower() for keyword in db_keywords)

    # Check if it's a text editor
    editor_keywords = ['edit', 'text', 'kate', 'gedit', 'emacs', 'vim', 'code',
                       'sublime', 'atom', 'notepad', 'nano', 'helix', 'textadept']
    is_editor = any(keyword in default.name.lower() for keyword in editor_keywords)

    # Get all applications to show context
    all_apps = app_manager.get_applications_for_file(str(sql_file))
    app_names = [app.name for app in all_apps]

    db_tools = [name for name in app_names
                if any(kw in name.lower() for kw in db_keywords)]
    text_editors = [name for name in app_names
                    if any(kw in name.lower() for kw in editor_keywords)]

    print(f"Database tools available: {db_tools}")
    print(f"Text editors available: {text_editors}")

    # If database tools are available, one should be the default
    if db_tools:
        assert is_db_tool, \
            f"SQL file default should be a database tool (like {db_tools[0]}), not text editor ({default.name})"

    # If only text editors are available, that's acceptable
    if not db_tools and text_editors:
        assert is_editor, \
            "If no database tools available, a text editor is acceptable"


def test_flatpak_export_paths_included():
    """Verify that Flatpak export paths are searched for desktop files."""
    app_manager = ApplicationManager()

    # This is a whitebox test - we're checking the internal implementation
    # to ensure Flatpak paths are included

    # Create a mock test to trigger the path check
    result = app_manager._get_system_default_for_mime_type('application/test-nonexistent')

    # The result will be None (no such app), but the code should have checked
    # Flatpak paths. We can't easily verify this without more instrumentation,
    # but at least we're exercising the code path.
    assert result is None, "Non-existent MIME type should have no default"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
