"""
Unit tests for crash logger functionality
"""
import pytest
import sys
import os
from pathlib import Path
import tempfile
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.crash_logger import CrashLogger


class TestCrashLogger:
    """Test crash logger functionality"""

    def test_log_directory_creation(self, tmp_path):
        """Test that log directory is created"""
        # Override log directory for testing
        original_dir = CrashLogger.LOG_DIR
        original_file = CrashLogger.LOG_FILE

        try:
            CrashLogger.LOG_DIR = tmp_path / "test_logs"
            CrashLogger.LOG_FILE = CrashLogger.LOG_DIR / "crash.log"

            CrashLogger.setup()

            assert CrashLogger.LOG_DIR.exists()
            assert CrashLogger.LOG_DIR.is_dir()
        finally:
            CrashLogger.LOG_DIR = original_dir
            CrashLogger.LOG_FILE = original_file

    def test_log_exception(self, tmp_path):
        """Test logging an exception"""
        # Override log directory for testing
        original_dir = CrashLogger.LOG_DIR
        original_file = CrashLogger.LOG_FILE

        try:
            CrashLogger.LOG_DIR = tmp_path / "test_logs"
            CrashLogger.LOG_FILE = CrashLogger.LOG_DIR / "crash.log"

            # Create a test exception
            try:
                raise ValueError("Test error message")
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                CrashLogger.log_exception(exc_type, exc_value, exc_traceback)

            # Verify log file was created
            assert CrashLogger.LOG_FILE.exists()

            # Read and verify log content
            with open(CrashLogger.LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "FATAL ERROR" in content
            assert "ValueError" in content
            assert "Test error message" in content
            assert "Stack Trace:" in content

            # Verify timestamp format (should contain date and time)
            assert datetime.now().strftime("%Y-%m-%d") in content

        finally:
            CrashLogger.LOG_DIR = original_dir
            CrashLogger.LOG_FILE = original_file

    def test_multiple_log_entries(self, tmp_path):
        """Test logging multiple exceptions"""
        # Override log directory for testing
        original_dir = CrashLogger.LOG_DIR
        original_file = CrashLogger.LOG_FILE

        try:
            CrashLogger.LOG_DIR = tmp_path / "test_logs"
            CrashLogger.LOG_FILE = CrashLogger.LOG_DIR / "crash.log"

            # Log first exception
            try:
                raise ValueError("First error")
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                CrashLogger.log_exception(exc_type, exc_value, exc_traceback)

            # Log second exception
            try:
                raise TypeError("Second error")
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                CrashLogger.log_exception(exc_type, exc_value, exc_traceback)

            # Read and verify log content
            with open(CrashLogger.LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()

            # Both exceptions should be in the log
            assert content.count("FATAL ERROR") == 2
            assert "ValueError" in content
            assert "First error" in content
            assert "TypeError" in content
            assert "Second error" in content

        finally:
            CrashLogger.LOG_DIR = original_dir
            CrashLogger.LOG_FILE = original_file

    def test_get_log_path(self):
        """Test getting log path"""
        path = CrashLogger.get_log_path()
        assert isinstance(path, str)
        assert "crash.log" in path

    def test_clear_log(self, tmp_path):
        """Test clearing the log file"""
        # Override log directory for testing
        original_dir = CrashLogger.LOG_DIR
        original_file = CrashLogger.LOG_FILE

        try:
            CrashLogger.LOG_DIR = tmp_path / "test_logs"
            CrashLogger.LOG_FILE = CrashLogger.LOG_DIR / "crash.log"

            # Create a log entry
            try:
                raise ValueError("Test error")
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                CrashLogger.log_exception(exc_type, exc_value, exc_traceback)

            assert CrashLogger.LOG_FILE.exists()

            # Clear the log
            CrashLogger.clear_log()

            # Verify log was deleted
            assert not CrashLogger.LOG_FILE.exists()

        finally:
            CrashLogger.LOG_DIR = original_dir
            CrashLogger.LOG_FILE = original_file

    def test_log_rotation(self, tmp_path):
        """Test log rotation when file exceeds max size"""
        # Override log directory and max size for testing
        original_dir = CrashLogger.LOG_DIR
        original_file = CrashLogger.LOG_FILE
        original_max_size = CrashLogger.MAX_LOG_SIZE

        try:
            CrashLogger.LOG_DIR = tmp_path / "test_logs"
            CrashLogger.LOG_FILE = CrashLogger.LOG_DIR / "crash.log"
            CrashLogger.MAX_LOG_SIZE = 100  # Small size for testing

            # Create a large log entry
            CrashLogger.setup()
            with open(CrashLogger.LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("X" * 150)  # Exceeds MAX_LOG_SIZE

            # Log a new exception (should trigger rotation)
            try:
                raise ValueError("New error after rotation")
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                CrashLogger.log_exception(exc_type, exc_value, exc_traceback)

            # Verify backup was created
            backup_file = CrashLogger.LOG_FILE.with_suffix('.log.old')
            assert backup_file.exists()

            # Verify new log contains the new error
            with open(CrashLogger.LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "New error after rotation" in content

        finally:
            CrashLogger.LOG_DIR = original_dir
            CrashLogger.LOG_FILE = original_file
            CrashLogger.MAX_LOG_SIZE = original_max_size

    def test_exception_handler_installation(self):
        """Test installing the exception handler"""
        original_excepthook = sys.excepthook

        try:
            CrashLogger.install_exception_handler()
            assert sys.excepthook == CrashLogger.log_exception
        finally:
            sys.excepthook = original_excepthook

    def test_nested_exception_stack_trace(self, tmp_path):
        """Test that nested exceptions produce proper stack traces"""
        # Override log directory for testing
        original_dir = CrashLogger.LOG_DIR
        original_file = CrashLogger.LOG_FILE

        try:
            CrashLogger.LOG_DIR = tmp_path / "test_logs"
            CrashLogger.LOG_FILE = CrashLogger.LOG_DIR / "crash.log"

            def level3():
                raise RuntimeError("Deep error")

            def level2():
                level3()

            def level1():
                level2()

            # Create nested exception
            try:
                level1()
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                CrashLogger.log_exception(exc_type, exc_value, exc_traceback)

            # Read and verify log content
            with open(CrashLogger.LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()

            # Should show all levels in stack trace
            assert "level1" in content
            assert "level2" in content
            assert "level3" in content
            assert "Deep error" in content

        finally:
            CrashLogger.LOG_DIR = original_dir
            CrashLogger.LOG_FILE = original_file


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
