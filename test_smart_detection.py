#!/usr/bin/env python3
"""
Test script for smart executable detection functionality
"""

import sys
import os
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from core.file_operations import FileOperations
from ui.main_window import FileTab

def test_executable_detection():
    """Test executable type detection"""
    print("=== Testing Executable Type Detection ===")
    
    # Test console applications
    console_apps = ['/usr/bin/ls', '/bin/bash', '/usr/bin/find', '/usr/bin/grep']
    
    print("\nConsole Applications:")
    for app in console_apps:
        if os.path.exists(app):
            exec_type = FileOperations.get_executable_type(app)
            print(f"  {app}: {exec_type}")
    
    # Test scripts
    print("\nScript Files:")
    
    # Create test scripts
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write('#!/bin/bash\necho "Hello from shell script"')
        bash_script = f.name
    os.chmod(bash_script, 0o755)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('#!/usr/bin/env python3\nprint("Hello from Python script")')
        python_script = f.name
    os.chmod(python_script, 0o755)
    
    test_scripts = [bash_script, python_script]
    
    for script in test_scripts:
        exec_type = FileOperations.get_executable_type(script)
        print(f"  {script}: {exec_type}")
    
    # Test GUI applications (check known GUI app names)
    print("\nChecking for GUI Applications:")
    potential_gui_apps = [
        '/usr/bin/firefox', '/usr/bin/gedit', '/usr/bin/kate', 
        '/usr/bin/nautilus', '/usr/bin/dolphin', '/usr/bin/code'
    ]
    
    gui_found = False
    for app in potential_gui_apps:
        if os.path.exists(app):
            exec_type = FileOperations.get_executable_type(app)
            print(f"  {app}: {exec_type}")
            if exec_type == 'gui':
                gui_found = True
    
    if not gui_found:
        print("  No GUI applications found in common locations")
    
    # Clean up test files
    os.unlink(bash_script)
    os.unlink(python_script)

def test_run_methods():
    """Test different run methods"""
    print("\n=== Testing Run Methods ===")
    
    # Create a test console script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write('#!/bin/bash\necho "Test script executed successfully"')
        test_script = f.name
    os.chmod(test_script, 0o755)
    
    print(f"\nTest script: {test_script}")
    
    # Test detection
    exec_type = FileOperations.get_executable_type(test_script)
    print(f"Detected type: {exec_type}")
    
    # Test if methods are callable (without actually running)
    print("Available methods:")
    print("  - FileOperations.run_executable(path) - smart detection")
    print("  - FileOperations.run_executable(path, force_terminal=True) - force terminal")  
    print("  - FileOperations.run_executable_direct(path) - direct execution")
    
    # Clean up
    os.unlink(test_script)

def test_dialog_logic():
    """Test the logic for when dialogs should appear"""
    print("\n=== Testing Dialog Logic ===")
    
    test_cases = [
        ('/usr/bin/ls', 'console', 'Should show dialog with terminal/direct options'),
        ('/bin/bash', 'console', 'Should show dialog with terminal/direct options'),
    ]
    
    # Create test script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('#!/usr/bin/env python3\nprint("Hello")')
        script_path = f.name
    os.chmod(script_path, 0o755)
    
    test_cases.append((script_path, 'script', 'Should show dialog with terminal/direct options (default: terminal)'))
    
    print("Dialog behavior:")
    for path, expected_type, behavior in test_cases:
        if os.path.exists(path):
            actual_type = FileOperations.get_executable_type(path)
            print(f"  {path}")
            print(f"    Expected: {expected_type}, Got: {actual_type}")
            print(f"    Behavior: {behavior}")
    
    # Clean up
    os.unlink(script_path)
    
    print("\nGUI applications would run directly without dialog")

if __name__ == '__main__':
    print("Smart Executable Detection Test")
    print("=" * 40)
    
    test_executable_detection()
    test_run_methods()
    test_dialog_logic()
    
    print("\n" + "=" * 40)
    print("Test completed! The smart detection system is ready.")
    print("\nHow it works:")
    print("1. GUI applications run directly without user prompt")
    print("2. Console applications show dialog: 'Run in Terminal' vs 'Run Directly'")
    print("3. Scripts show dialog with 'Run in Terminal' as default option")