#!/usr/bin/env python3
"""Lightweight selection persistence test using FileTab directly (no MainWindow)."""

import os
import sys
import tempfile

sys.path.insert(0, 'src')

from PyQt6.QtWidgets import QApplication
from ui.main_window import FileTab  # Reuse FileTab logic only


def test_filter_selection():
    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp:
        # Create some files with predictable names
        names = ["alpha.txt", "alpine.txt", "beta.txt", "gamma.txt"]
        for n in names:
            open(os.path.join(tmp, n), 'w').close()

        tab = FileTab(tmp)
        tab.navigate_to(tmp)

        # Ensure file list populated
        model = tab.file_list.source_model
        assert model.rowCount() == len(names)

        # Select the second item after initial sort (FileListView sorts? assume name order)
        # We'll locate item named 'alpine.txt'
        target_name = 'alpine.txt'
        target_index = None
        for row in range(model.rowCount()):
            item = model.item(row, 0)
            if item and item.text() == target_name:
                # Map to proxy (the proxy may re-order; use select_item_by_name for reliability)
                tab.file_list.select_item_by_name(target_name)
                target_index = tab.file_list.currentIndex()
                break
        assert target_index and target_index.isValid(), "Failed to select target item before filtering"

        # Apply filter that should keep 'alpine.txt' visible (common prefix 'al')
        tab.apply_filter('al')
        cur_idx = tab.file_list.currentIndex()
        assert cur_idx.isValid(), "Selection lost after applying filter"
        src_idx = tab.file_list.proxy_model.mapToSource(cur_idx)
        sel_item = model.item(src_idx.row(), 0)
        assert sel_item and sel_item.text() == target_name, "Wrong item selected after filter"

        # Clear filter and ensure selection still same
        tab.clear_filter()
        cur_idx2 = tab.file_list.currentIndex()
        assert cur_idx2.isValid(), "Selection lost after clearing filter"
        src_idx2 = tab.file_list.proxy_model.mapToSource(cur_idx2)
        sel_item2 = model.item(src_idx2.row(), 0)
        assert sel_item2 and sel_item2.text() == target_name, "Selection changed after clearing filter"

        # Apply a filter that excludes the selected item => selection should move (implementation chooses first row)
        tab.apply_filter('gamma')
        cur_idx3 = tab.file_list.currentIndex()
        assert cur_idx3.isValid(), "No selection after restrictive filter"
        src_idx3 = tab.file_list.proxy_model.mapToSource(cur_idx3)
        new_item = model.item(src_idx3.row(), 0)
        assert new_item and new_item.text() == 'gamma.txt', "Did not select first remaining item after restrictive filter"
