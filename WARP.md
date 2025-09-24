# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**LitterBox** is an opinionated Linux file manager built with Python3 and PyQt6. The entire codebase is AI-generated as an experiment in "vibe coding" and prompt engineering. It provides a modern, keyboard-friendly file management interface with features like tabbed browsing, type-to-filter, and comprehensive file operations.

## Architecture

### Core Structure
- **Entry Point**: `main.py` - Sets up PyQt6 application and launches MainWindow
- **Source Code**: All implementation code lives in `src/` directory
- **Modular Design**: Clean separation between UI, core logic, and utilities

### Key Components

#### UI Layer (`src/ui/`)
- **MainWindow** (`main_window.py`): Main application window with tab management, filter bar, and keyboard shortcuts
- **FileTab** (`main_window.py`): Individual tab containing file list and navigation logic
- **FileListView** (`file_list_view.py`): Custom QTreeView with proxy model for sorting and filtering
- **PathNavigator** (`path_navigator.py`): Clickable breadcrumb path with edit mode (Ctrl+L)
- **PlacesButton** (`places_button.py`): Quick navigation dropdown for standard directories
- **PropertiesDialog** (`properties_dialog.py`): File properties and permissions editor
- **ApplicationSelectionDialog** (`application_selection_dialog.py`): "Open with" application selector

#### Core Logic (`src/core/`)
- **FileOperations** (`file_operations.py`): All file system operations (create, rename, delete, trash, etc.)
- **ApplicationManager** (`application_manager.py`): System application detection and file associations

#### Utilities (`src/utils/`)
- **Settings** (`settings.py`): Persistent configuration management (`~/.config/filemanager/settings.json`)

### Key Architectural Patterns

#### PyQt6 Signal/Slot Architecture
The application heavily uses PyQt6's signal/slot system for loose coupling:
- `FileTab.path_changed` → Updates window title and toolbar path
- `FileListView.item_double_clicked` → Handles file/folder activation
- `FilterBar.filter_changed` → Updates file list filtering in real-time

#### Model-View Pattern
- **Source Model**: `QStandardItemModel` holds file data
- **Proxy Model**: `FileSortProxyModel` handles filtering and custom sorting (directories first)
- **View**: `FileListView` (QTreeView) displays the filtered/sorted data

#### Settings Persistence
All user preferences (window size, sort order, column widths) are automatically saved to `~/.config/filemanager/settings.json` using the Settings utility class.

## Common Development Commands

### Run Application
```bash
# Quick start (preferred)
./run.sh

# Manual setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Development Environment
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (only PyQt6 currently)
pip install -r requirements.txt

# Run directly
python main.py

# Run from specific directory
cd /path/to/LitterBox && python main.py
```

### Testing
The project has several test files (not formal unit tests):
```bash
# Various manual test scripts exist:
python test.py                    # Basic functionality tests
python test_executable_fix.py     # Executable handling tests
python test_open_with.py          # "Open with" dialog tests
python test_rename_functionality.py  # Rename operation tests
python test_scrolling.py          # UI scrolling tests
python test_ui_changes.py         # UI behavior tests

# Run test script
./test_script.sh
```

## Key Development Guidelines

### File Operations
- All file system operations go through `FileOperations` class
- Always return tuple of `(success: bool, result: str)` for error handling
- Use `Path` objects internally, convert to strings for UI display
- Support both `gio trash` and `trash-cli` for Linux desktop compatibility

### UI Components
- Use PyQt6 signal/slot pattern for component communication  
- Filter bar appears automatically on typing and supports arrow key navigation
- Path navigation supports both button clicks and Ctrl+L text edit mode
- Context menus provide standard file operations (Open, Rename, Delete, Properties)

### Settings Management
- Use `Settings` class for all persistent configuration
- Window geometry and sort preferences are automatically saved
- Settings are stored in standard Linux config location (`~/.config/filemanager/`)

### Error Handling
- Show user-friendly error dialogs with `QMessageBox.warning()`
- File operations should gracefully handle permissions errors
- Missing system dependencies (trash commands) should fall back appropriately

## System Dependencies

### Required
- **Python 3.8+**
- **PyQt6** (automatically installed via requirements.txt)
- **Linux** (tested on modern distributions)

### Optional System Tools
- **gio** (most desktop environments) - for trash functionality
- **trash-cli** - fallback trash command
- **xdg-open** - for opening files with default applications
- **gnome-terminal**, **konsole**, **xterm** - for running executables

## Configuration

### User Settings Location
- Settings file: `~/.config/filemanager/settings.json`
- Automatically created on first run
- Contains window geometry, sort preferences, column widths

### Keyboard Shortcuts
- **Ctrl+L**: Toggle path edit mode
- **Ctrl+W**: Close current tab
- **Ctrl+T**: New tab (opens in same location as current tab)
- **Ctrl+Enter**: Properties dialog
- **Enter**: Open selected item
- **Backspace**: Navigate to parent directory
- **F2**: Rename selected item
- **Esc**: Clear filter (when active)
- **Type to filter**: Automatically shows filter bar

## Development Notes

### Executable File Handling
When executable files are activated, the application shows a dialog offering to "Run" or "Edit" (for text-based executables). Running opens a terminal window that stays open after execution.

### Filter System
The type-to-filter system uses a regex-based proxy model that filters on filename only (not full path). The filter bar appears at the bottom and supports keyboard navigation while active.

### Tab Management  
New tabs open in the same directory as the current tab. The tab bar is hidden when only one tab is open. Each tab maintains its own navigation history and filter state.

### Custom Sorting
Files are sorted with directories always appearing first, regardless of sort order. The sorting system uses a custom proxy model that overrides `lessThan()` to implement this behavior while respecting user sort preferences.