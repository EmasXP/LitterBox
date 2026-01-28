#!/usr/bin/env python3
"""
Demo: Text-like application/* MIME types

This demonstrates the enhanced text file detection for various
configuration and programming file formats that use application/*
MIME types but are really just text files.

Usage:
    python tests/manual/text_like_apps_demo.py
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from core.application_manager import ApplicationManager


def test_file_type(app_manager, filename, content):
    """Test application discovery for a specific file type."""
    # Create temporary file
    tmp_dir = Path(tempfile.mkdtemp())
    test_file = tmp_dir / filename
    test_file.write_text(content)

    # Get MIME type information
    mime_type = app_manager.get_mime_type(str(test_file))
    mime_chain = app_manager._get_mime_types_for_file(str(test_file))
    applications = app_manager.get_applications_for_file(str(test_file))

    # Count text editors
    editor_keywords = ['edit', 'text', 'kate', 'gedit', 'emacs', 'vim', 'code',
                       'sublime', 'atom', 'notepad', 'nano', 'helix', 'textadept']
    text_editors = [app for app in applications
                    if any(kw in app.name.lower() for kw in editor_keywords)]

    print(f"\\n{'=' * 70}")
    print(f"File: {filename}")
    print(f"{'=' * 70}")
    print(f"Primary MIME type: {mime_type}")
    print(f"Fallback chain: {' → '.join(mime_chain)}")
    print(f"\\nApplications found: {len(applications)}")
    print(f"Text editors: {len(text_editors)}")

    if text_editors:
        print(f"\\n📝 Text Editors ({len(text_editors)}):")
        for editor in text_editors[:5]:
            print(f"  • {editor.name}")
        if len(text_editors) > 5:
            print(f"  ... and {len(text_editors) - 5} more")

    # Verify text/plain is in chain for application/* types
    if mime_type.startswith('application/'):
        has_text_plain = 'text/plain' in mime_chain
        status = "✅" if has_text_plain else "❌"
        print(f"\\n{status} text/plain fallback: {'Yes' if has_text_plain else 'No'}")

    # Cleanup
    test_file.unlink()
    tmp_dir.rmdir()

    return len(text_editors) > 0


def main():
    print("=" * 70)
    print("Text-Like Application/* MIME Types Demo")
    print("=" * 70)
    print("\\nTesting various text-based file formats that use application/*")
    print("MIME types to verify they can be opened with text editors...")

    app_manager = ApplicationManager()

    # Test cases: (filename, content)
    test_cases = [
        ("pyproject.toml", "[tool.poetry]\\nname = 'test'\\nversion = '0.1.0'"),
        ("query.sql", "SELECT id, name FROM users WHERE active = 1;"),
        ("config.json", '{"database": {"host": "localhost", "port": 5432}}'),
        ("data.yaml", "services:\\n  web:\\n    image: nginx\\n    ports:\\n      - 80:80"),
        ("styles.xml", "<?xml version='1.0'?><config><setting>value</setting></config>"),
        ("index.php", "<?php echo 'Hello, World!'; ?>"),
        ("document.tex", "\\\\documentclass{article}\\n\\\\begin{document}\\nTest\\\\end{document}"),
        ("query.graphql", "query { user(id: 1) { name email } }"),
        ("app.properties", "app.name=MyApp\\napp.version=1.0"),
        ("settings.ini", "[DEFAULT]\\ndebug=true\\n[database]\\nhost=localhost"),
    ]

    results = []
    for filename, content in test_cases:
        has_editors = test_file_type(app_manager, filename, content)
        results.append((filename, has_editors))

    # Summary
    print("\\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    successful = sum(1 for _, has_editors in results if has_editors)
    total = len(results)

    print(f"\\nFiles with text editor support: {successful}/{total}")
    print("\\nResults:")
    for filename, has_editors in results:
        status = "✅" if has_editors else "⚠️"
        print(f"  {status} {filename}")

    if successful == total:
        print("\\n🎉 All text-based file types can be opened with text editors!")
    elif successful > 0:
        print(f"\\n✅ Most file types ({successful}/{total}) have text editor support")
    else:
        print("\\n⚠️ No text editors found. Please install a text editor.")


if __name__ == '__main__':
    main()
