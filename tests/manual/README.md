# Manual Test Scripts

This directory contains manual test scripts and investigation tools that are **NOT** run automatically by pytest.

## Purpose

These scripts are used for:
- **Manual testing** of specific features that require user interaction
- **Debugging** and investigation during development
- **Demonstrations** of features or behaviors
- **Interactive testing** that can't be automated

## Important Notes

⚠️ **These files do NOT follow pytest naming conventions on purpose** to prevent them from being discovered and run by pytest.

⚠️ **These scripts may intentionally crash** or require user interaction. They are not part of the automated test suite.

## Available Scripts

### `crash_logger_manual_test.py`
Manual test script to verify crash logging functionality. This script deliberately raises exceptions to test that they are properly logged to the crash log file.

**Usage:**
```bash
# Test basic exception logging
python tests/manual/crash_logger_manual_test.py basic

# Test nested exception with stack trace
python tests/manual/crash_logger_manual_test.py nested

# Test attribute error
python tests/manual/crash_logger_manual_test.py attr
```

### `smart_detection_demo.py`
Demonstration and testing script for the smart executable detection system. Shows how the system detects different types of executables (GUI apps, console apps, scripts) and decides how to run them.

**Usage:**
```bash
python tests/manual/smart_detection_demo.py
```

### `multi_delete_demo.py`
Demonstration and testing script for multi-selection delete/trash functionality. Creates a temporary test directory with sample files to verify that:
- Multiple files can be selected
- Context menu shows item count for multiple selections
- Delete and trash operations work on all selected items
- Confirmation dialogs are properly formatted
- Error handling works for partial failures

**Usage:**
```bash
python tests/manual/multi_delete_demo.py
```

Follow the on-screen instructions to test selecting multiple files and using the delete/trash features.


## Creating New Manual Scripts

When creating investigation or manual test scripts:

1. **Place them in this directory** (`tests/manual/`)
2. **Use descriptive names** that explain the purpose (e.g., `feature_name_demo.py`, `debug_feature.py`)
3. **Do NOT use `test_` prefix** to avoid pytest discovery
4. **Document the purpose** in comments at the top of the file
5. **Add usage instructions** in this README

## For AI Assistants

When an AI creates investigation scripts or manual test tools:
- Save them to `tests/manual/` directory
- Do NOT use `test_*.py` naming pattern
- Use descriptive names like `<feature>_demo.py` or `<feature>_manual_test.py`
- Add appropriate documentation in the file header
- Update this README with usage instructions if the script is useful for future reference
