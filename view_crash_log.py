#!/usr/bin/env python3
"""
Utility script to view and manage LitterBox crash logs
"""
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.crash_logger import CrashLogger


def main():
    """Main function to manage crash logs"""
    if len(sys.argv) < 2:
        print("LitterBox Crash Log Manager")
        print(f"Log file location: {CrashLogger.get_log_path()}")
        print()
        print("Usage:")
        print(f"  {sys.argv[0]} view    - View the crash log")
        print(f"  {sys.argv[0]} clear   - Clear the crash log")
        print(f"  {sys.argv[0]} path    - Show the log file path")
        print(f"  {sys.argv[0]} exists  - Check if log file exists")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "view":
        log_path = Path(CrashLogger.get_log_path())
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    print(content)
                else:
                    print("Log file is empty.")
        else:
            print(f"No crash log found at: {log_path}")

    elif command == "clear":
        log_path = Path(CrashLogger.get_log_path())
        if log_path.exists():
            CrashLogger.clear_log()
            print(f"Crash log cleared: {log_path}")
        else:
            print(f"No crash log to clear at: {log_path}")

    elif command == "path":
        print(CrashLogger.get_log_path())

    elif command == "exists":
        log_path = Path(CrashLogger.get_log_path())
        if log_path.exists():
            size = log_path.stat().st_size
            print(f"Log file exists: {log_path}")
            print(f"Size: {size:,} bytes")

            # Count number of crash entries
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                crash_count = content.count("FATAL ERROR -")
            print(f"Number of crashes logged: {crash_count}")
        else:
            print(f"No log file exists at: {log_path}")

    else:
        print(f"Unknown command: {command}")
        print("Use 'view', 'clear', 'path', or 'exists'")
        sys.exit(1)


if __name__ == "__main__":
    main()
