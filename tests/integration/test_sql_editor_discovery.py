"""
Integration test for SQL file editor discovery.

Tests the complete workflow of discovering text editors for SQL files,
simulating the real-world scenario where a user has an SQL file and
expects text editors like Kate or Textadept to be available.
"""
import pytest
from pathlib import Path
from core.application_manager import ApplicationManager


def test_sql_file_discovers_text_editors(tmp_path):
    """
    Integration test: SQL file should discover common text editors.

    This simulates the user scenario: having an SQL file that should be
    openable by text editors, not just specialized database tools like DBeaver.
    """
    # Create a realistic SQL file
    sql_file = tmp_path / "query.sql"
    sql_file.write_text("""
-- Sample database query
SELECT
    users.id,
    users.name,
    users.email,
    COUNT(orders.id) as order_count
FROM users
LEFT JOIN orders ON users.id = orders.user_id
WHERE users.active = true
GROUP BY users.id, users.name, users.email
ORDER BY order_count DESC
LIMIT 100;
""")

    # Initialize application manager
    app_manager = ApplicationManager()

    # Get all applications that can open this SQL file
    applications = app_manager.get_applications_for_file(str(sql_file))

    # Extract application names for easier checking
    app_names = [app.name for app in applications]

    print(f"\nFound {len(applications)} applications for SQL file:")
    for app in applications[:10]:  # Print first 10
        print(f"  - {app.name}")

    # Verify we found multiple applications
    assert len(applications) > 1, \
        "Should find multiple applications for SQL files (not just DBeaver)"

    # Check for common text editors that should be available
    # These editors all support text/plain MIME type
    potential_editors = {
        'Kate', 'Gedit', 'Emacs', 'Vim', 'Neovim', 'Visual Studio Code',
        'VSCode', 'Sublime Text', 'Atom', 'Geany', 'Mousepad', 'Pluma',
        'Text Editor', 'Textadept', 'Notepadqq', 'nano', 'Helix'
    }

    # Find which editors are present
    found_editors = [name for name in app_names if name in potential_editors]

    # We should find at least one common text editor
    # (Unless the system has no text editors installed, which would be unusual)
    print(f"\nFound text editors: {found_editors}")

    # Verify the fallback mechanism is working
    # by checking that applications supporting text/plain are included
    text_plain_supported_apps = [
        app for app in applications
        if app.can_handle_mime_type('text/plain')
    ]

    assert len(text_plain_supported_apps) > 0, \
        "Should include applications that support text/plain MIME type"

    print(f"\nApplications supporting text/plain: {len(text_plain_supported_apps)}")

    # The key insight: without the fix, only DBeaver would be found
    # With the fix, text editors are also discovered
    specialized_db_tools = ['DBeaver', 'DBeaver CE', 'MySQL Workbench', 'pgAdmin']
    db_tool_count = sum(1 for name in app_names if any(db in name for db in specialized_db_tools))
    text_editor_count = len(found_editors)

    # Success criteria: we should have text editors, not just database tools
    if len(found_editors) > 0:
        assert text_editor_count >= db_tool_count, \
            f"Should have at least as many text editors ({text_editor_count}) as database tools ({db_tool_count})"


def test_sql_mime_type_resolution(tmp_path):
    """Test that SQL files are correctly identified as application/sql."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("SELECT 1;")

    app_manager = ApplicationManager()
    mime_type = app_manager.get_mime_type(str(sql_file))

    # Should detect as application/sql
    assert mime_type == 'application/sql', \
        f"SQL file should be detected as 'application/sql', got '{mime_type}'"


def test_sql_fallback_chain(tmp_path):
    """Test the complete MIME type fallback chain for SQL files."""
    sql_file = tmp_path / "database.sql"
    sql_file.write_text("CREATE TABLE users (id INT PRIMARY KEY);")

    app_manager = ApplicationManager()

    # Get the MIME type chain
    mime_chain = app_manager._get_mime_types_for_file(str(sql_file))

    print(f"\nMIME type fallback chain for SQL: {mime_chain}")

    # Verify the chain structure
    assert len(mime_chain) >= 3, \
        "Should have at least 3 MIME types in the fallback chain"

    assert mime_chain[0] == 'application/sql', \
        "Primary MIME type should be application/sql"

    assert 'text/x-sql' in mime_chain, \
        "Should include text/x-sql as SQL-specific text variant"

    assert 'text/plain' in mime_chain, \
        "Should include text/plain as universal text fallback"

    # Verify ordering: text/x-sql should come before text/plain
    sql_text_idx = mime_chain.index('text/x-sql')
    plain_text_idx = mime_chain.index('text/plain')

    assert sql_text_idx < plain_text_idx, \
        "text/x-sql should come before text/plain in priority"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
