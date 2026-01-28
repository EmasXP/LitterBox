#!/usr/bin/env python3
"""
Manual demo: Test SQL file application discovery

This script demonstrates the application discovery for SQL files,
showing that text editors are now properly discovered alongside
database-specific tools like DBeaver.

Usage:
    python tests/manual/sql_file_demo.py [path_to_sql_file]
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from core.application_manager import ApplicationManager


def demo_sql_file_discovery(sql_file_path: str):
    """Demonstrate application discovery for an SQL file."""

    print(f"Testing SQL file: {sql_file_path}")
    print("=" * 70)

    # Check if file exists
    if not Path(sql_file_path).exists():
        print(f"Error: File not found: {sql_file_path}")
        return

    # Initialize application manager
    app_manager = ApplicationManager()

    # Get MIME type
    mime_type = app_manager.get_mime_type(sql_file_path)
    print(f"\nDetected MIME type: {mime_type}")

    # Get MIME type fallback chain
    mime_chain = app_manager._get_mime_types_for_file(sql_file_path)
    print(f"\nMIME type fallback chain:")
    for i, mime in enumerate(mime_chain, 1):
        print(f"  {i}. {mime}")

    # Get all applications
    applications = app_manager.get_applications_for_file(sql_file_path)

    print(f"\nFound {len(applications)} applications:")
    print("-" * 70)

    # Categorize applications
    db_tools = []
    text_editors = []
    other_apps = []

    db_keywords = ['dbeaver', 'mysql', 'postgres', 'pgadmin', 'sql', 'database']
    editor_keywords = ['edit', 'text', 'kate', 'gedit', 'emacs', 'vim', 'code',
                       'sublime', 'atom', 'notepad', 'nano', 'helix', 'textadept']

    for app in applications:
        name_lower = app.name.lower()

        if any(keyword in name_lower for keyword in db_keywords):
            db_tools.append(app)
        elif any(keyword in name_lower for keyword in editor_keywords):
            text_editors.append(app)
        else:
            other_apps.append(app)

    # Display categorized results
    if db_tools:
        print("\n📊 Database Tools:")
        for app in db_tools:
            print(f"  • {app.name}")

    if text_editors:
        print("\n📝 Text Editors:")
        for app in text_editors:
            mime_info = "text/plain" if app.can_handle_mime_type('text/plain') else "other"
            print(f"  • {app.name} (supports {mime_info})")

    if other_apps:
        print("\n🔧 Other Applications:")
        for app in other_apps[:5]:  # Limit to first 5
            print(f"  • {app.name}")
        if len(other_apps) > 5:
            print(f"  ... and {len(other_apps) - 5} more")

    # Summary
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Database tools: {len(db_tools)}")
    print(f"  Text editors: {len(text_editors)}")
    print(f"  Other applications: {len(other_apps)}")
    print(f"  Total: {len(applications)}")

    # Check if the fix is working
    if len(text_editors) > 0:
        print("\n✅ SUCCESS: Text editors are being discovered for SQL files!")
    else:
        print("\n⚠️  WARNING: No text editors found. This might indicate an issue.")

    # Get default application
    default_app = app_manager.get_default_application(sql_file_path)
    if default_app:
        print(f"\n🌟 Default application: {default_app.name}")

    print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]
    else:
        # Default to the user's file if it exists
        sql_file = '/home/magnus/Downloads/query.sql'
        if not Path(sql_file).exists():
            print("Usage: python sql_file_demo.py <path_to_sql_file>")
            print("\nCreating a demo SQL file...")
            import tempfile
            demo_dir = Path(tempfile.mkdtemp())
            sql_file = str(demo_dir / "demo.sql")
            Path(sql_file).write_text("SELECT * FROM users WHERE active = 1;")
            print(f"Created: {sql_file}\n")

    demo_sql_file_discovery(sql_file)
