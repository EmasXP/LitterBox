# Crash Logging Feature

## Overview
LitterBox now includes automatic crash logging functionality that captures and logs all unhandled exceptions with full stack traces and timestamps.

## Features

### Automatic Exception Logging
- All fatal crashes are automatically logged
- Logs include:
  - Timestamp (date and time)
  - Exception type
  - Error message
  - Full stack trace showing the call chain

### Log File Management
- **Location**: `~/.local/share/litterbox/crash.log`
- **Automatic rotation**: When log exceeds 5 MB, old log is saved as `crash.log.old`
- **Format**: Human-readable text with clear separators between entries

### Utility Scripts

#### View/Manage Logs
Use `view_crash_log.py` to manage crash logs:

```bash
# View all crash logs
python3 view_crash_log.py view

# Check if log exists and get stats
python3 view_crash_log.py exists

# Get log file path
python3 view_crash_log.py path

# Clear the log file
python3 view_crash_log.py clear
```

#### Test Crash Logger
Use `test_crash_logger.py` to test the crash logging functionality:

```bash
# Test basic exception logging
python3 test_crash_logger.py basic

# Test nested exception with full stack trace
python3 test_crash_logger.py nested

# Test attribute error
python3 test_crash_logger.py attr
```

## Implementation Details

### Files Added
1. **src/utils/crash_logger.py** - Core crash logging implementation
   - `CrashLogger` class with static methods
   - Automatic log rotation
   - Exception handler installation

2. **view_crash_log.py** - Utility script for log management
   - View, clear, and check log status

3. **test_crash_logger.py** - Manual testing script
   - Tests various exception types
   - Demonstrates crash logging in action

4. **test_crash_logger_unit.py** - Unit tests
   - Comprehensive test coverage
   - Tests log rotation, multiple entries, stack traces

### Integration
The crash logger is integrated into the main application entry point (`main.py`):

```python
from utils.crash_logger import CrashLogger

def main():
    # Install crash logger to catch unhandled exceptions
    CrashLogger.install_exception_handler()
    # ... rest of application startup
```

### Example Log Entry
```
================================================================================
FATAL ERROR - 2025-10-31 09:51:27
================================================================================
Exception Type: ZeroDivisionError
Exception Message: division by zero

Stack Trace:
Traceback (most recent call last):
  File "/path/to/test_crash_logger.py", line 59, in <module>
    test_nested_exception()
  File "/path/to/test_crash_logger.py", line 41, in test_nested_exception
    level1()
  File "/path/to/test_crash_logger.py", line 34, in level1
    return level2()
  File "/path/to/test_crash_logger.py", line 31, in level2
    return level3()
  File "/path/to/test_crash_logger.py", line 28, in level3
    return 1 / 0  # Division by zero
ZeroDivisionError: division by zero
================================================================================
```

## Benefits
1. **Easy debugging**: Full stack traces help identify crash causes
2. **User support**: Users can share log files when reporting bugs
3. **Crash history**: Multiple crashes are logged sequentially
4. **Non-intrusive**: Errors are logged to stderr and file, no GUI interruption
5. **Automatic**: No user action required - works out of the box

## Notes
- Logs are written to `~/.local/share/litterbox/` following XDG standards
- If the directory can't be created, falls back to current directory
- Old logs are preserved when rotating (`.log.old` suffix)
- Error output is also printed to stderr for immediate visibility
