"""Small, semantic Qt control policies shared across canonical forms.

Top-level geometry belongs to :mod:`adaptive_window`; form hierarchy and
overflow belong to canonical ``.ui`` resources.  This module deliberately has
no root-fitting, coordinate inference, or descendant-repair surface.
"""

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QHeaderView, QSizePolicy


def configure_navigation_tool_buttons(buttons):
    """Size icon navigation controls from the active Qt style."""
    from PyQt5.QtWidgets import QStyle

    for button in buttons:
        icon_extent = button.style().pixelMetric(QStyle.PM_SmallIconSize, None, button)
        # layout-audit: allow=style-metric-control; reason=icon control dimensions follow the active Qt style metric
        button.setIconSize(QSize(icon_extent, icon_extent))
        # layout-audit: allow=style-metric-control; reason=icon control dimensions follow the active Qt style metric
        button.setMinimumSize(QSize(0, 0))
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)


def configure_compact_table(table, stretch_columns=False, fill_available_width=False):
    """Fit a compact Transactional table once; native scrolling owns overflow."""
    if table is None:
        return

    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
    table.setMinimumWidth(0)
    header = table.horizontalHeader()
    header.setStretchLastSection(False)

    if stretch_columns:
        header.setSectionResizeMode(QHeaderView.Stretch)
    else:
        header.setSectionResizeMode(QHeaderView.Interactive)
        table.resizeColumnsToContents()
        header.setStretchLastSection(fill_available_width)

    table.resizeRowsToContents()
    header_height = 0 if header.isHidden() else header.sizeHint().height()
    table_height = (
        header_height
        + sum(table.rowHeight(row) for row in range(table.rowCount()))
        + 2 * table.frameWidth()
    )
    # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
    table.setMinimumHeight(table_height)
    # layout-audit: allow=compact-table-overflow; reason=compact table keeps rows visible and owns excess overflow
    table.setMaximumHeight(table_height)


def configure_spreadsheet_table_view(table_view):
    """Give a Workspace table an expanding viewport and user-owned columns."""
    if table_view is None:
        return

    table_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    header = table_view.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(QHeaderView.Interactive)
