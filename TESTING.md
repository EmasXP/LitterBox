# Testing Guide for LitterBox

## Testing Philosophy

**Tests are not optional - they are part of the implementation.**

When working on this project:
- ✅ **Add a feature** → Write tests for it
- ✅ **Fix a bug** → Add a test that would have caught it
- ✅ **Refactor code** → Ensure tests still pass, add new ones if needed
- ✅ **Modify functionality** → Update related tests

If you're an AI assistant helping with this project, always propose or create tests even if the user doesn't explicitly ask for them. Testing is part of good development practice.

## Directory Structure

```
tests/
├── conftest.py           # Shared pytest fixtures (QApplication, etc.)
├── __init__.py
├── unit/                 # Unit tests - test individual components in isolation
│   ├── __init__.py
│   ├── test_crash_logger.py
│   ├── test_application_discovery.py
│   ├── test_icon_fetching.py
│   ├── test_mime_fetching.py
│   ├── test_shift_navigation.py
│   ├── test_filter_selection.py
│   └── test_selection_persistence.py
├── integration/          # Integration tests - test multiple components together
│   ├── __init__.py
│   ├── test_copy_paste.py
│   └── test_infinite_recursion.py
└── manual/              # Manual test scripts for investigation/debugging
    ├── crash_logger_manual_test.py
    └── smart_detection_demo.py
```

## Test Categories

### Unit Tests (`tests/unit/`)
Unit tests verify individual components or functions in isolation. They should:
- Test a single unit of functionality
- Be fast to execute
- Not require user interaction
- Mock external dependencies when appropriate
- Use pytest assertions and fixtures

**Examples:**
- Testing MIME type detection logic
- Testing icon fetching behavior
- Testing UI component behavior in isolation

### Integration Tests (`tests/integration/`)
Integration tests verify that multiple components work correctly together. They may:
- Test file system operations
- Test complex workflows involving multiple classes
- Use temporary directories for file operations
- Take longer to execute than unit tests

**Examples:**
- Testing file copy/paste operations end-to-end
- Testing file transfer with conflict resolution
- Testing infinite recursion detection across file operations

### Manual Tests (`tests/manual/`)
Manual test scripts are NOT run by pytest automatically. They are:
- Scripts for manual testing or debugging
- Demonstration programs for specific features
- Investigation tools created during development
- Should NOT follow pytest naming conventions (avoid `test_*.py` prefix)

**Examples:**
- Scripts that deliberately crash to test logging
- Interactive demos for features
- Performance testing tools

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run a specific test file
pytest tests/unit/test_crash_logger.py

# Run a specific test function
pytest tests/unit/test_crash_logger.py::TestCrashLogger::test_log_exception
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
```

### Run Tests in Parallel (if pytest-xdist is installed)
```bash
pytest -n auto
```

## Writing Tests

### Naming Conventions

1. **Test files**: Must start with `test_` (e.g., `test_feature_name.py`)
2. **Test classes**: Must start with `Test` (e.g., `class TestClassName:`)
3. **Test functions**: Must start with `test_` (e.g., `def test_feature():`)
4. **Manual scripts**: Should NOT start with `test_` to avoid pytest discovery

### Using Fixtures

Common fixtures are defined in `tests/conftest.py`:

```python
def test_something(qapp):
    """qapp fixture provides QApplication instance for PyQt tests"""
    # Your test code here
    pass

def test_with_temp_dir(tmp_path):
    """tmp_path is a pytest built-in fixture providing temporary directory"""
    test_file = tmp_path / "file.txt"
    test_file.write_text("content")
    # Your test code here
```

### Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures and context managers for proper resource cleanup
3. **Assertions**: Use clear, descriptive assertion messages
4. **Mocking**: Mock external dependencies (file system, network, etc.) when appropriate
5. **Temporary Files**: Always use `tmp_path` or `tempfile` for file operations
6. **Qt Tests**: Use the `qapp` fixture for PyQt/Qt tests

### Example Unit Test

```python
import pytest
from src.core.some_module import SomeClass

def test_some_functionality():
    """Test that SomeClass does something correctly"""
    obj = SomeClass()
    result = obj.some_method("input")
    assert result == "expected_output"
    assert obj.state == "expected_state"
```

### Example Integration Test

```python
import pytest
from pathlib import Path
from src.core.file_operations import FileOperations

def test_file_copy_operation(tmp_path):
    """Test complete file copy workflow"""
    source = tmp_path / "source" / "file.txt"
    source.parent.mkdir()
    source.write_text("test content")

    dest = tmp_path / "dest"
    dest.mkdir()

    ops = FileOperations()
    ops.copy_file(str(source), str(dest))

    copied = dest / "file.txt"
    assert copied.exists()
    assert copied.read_text() == "test content"
```

## PyQt/GUI Testing

GUI tests require special handling:

1. **QApplication**: Use the `qapp` fixture from `conftest.py`
2. **Offscreen Platform**: Tests run with `QT_QPA_PLATFORM=offscreen` to avoid GUI display
3. **Event Processing**: Use `QApplication.processEvents()` or `QTest.qWait()` when needed
4. **Cleanup**: Always call `.deleteLater()` on Qt objects when done

## Configuration

The `pytest.ini` file in the project root configures pytest behavior:
- Test discovery patterns
- Output verbosity
- Markers for categorizing tests
- Directories to exclude from test discovery

## For AI Assistants

When creating new tests:

1. **Determine test type first**: Is it a unit test, integration test, or manual script?
2. **Use correct directory**:
   - `tests/unit/` for isolated component tests
   - `tests/integration/` for multi-component workflow tests
   - `tests/manual/` for investigation/debugging scripts (use descriptive names, NOT `test_*.py`)
3. **Follow naming conventions**: Files must start with `test_` for pytest discovery (except manual scripts)
4. **Use existing fixtures**: Check `conftest.py` for available fixtures (especially `qapp` for Qt tests)
5. **Keep tests focused**: Each test function should test one specific behavior
6. **Add docstrings**: Explain what the test verifies
7. **Use tmp_path**: For any file system operations, use pytest's `tmp_path` fixture
8. **Mock when appropriate**: Don't make real network calls or modify system state unnecessarily

### Quick Decision Tree for Test Placement

```
Is it automated (pytest)?
├─ Yes
│  ├─ Tests single component? → tests/unit/test_<feature>.py
│  └─ Tests multiple components? → tests/integration/test_<feature>.py
└─ No (manual/interactive/debugging)
   └─ tests/manual/<descriptive_name>.py (NOT test_*.py)
```

## Continuous Integration

When running tests in CI:
- All tests in `tests/unit/` and `tests/integration/` are run automatically
- Manual tests in `tests/manual/` are excluded from automated runs
- Tests run with offscreen Qt platform to avoid display requirements
- Coverage reports are generated

## Troubleshooting

### "No tests collected"
- Ensure test files start with `test_`
- Ensure test functions start with `test_`
- Check that the file is in `tests/` directory
- Check `pytest.ini` for excluded directories

### Qt/PyQt segmentation faults
- Ensure you're using the `qapp` fixture
- Check that `QT_QPA_PLATFORM=offscreen` is set
- Verify that Qt objects are properly cleaned up

### Import errors
- Ensure `sys.path.insert(0, 'src')` is used if needed
- Check that relative imports are correct
- Verify that `__init__.py` files exist in test directories

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [PyQt testing guide](https://pytest-qt.readthedocs.io/)
- Project-specific test examples in `tests/unit/` and `tests/integration/`
