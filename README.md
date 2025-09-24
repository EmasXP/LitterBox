# LitterBox

An opinionated Linux file manager built with Python3 and PyQt6.

_The entire code base is entirely written by AI_. This project is an experiment on how far one can go with [vibe coding](https://en.wikipedia.org/wiki/Vibe_coding), and also for me to better learn prompt engineering. Many of the commit messages are going to be AI generated too. To be clear, this is a personal testing ground for me, but I do plan to use the application in the end too.

In fact, the remainder of this README is written by AI too:

## Features

### Core Interface
- **Toolbar**: Places button, path navigation as clickable buttons, new folder/file creation buttons
- **Detailed List View**: Shows files and folders with Name (with icons), Size, and Modified columns
- **Tab Support**: Multiple tabs with tab bar hidden when only one tab is open
- **Filter System**: Type-to-filter files with automatic filter bar appearance
- **Places Dropdown**: Quick navigation to standard directories (Home, Desktop, Downloads, etc.)

### Navigation
- **Path Buttons**: Click any path component to navigate there
- **Path Edit Mode**: Ctrl+L switches to text input, Esc returns to buttons
- **Keyboard Navigation**:
  - Backspace: Go to parent directory
  - Enter: Open selected file/folder
  - Arrow keys: Navigate file list
  - Typing: Activate filter mode

### File Operations
- **Context Menu**: Right-click for Open, Open with, Rename, Move to trash, Delete, Properties
- **Create Operations**: New folder and new file buttons in toolbar
- **Drag & Drop**: (Basic support in file list)
- **Hidden Files**: Always shown in the list

### Advanced Features
- **Properties Dialog**: File information, permissions editing, open-with selection
- **Persistent Settings**: Window size and sort preferences saved between sessions
- **Sorting**: Click column headers to sort, persistent across directory navigation
- **Filter Navigation**: Arrow keys work while filtering is active

### Keyboard Shortcuts
- **Ctrl+L**: Toggle path edit mode
- **Ctrl+W**: Close current tab
- **Ctrl+T**: New tab
- **Ctrl+Enter**: Properties dialog for selected item
- **Enter**: Open selected item
- **Backspace**: Navigate to parent directory
- **Esc**: Clear filter (when active)

## Installation

### Quick Start
```bash
./run.sh
```

### Manual Installation
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

## Usage

### Basic Navigation
1. Use the **Places** button to quickly jump to common directories
2. Click path buttons to navigate to any parent directory
3. Double-click folders to enter them, files to open with default application
4. Use **Backspace** to go up one level

### File Management
1. **Create**: Use toolbar buttons for new folders/files
2. **Rename**: Right-click item → Rename
3. **Delete**: Right-click item → Delete or Move to Trash
4. **Properties**: Right-click item → Properties (or Ctrl+Enter)

### Advanced Usage
1. **Multiple Tabs**: Ctrl+T for new tab, Ctrl+W to close
2. **Quick Filter**: Start typing while list is focused to filter files
3. **Sorting**: Click column headers to sort by Name, Size, or Modified date
4. **Path Editing**: Ctrl+L to type a path directly

## System Requirements

- Linux (tested on modern distributions)
- Python 3.8+
- PyQt6
- Standard Linux utilities: `xdg-open`, `gio` (for trash functionality)

## Configuration

Settings are automatically saved to `~/.config/filemanager/settings.json` and include:
- Window size and position
- Current sort column and order
- Hidden file visibility preferences

## Troubleshooting

### Missing Dependencies
If you get import errors, ensure PyQt6 is installed:
```bash
pip install PyQt6
```

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
