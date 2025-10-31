"""
Crash logging utility for LitterBox
Logs fatal exceptions with timestamps and stack traces to a log file.
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path
import os


class CrashLogger:
    """Logger for fatal crashes and exceptions"""

    # Log file location in user's cache/config directory
    LOG_DIR = Path.home() / ".local" / "share" / "litterbox"
    LOG_FILE = LOG_DIR / "crash.log"
    MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB

    @classmethod
    def setup(cls):
        """Setup the crash logger directory"""
        try:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If we can't create the directory, fall back to current directory
            cls.LOG_DIR = Path.cwd()
            cls.LOG_FILE = cls.LOG_DIR / "crash.log"

    @classmethod
    def log_exception(cls, exc_type, exc_value, exc_traceback):
        """
        Log an exception with full stack trace and timestamp.

        Args:
            exc_type: Exception type
            exc_value: Exception instance
            exc_traceback: Exception traceback
        """
        try:
            cls.setup()

            # Check log file size and rotate if needed
            cls._rotate_log_if_needed()

            # Format the log entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            separator = "=" * 80

            log_entry = f"\n{separator}\n"
            log_entry += f"FATAL ERROR - {timestamp}\n"
            log_entry += f"{separator}\n"

            # Add exception information
            log_entry += f"Exception Type: {exc_type.__name__}\n"
            log_entry += f"Exception Message: {str(exc_value)}\n"
            log_entry += f"\nStack Trace:\n"
            log_entry += "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            log_entry += f"{separator}\n"

            # Write to log file
            with open(cls.LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)

            # Also print to stderr for immediate visibility
            print(f"\nFATAL ERROR logged to: {cls.LOG_FILE}", file=sys.stderr)
            print(log_entry, file=sys.stderr)

        except Exception as e:
            # If logging fails, at least print to stderr
            print(f"Failed to write crash log: {e}", file=sys.stderr)
            traceback.print_exception(exc_type, exc_value, exc_traceback)

    @classmethod
    def _rotate_log_if_needed(cls):
        """Rotate log file if it exceeds maximum size"""
        try:
            if cls.LOG_FILE.exists():
                file_size = cls.LOG_FILE.stat().st_size
                if file_size > cls.MAX_LOG_SIZE:
                    # Rename old log file
                    backup_file = cls.LOG_FILE.with_suffix('.log.old')
                    if backup_file.exists():
                        backup_file.unlink()
                    cls.LOG_FILE.rename(backup_file)
        except Exception:
            # If rotation fails, continue anyway
            pass

    @classmethod
    def install_exception_handler(cls):
        """Install the crash logger as the global exception handler"""
        sys.excepthook = cls.log_exception

    @classmethod
    def get_log_path(cls) -> str:
        """Get the path to the log file"""
        cls.setup()
        return str(cls.LOG_FILE)

    @classmethod
    def clear_log(cls):
        """Clear the crash log file"""
        try:
            if cls.LOG_FILE.exists():
                cls.LOG_FILE.unlink()
        except Exception as e:
            print(f"Failed to clear log: {e}", file=sys.stderr)
