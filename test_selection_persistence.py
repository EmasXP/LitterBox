import os
import sys
import tempfile
from pathlib import Path

import pytest  # type: ignore

sys.path.insert(0, 'src')

from ui.main_window import FileTab


def _populate_demo_tree(root: Path) -> None:
    """Create a small directory structure for navigation tests."""
    (root / 'Desktop').mkdir()
    (root / 'Desktop' / 'project').mkdir()
    (root / 'Desktop' / 'screenshots').mkdir()
    (root / 'Downloads').mkdir()
    # Drop a file so directories are not contiguous alphabetically
    (root / 'Desktop' / 'notes.txt').write_text('notes', encoding='utf-8')


def _current_item_name(tab: FileTab) -> str:
    index = tab.file_list.currentIndex()
    assert index.isValid(), "Expected an item to be selected"
    src_idx = tab.file_list.proxy_model.mapToSource(index)
    item = tab.file_list.source_model.item(src_idx.row(), 0)
    assert item is not None, "Selected item missing from source model"
    return item.text()


def test_navigate_to_parent_preselects_previous_folder(qapp):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _populate_demo_tree(root)

        start = root / 'Desktop' / 'project'
        tab = FileTab(str(start))
        tab.navigate_to(str(start))

        # Simulate clicking the "Desktop" segment by navigating to parent with hint
        tab.navigate_to(str(start.parent), select_entries=[start.name])

        assert _current_item_name(tab) == start.name


def test_navigate_to_grandparent_selects_intermediate_folder(qapp):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _populate_demo_tree(root)

        start = root / 'Desktop' / 'project'
        tab = FileTab(str(start))
        tab.navigate_to(str(start))

        # Simulate clicking "root" segment then expect "Desktop" highlighted
        tab.navigate_to(str(root), select_entries=['Desktop'])

        assert _current_item_name(tab) == 'Desktop'


def test_navigation_without_hints_defaults_to_first_item(qapp):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _populate_demo_tree(root)

        tab = FileTab(str(root))
        tab.navigate_to(str(root))

        # Without hints the first entry should be selected (directories first, alphabetical)
        expected_first = sorted([p.name for p in root.iterdir()], key=lambda n: (not (root / n).is_dir(), n.lower()))[0]
        assert _current_item_name(tab) == expected_first
