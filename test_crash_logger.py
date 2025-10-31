#!/usr/bin/env python3
"""
Test script for crash logger functionality
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.crash_logger import CrashLogger


def test_basic_exception():
    """Test logging a basic exception"""
    print("Testing basic exception logging...")
    CrashLogger.install_exception_handler()

    print(f"Log file will be written to: {CrashLogger.get_log_path()}")

    # This should be caught and logged
    raise ValueError("This is a test error to verify crash logging works!")


def test_nested_exception():
    """Test logging with nested function calls"""
    def level3():
        return 1 / 0  # Division by zero

    def level2():
        return level3()

    def level1():
        return level2()

    print("Testing nested exception with stack trace...")
    CrashLogger.install_exception_handler()

    print(f"Log file will be written to: {CrashLogger.get_log_path()}")

    level1()


def test_attribute_error():
    """Test logging an attribute error"""
    print("Testing attribute error logging...")
    CrashLogger.install_exception_handler()

    print(f"Log file will be written to: {CrashLogger.get_log_path()}")

    obj = None
    obj.some_method()  # This will raise AttributeError


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "nested":
            test_nested_exception()
        elif test_type == "attr":
            test_attribute_error()
        else:
            test_basic_exception()
    else:
        print("Usage: python test_crash_logger.py [basic|nested|attr]")
        print("Running basic test by default...\n")
        test_basic_exception()
