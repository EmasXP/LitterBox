# GitHub Copilot Instructions for LitterBox

## Testing Philosophy

**ALWAYS create or update tests when adding or modifying functionality.**

When you:
- Add a new feature → Write tests for it
- Fix a bug → Add a test that would have caught the bug
- Refactor code → Ensure existing tests still pass and add new ones if coverage gaps exist
- Modify existing functionality → Review and update related tests

If the user doesn't explicitly ask for tests, create them anyway as part of good development practice.

## Testing Guidelines

When creating or modifying tests in this project:

### Test Organization

1. **Unit Tests** go in `tests/unit/`
   - Test individual functions, classes, or modules in isolation
   - Mock external dependencies
   - Fast execution
   - File naming: `test_<feature_name>.py`

2. **Integration Tests** go in `tests/integration/`
   - Test multiple components working together
   - May use file system, temporary directories
   - Test complete workflows
   - File naming: `test_<feature_name>.py`

3. **Manual/Investigation Scripts** go in `tests/manual/`
   - Scripts for debugging or manual testing
   - NOT automatically run by pytest
   - File naming: `<descriptive_name>.py` (do NOT use `test_` prefix)

### File Naming

- ✅ Automated tests: `test_feature_name.py` (in tests/unit/ or tests/integration/)
- ✅ Manual scripts: `feature_demo.py` or `feature_manual_test.py` (in tests/manual/)
- ❌ Avoid: `test_*.py` files in root directory

### Import Pattern

Tests automatically import from `src/` via conftest.py. Just use:
```python
from core.module_name import ClassName
from ui.component_name import Component
from utils.utility_name import utility_function
```

### PyQt/GUI Testing

For tests involving Qt/PyQt6:
```python
def test_something(qapp):
    """qapp fixture provides QApplication"""
    # Test code here
```

The `qapp` fixture is defined in `tests/conftest.py` and provides a single QApplication instance for all tests.

### Quick Reference

**New unit test?** → Create `tests/unit/test_<name>.py`
**New integration test?** → Create `tests/integration/test_<name>.py`
**Investigation script?** → Create `tests/manual/<name>_demo.py` (no `test_` prefix!)

### Test Coverage Expectations

When implementing new code:
1. **Always suggest tests** - Even if the user doesn't ask, propose adding tests
2. **Test edge cases** - Don't just test the happy path
3. **Test error conditions** - Verify proper error handling
4. **Keep tests maintainable** - Clear names, good documentation, focused assertions

See [TESTING.md](TESTING.md) for complete documentation.

## Code Style

- Use type hints where appropriate
- Follow PEP 8 conventions
- Keep functions focused and single-purpose
- Document complex logic with comments

## Project Structure

```
LitterBox/
├── src/
│   ├── core/        # Business logic (file operations, app management)
│   ├── ui/          # User interface components
│   └── utils/       # Utilities (settings, crash logging)
├── tests/
│   ├── unit/        # Automated unit tests
│   ├── integration/ # Automated integration tests
│   └── manual/      # Manual test scripts
└── main.py          # Application entry point
```

## Common Patterns

### File Operations
Use `FileOperations` class from `src/core/file_operations.py` for file system operations.

### Application Manager
Use `ApplicationManager` from `src/core/application_manager.py` for desktop application detection and MIME types.

### Settings
Use `Settings` from `src/utils/settings.py` for persistent configuration.

### Crash Logging
The crash logger in `src/utils/crash_logger.py` automatically handles unhandled exceptions.

## Development Workflow with Tests

### When Adding New Features
1. Write the test first (TDD) or immediately after implementing
2. Run tests to verify they pass: `pytest tests/unit/test_<feature>.py -v`
3. Consider both unit tests (isolated component) and integration tests (workflow)

### When Fixing Bugs
1. Write a test that reproduces the bug
2. Verify the test fails with the current code
3. Fix the bug
4. Verify the test now passes
5. Add the test to prevent regression

### When Refactoring
1. Run existing tests before refactoring: `pytest`
2. Refactor the code
3. Run tests again to ensure nothing broke
4. Add new tests if you discover gaps in coverage

### Proactive Test Suggestions

When a user asks you to implement something, proactively say:
- "I'll also create tests for this functionality"
- "Would you like me to add tests for edge cases?"
- "Let me verify this works by running the tests"

Don't wait to be asked - testing is part of the implementation process.
