#!/usr/bin/env python3
"""
Manual test script to verify JSON file application discovery with text/plain fallback
"""
import sys
sys.path.insert(0, 'src')

from core.application_manager import ApplicationManager

def test_json_file():
    """Test JSON file application discovery"""
    manager = ApplicationManager()
    json_file = '/tmp/test_sample.json'

    print(f"Testing application discovery for: {json_file}\n")

    # Get MIME type
    mime_type = manager.get_mime_type(json_file)
    print(f"Primary MIME type: {mime_type}")

    # Get MIME type chain with fallbacks
    mime_chain = manager._get_mime_types_for_file(json_file)
    print(f"\nMIME type fallback chain:")
    for i, mt in enumerate(mime_chain, 1):
        print(f"  {i}. {mt}")

    # Check if text/plain is in the chain
    if 'text/plain' in mime_chain:
        print("\n✓ text/plain fallback IS included")
    else:
        print("\n✗ text/plain fallback NOT included")

    # Check if the file appears to be text
    is_text = manager._appears_to_be_text(json_file)
    print(f"\nFile detected as text: {is_text}")

    # Get applications
    print("\nFinding applications...")
    apps = manager.get_applications_for_file(json_file)

    print(f"\nFound {len(apps)} application(s):")
    for i, app in enumerate(apps[:10], 1):  # Show first 10
        print(f"  {i}. {app.name}")

    if len(apps) > 10:
        print(f"  ... and {len(apps) - 10} more")

    # Get default application
    default_app = manager.get_default_application(json_file)
    if default_app:
        print(f"\nDefault application: {default_app.name}")
    else:
        print("\nNo default application set")

if __name__ == '__main__':
    test_json_file()
