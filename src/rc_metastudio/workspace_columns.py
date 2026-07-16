# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""User-owned column sizing for persistent workspace tables."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableView

from workspace_column_identity import (
    WORKSPACE_COLUMN_IDENTITY_ROLE,
    WorkspaceColumnIdentity,
    WorkspaceColumnWidthState,
)


class WorkspaceColumnWidthController(object):
    """Auto-fit a schema once, then preserve the user's section widths."""

    def __init__(self, table, saved_widths=None):
        self.table = table
        self._widths = (
            saved_widths.copy()
            if isinstance(saved_widths, WorkspaceColumnWidthState)
            else WorkspaceColumnWidthState(saved_widths)
        )
        self._applying = False
        table.horizontalHeader().sectionResized.connect(self._section_resized)

    def restore(self, widths):
        self._widths = (
            widths.copy()
            if isinstance(widths, WorkspaceColumnWidthState)
            else WorkspaceColumnWidthState(widths)
        )
        self.synchronize_schema()

    def begin_schema_change(self):
        """Ignore toolkit-driven section resizing during a model transition."""
        self._applying = True

    def end_schema_change(self):
        self._applying = False
        self.synchronize_schema()

    def state(self):
        self._capture_visible_widths()
        return self._widths.copy()

    def synchronize_schema(self):
        """Restore known sections and content-fit only previously unseen ones."""
        model = self.table.model()
        if model is None:
            return
        keys = self._schema_keys()
        self._applying = True
        try:
            for column, key in enumerate(keys):
                width = self._widths.get(key)
                if width is None:
                    self.table.resizeColumnToContents(column)
                    width = self.table.columnWidth(column)
                    self._widths[key] = width
                else:
                    self.table.setColumnWidth(column, width)
        finally:
            self._applying = False

    def auto_fit_all(self):
        """Explicitly fit every visible section and transfer ownership back."""
        self._applying = True
        try:
            QTableView.resizeColumnsToContents(self.table)
        finally:
            self._applying = False
        self._capture_visible_widths()

    def _capture_visible_widths(self):
        for column, key in enumerate(self._schema_keys()):
            self._widths[key] = self.table.columnWidth(column)

    def _section_resized(self, logical_index, _old_size, new_size):
        if self._applying or new_size <= 0:
            return
        keys = self._schema_keys()
        if 0 <= logical_index < len(keys):
            self._widths[keys[logical_index]] = int(new_size)

    def _schema_keys(self):
        model = self.table.model()
        if model is None:
            return []
        identities = []
        for column in range(model.columnCount()):
            value = model.headerData(
                column, Qt.Orientation.Horizontal, WORKSPACE_COLUMN_IDENTITY_ROLE
            )
            identities.append(
                WorkspaceColumnIdentity.coerce(
                    value, fallback_section=column, model=model
                )
            )
        return identities
