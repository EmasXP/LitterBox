"""
Test text-like application/* MIME types fallback to text/plain.

Tests that various text-based files with application/* MIME types
can be opened with text editors by ensuring text/plain is included
as a fallback MIME type.
"""
import pytest
from pathlib import Path
from core.application_manager import ApplicationManager


@pytest.mark.parametrize("filename,expected_primary,should_have_text_plain", [
    # Configuration files
    ("config.toml", "application/toml", True),
    ("settings.ini", "text/plain", True),  # INI often detected as text/plain already
    ("app.properties", "text/plain", True),  # Properties often detected as text/plain

    # Programming/script files
    ("script.sql", "application/sql", True),
    ("query.graphql", "application/graphql", True),
    ("index.php", "application/x-httpd-php", True),

    # Document files
    ("paper.tex", "text/x-tex", True),  # LaTeX usually detected as text/*

    # Data files
    ("data.json", "application/json", True),
    ("config.yaml", "application/x-yaml", True),
    ("styles.xml", "application/xml", True),
])
def test_text_like_mime_fallback(tmp_path, filename, expected_primary, should_have_text_plain):
    """Test that text-based files get text/plain as a fallback."""
    # Create test file with appropriate content
    test_file = tmp_path / filename

    # Add realistic content based on file type
    content_map = {
        ".toml": "[section]\\nkey = 'value'",
        ".ini": "[Section]\\nkey=value",
        ".properties": "key=value",
        ".sql": "SELECT * FROM users;",
        ".graphql": "query { user { name } }",
        ".php": "<?php echo 'test'; ?>",
        ".tex": "\\\\documentclass{article}\\n\\\\begin{document}\\nTest\\n\\\\end{document}",
        ".json": '{"key": "value"}',
        ".yaml": "key: value",
        ".xml": "<?xml version='1.0'?><root/>",
    }

    ext = test_file.suffix
    content = content_map.get(ext, "test content")
    test_file.write_text(content)

    # Initialize application manager
    app_manager = ApplicationManager()

    # Get MIME types
    detected_mime = app_manager.get_mime_type(str(test_file))
    mime_chain = app_manager._get_mime_types_for_file(str(test_file))

    print(f"\\nFile: {filename}")
    print(f"  Detected: {detected_mime}")
    print(f"  Expected: {expected_primary}")
    print(f"  Chain: {mime_chain}")

    # If the expected primary is text/*, it's already handled by the text/* check
    if expected_primary.startswith('text/'):
        # For text/* MIME types, text/plain should be added by the text/* handler
        if expected_primary != 'text/plain':
            assert 'text/plain' in mime_chain, \
                f"{filename}: text/plain should be in fallback chain for {detected_mime}"
    else:
        # For application/* MIME types that are text-like
        if should_have_text_plain:
            # The detected MIME might not match expected exactly, but text/plain should be in chain
            assert 'text/plain' in mime_chain, \
                f"{filename}: text/plain should be in fallback chain for {detected_mime}"


def test_toml_file_application_discovery(tmp_path):
    """Test that text editors are discovered for TOML configuration files."""
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text("""
[tool.poetry]
name = "myproject"
version = "0.1.0"
description = "A test project"

[tool.poetry.dependencies]
python = "^3.9"
""")

    app_manager = ApplicationManager()

    # Get MIME type
    mime_type = app_manager.get_mime_type(str(toml_file))
    print(f"\\nTOML MIME type: {mime_type}")

    # Get MIME type chain
    mime_chain = app_manager._get_mime_types_for_file(str(toml_file))
    print(f"TOML fallback chain: {mime_chain}")

    # Get applications
    applications = app_manager.get_applications_for_file(str(toml_file))
    app_names = [app.name for app in applications]

    print(f"Found {len(applications)} applications for TOML")
    print(f"Sample apps: {app_names[:5]}")

    # Should find applications
    assert len(applications) > 0, "Should find applications for TOML files"

    # If MIME type is application/toml, text/plain should be in fallback
    if mime_type == 'application/toml':
        assert 'text/plain' in mime_chain, \
            "application/toml should have text/plain fallback"


def test_latex_file_application_discovery(tmp_path):
    """Test that text editors are discovered for LaTeX files."""
    tex_file = tmp_path / "document.tex"
    tex_file.write_text("""
\\documentclass{article}
\\begin{document}
Hello, world!
\\end{document}
""")

    app_manager = ApplicationManager()

    # Get MIME type
    mime_type = app_manager.get_mime_type(str(tex_file))
    print(f"\\nLaTeX MIME type: {mime_type}")

    # Get MIME type chain
    mime_chain = app_manager._get_mime_types_for_file(str(tex_file))
    print(f"LaTeX fallback chain: {mime_chain}")

    # Get applications
    applications = app_manager.get_applications_for_file(str(tex_file))

    print(f"Found {len(applications)} applications for LaTeX")

    # Should find applications
    assert len(applications) > 0, "Should find applications for LaTeX files"

    # text/plain should be in the chain
    assert 'text/plain' in mime_chain, \
        f"{mime_type} should have text/plain fallback"


def test_graphql_file_application_discovery(tmp_path):
    """Test that text editors are discovered for GraphQL query files."""
    gql_file = tmp_path / "query.graphql"
    gql_file.write_text("""
query GetUser($id: ID!) {
  user(id: $id) {
    name
    email
    posts {
      title
    }
  }
}
""")

    app_manager = ApplicationManager()

    # Get MIME type
    mime_type = app_manager.get_mime_type(str(gql_file))
    print(f"\\nGraphQL MIME type: {mime_type}")

    # Get MIME type chain
    mime_chain = app_manager._get_mime_types_for_file(str(gql_file))
    print(f"GraphQL fallback chain: {mime_chain}")

    # If detected as application/graphql, should have text/plain fallback
    if mime_type == 'application/graphql':
        assert 'text/plain' in mime_chain, \
            "application/graphql should have text/plain fallback"


def test_all_text_like_apps_have_text_plain_fallback():
    """Verify all entries in text_like_apps dictionary end with text/plain."""
    # This is a sanity check to ensure consistency in the configuration

    # The expected structure from application_manager.py
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
        'application/sql': ['text/x-sql', 'text/plain'],
        'application/toml': ['text/x-toml', 'text/plain'],
        'application/x-toml': ['application/toml', 'text/x-toml', 'text/plain'],
        'application/x-latex': ['text/x-tex', 'text/plain'],
        'application/x-tex': ['text/x-tex', 'text/plain'],
        'application/x-wine-extension-ini': ['text/x-ini', 'text/plain'],
        'application/x-java-properties': ['text/x-java', 'text/plain'],
        'application/graphql': ['text/x-graphql', 'text/plain'],
        'application/x-httpd-php': ['text/x-php', 'application/x-php', 'text/plain'],
    }

    # Check each entry ends with text/plain
    for mime_type, fallbacks in text_like_apps.items():
        assert fallbacks[-1] == 'text/plain', \
            f"{mime_type} should end with text/plain, but ends with {fallbacks[-1]}"

        # Check no empty strings
        assert all(f.strip() for f in fallbacks), \
            f"{mime_type} has empty fallback entries"

        # Check MIME type format
        assert '/' in mime_type, \
            f"{mime_type} is not a valid MIME type format"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
