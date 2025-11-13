import os
from pathlib import Path
import pytest
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QKeySequence

from ui.main_window import FileTab

@pytest.fixture
def temp_dir(tmp_path):
    # Create temporary files
    (tmp_path / "file1.txt").write_text("one")
    (tmp_path / "file2.log").write_text("two")
    return tmp_path

def _select_two(tab: FileTab):
    # Select both items in the file list
    fl = tab.file_list
    assert fl.select_item_by_name("file1.txt")
    # Select second while keeping first selected
    # Find second item index in source model
    for row in range(fl.source_model.rowCount()):
        item = fl.source_model.item(row, 0)
        if not item:
            continue
        p = item.data(Qt.ItemDataRole.UserRole)
        if os.path.basename(p) == "file2.log":
            src_index = fl.source_model.index(row, 0)
            proxy_index = fl.proxy_model.mapFromSource(src_index)
            sel_model = fl.selectionModel()
            assert sel_model is not None
            # Extend selection to include second item
            sel_model.select(proxy_index, sel_model.SelectionFlag.Select | sel_model.SelectionFlag.Rows)  # type: ignore[attr-defined]
            break
    selected = tab.file_list.get_selected_items()
    assert len(selected) == 2
    return selected

def test_delete_shortcuts_trash_and_permanent(qapp, temp_dir):
    tab = FileTab(str(temp_dir))
    # Stop background timers to avoid interference
    if hasattr(tab, '_poll_timer'):
        tab._poll_timer.stop()
    if hasattr(tab, '_watch_refresh_timer'):
        tab._watch_refresh_timer.stop()
    qapp.processEvents()

    selected = _select_two(tab)

    trashed_calls = []
    deleted_calls = []

    # Rewire signals to custom collectors (disconnect original slots)
    try:
        tab.file_list.trash_requested.disconnect()  # disconnect all
    except Exception:
        pass
    try:
        tab.file_list.delete_requested.disconnect()
    except Exception:
        pass

    tab.file_list.trash_requested.connect(lambda paths: trashed_calls.extend(paths))
    tab.file_list.delete_requested.connect(lambda paths: deleted_calls.extend(paths))

    # Delete key should emit trash_requested
    QTest.keyClick(tab.file_list, Qt.Key.Key_Delete)  # type: ignore[arg-type]
    assert set(trashed_calls) == set(selected)
    assert deleted_calls == []

    # Ctrl+Delete should emit delete_requested
    QTest.keyClick(tab.file_list, Qt.Key.Key_Delete, Qt.KeyboardModifier.ControlModifier)  # type: ignore[arg-type]
    assert set(deleted_calls) == set(selected)

def test_delete_shortcut_no_selection(qapp, temp_dir):
    tab = FileTab(str(temp_dir))
    if hasattr(tab, '_poll_timer'):
        tab._poll_timer.stop()
    if hasattr(tab, '_watch_refresh_timer'):
        tab._watch_refresh_timer.stop()
    qapp.processEvents()

    trashed_calls = []
    try:
        tab.file_list.trash_requested.disconnect()
    except Exception:
        pass
    tab.file_list.trash_requested.connect(lambda paths: trashed_calls.extend(paths))

    # Clear selection
    sel_model = tab.file_list.selectionModel()
    if sel_model:
        sel_model.clearSelection()

    QTest.keyClick(tab.file_list, Qt.Key.Key_Delete)  # type: ignore[arg-type]
    assert trashed_calls == []

def test_context_menu_actions_have_shortcuts(qapp, temp_dir, monkeypatch):
    tab = FileTab(str(temp_dir))
    qapp.processEvents()
    fl = tab.file_list

    captured_menus = []
    orig_init = __import__('PyQt6').QtWidgets.QMenu.__init__  # type: ignore
    orig_exec = __import__('PyQt6').QtWidgets.QMenu.exec  # type: ignore
    from PyQt6.QtWidgets import QMenu  # type: ignore

    def tracking_init(self, *args, **kwargs):  # type: ignore
        orig_init(self, *args, **kwargs)
        captured_menus.append(self)

    def fake_exec(self, *args, **kwargs):  # type: ignore
        # Do not block; just return
        return None

    monkeypatch.setattr(QMenu, "__init__", tracking_init)
    monkeypatch.setattr(QMenu, "exec", fake_exec)

    # Single selection
    assert fl.select_item_by_name("file1.txt")
    path_single = fl.get_selected_items()[0]
    tab.show_context_menu(path_single, fl.mapToGlobal(QPoint(0, 0)))
    assert captured_menus, "Menu should have been captured for single selection"
    single_actions = captured_menus[-1].actions()
    # Verify shortcuts are assigned (right-aligned by style, not in text)
    assert any(a.text().startswith("Move to Trash") and not a.text().endswith("Del]") and a.shortcut().toString() for a in single_actions)
    assert any(a.text().startswith("Delete") and a.shortcut().toString().lower().startswith("ctrl+del") for a in single_actions)

    # Map actions by text for easier lookup
    actions_map = {a.text(): a for a in single_actions}

    # Open (Enter / Return)
    if "Open" in actions_map:
        open_seq = actions_map["Open"].shortcut().toString()
        assert open_seq in ("Return", "Enter"), f"Unexpected Open shortcut: {open_seq}"

    # Open with... (Ctrl+Enter / Ctrl+Return)
    if "Open with..." in actions_map:
        ow_seq = actions_map["Open with..."].shortcut().toString()
        assert ow_seq in ("Ctrl+Return", "Ctrl+Enter"), f"Unexpected Open with shortcut: {ow_seq}"

    # Rename (F2)
    if "Rename" in actions_map:
        rename_seq = actions_map["Rename"].shortcut().toString()
        assert rename_seq == "F2", f"Unexpected Rename shortcut: {rename_seq}"

    # Copy, Cut, Paste
    for label, std in (("Copy", QKeySequence.StandardKey.Copy), ("Cut", QKeySequence.StandardKey.Cut), ("Paste", QKeySequence.StandardKey.Paste)):
        if label in actions_map:
            expected = QKeySequence(std).toString()
            actual = actions_map[label].shortcut().toString()
            assert actual == expected, f"Unexpected {label} shortcut: {actual} (expected {expected})"

    # Properties (Alt+Enter / Alt+Return)
    if "Properties" in actions_map:
        prop_seq = actions_map["Properties"].shortcut().toString()
        assert prop_seq in ("Alt+Return", "Alt+Enter"), f"Unexpected Properties shortcut: {prop_seq}"

    # Multi selection
    _select_two(tab)
    tab.show_context_menu(path_single, fl.mapToGlobal(QPoint(0, 0)))
    assert len(captured_menus) >= 2, "Menu should have been captured for multi selection"
    multi_actions = captured_menus[-1].actions()
    trash_actions = [a for a in multi_actions if a.text().startswith("Move to Trash")]
    delete_actions = [a for a in multi_actions if a.text().startswith("Delete")]
    assert trash_actions and all(a.shortcut().toString() != "" for a in trash_actions)
    assert delete_actions and all(a.shortcut().toString().lower().startswith("ctrl+del") for a in delete_actions)
