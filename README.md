# LitterBox

An opinionated Linux file manager built with Python3 and PyQt6.

_The entire codebase is written by AI._ This project is an experiment to see how far one can go with [vibe coding](https://en.wikipedia.org/wiki/Vibe_coding), and also a way for me to improve my prompt engineering skills. Many of the commit messages will be AI-generated as well. To be clear, this is primarily a personal testing ground, but I do intend to use the application in the end.

I have an ambivalent relationship with vibe coding, but I realize I can’t stay set in my ways or cling to the past. If this is the future, I’d better adapt to it.

## Key features

* "Places" drop down menu for quick access
* Path bar with buttons
  * `Ctrl+L` switches to text input, `Esc` returns to buttons
* Quick buttons for creating a new folder and a new empty file
* Detailed list view
  * Persistent column sort: The sort stays the same when navigating between folders, and between application sessions.
  * Hidden files are always shown
  * Type-to-filter files and folders with automatic filter bar appearance
    * `Esc` to clear and hide the filter
    * Arrow up/down navigation to focus entries in the filtered list
  * Right-click context menu: "Open with...", "Rename", "Move to trash", "Delete" and "Properties"
  * `Enter` to open a file or a folder
    * Executable files will ask for permission to run before being run
    * Asks if to run in a terminal window if the executable might be a non-GUI application
  * `Backspace` to navigate to parent folder
* Multiple tabs
  * `Ctrl+T` to open a new tab
  * `Ctrl+W` to close the current tab (or use the close button on the tab)
  * Tab row is hidden when only one tab is open
* Properties dialog
  * File information
  * Permissions editing
  * Open-with selection
* Window and column sizes size are saved between sessions
* Live auto-refresh: Open tabs automatically refresh when files/folders are created, removed, renamed or modified by another application (now preserves current selection and scroll position)
* Copy / Cut / Paste with conflict management, using `Ctrl+X`, `Ctrl+C` and `Ctrl+V`

### Keyboard Shortcuts
- **Ctrl+L**: Toggle path edit mode
- **Ctrl+T**: New tab
- **Ctrl+W**: Close current tab
- **Ctrl+Enter**: "Open with" dialog for selected item
- **Alt+Enter**: Properties dialog for selected item
- **Enter**: Open selected item
- **Backspace**: Navigate to parent directory
- **Alt+<**: Jump to first item in list (Emacs-style beginning)
- **Alt+>**: Jump to last item in list (Emacs-style end)
- **Esc**: Clear filter (when active) and exits path edit mode (if active)
- **Ctrl+PageUp**: Select tab to the left
- **Ctrl+PageDown**: Select tab to the right
- **Ctrl+Tab**: Select previously used tab
- **Ctrl+X**: Cut file/folder
- **Ctrl+C**: Copy file/folder
- **Ctrl+V**: Paste file/folder
- **Alt+Shift+N**: Create new folder
- **Ctrl+Shift+N**: Create new empty file
- **F2**: Rename file/folder
- **Delete**: Move selected file(s)/folder(s) to Trash
- **Ctrl+Delete**: Permanently delete the  selected file(s)/folder(s)

Note: Depending on keyboard layout these Emacs-style shortcuts may require holding Shift together with Alt to produce the < and > characters (e.g. on US keyboards Alt+Shift+, and Alt+Shift+.). On Swedish keyboards they map directly to Alt+< and Alt+Shift+<.

## Installation

### Quick Start

This will automatically create a Python Virtual Environment. (I'm not sure I like this approach, I might remove it in the future)

```bash
./run.sh
```

### Manual Installation using venv
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

This code block above is suggested by AI (Claude), but this is just easier:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```
### Manual installation using system PIP

One can also run without a virtual environment. I recommend this because it makes the window looks nicer:

```bash
python3 main.py
```

## System Requirements

- Linux (tested on modern distributions)
- Python 3.8+
- PyQt6
- watchdog (Python library)
- Standard Linux utilities: `xdg-open`, `gio` (for trash functionality)

## Installing the .desktop file

```bash
cp litterbox.desktop ~/.local/share/applications/
nano ~/.local/share/applications/litterbox.desktop
```

The example use `nano`, but use whatever you enjoy.

Edit the `Exec` line to contain the absolute path to LitterBox/main.py. You might need to prefix the path with `python3`. For example  `python3 /absolute/path/to/LitterBox/main.py`

## Testing

LitterBox uses pytest for automated testing. Tests are organized in a structured hierarchy:

```
tests/
├── unit/          # Unit tests for individual components
├── integration/   # Integration tests for workflows
└── manual/        # Manual test scripts (not run automatically)
```

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=src --cov-report=html
```

For detailed information about the testing structure and how to write new tests, see [TESTING.md](TESTING.md).

## Troubleshooting

### Crash Logging
If LitterBox crashes due to an unhandled exception, detailed error information is automatically logged to help with debugging:

**Log Location**: `~/.local/share/litterbox/crash.log`

The log file includes:
- Timestamp of when the crash occurred
- Exception type and error message
- Full stack trace showing where the error originated

The log file is automatically rotated when it exceeds 5 MB (the old log is saved as `crash.log.old`).

To view the crash log:
```bash
cat ~/.local/share/litterbox/crash.log
```

### Missing Dependencies
If you get import errors, ensure PyQt6 is installed:
```bash
pip install PyQt6
```

If automatic live refresh does not work, you may be missing the optional dependency:
```bash
pip install watchdog
```
Without watchdog the application still works; you'll just need to trigger refreshes via actions (they happen automatically after create/rename/delete operations already).

### Trash Functionality
The app tries to use `gio trash` first, then falls back to `trash-cli`. Install one of these:
```bash
# Most desktop environments include gio
sudo apt install glib2-bin

# Or install trash-cli as alternative
sudo apt install trash-cli
```

### File Associations
File opening uses `xdg-open`, which should work with most desktop environments. If files don't open correctly, check your desktop environment's file associations.
