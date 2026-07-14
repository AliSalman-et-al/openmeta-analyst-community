"""Small, semantic Qt control policies shared across canonical forms.

Top-level geometry belongs to :mod:`adaptive_window`; form hierarchy and
overflow belong to canonical ``.ui`` resources.  This module deliberately has
no root-fitting, coordinate inference, or descendant-repair surface.
"""

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QHeaderView, QProxyStyle, QSizePolicy, QStyle


OUTCOME_NAVIGATION_ICON_EXTENT = 20
COMPACT_ANALYSIS_ICON_EXTENT = 18
STANDARD_ANALYSIS_ICON_EXTENT = 28


class _MenuIconProxyStyle(QProxyStyle):
    """Override only the small-icon metric for one menu surface."""

    def __init__(self, icon_extent, parent=None):
        super(_MenuIconProxyStyle, self).__init__()
        self._icon_extent = icon_extent
        self.setParent(parent)

    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PM_SmallIconSize:
            return self._icon_extent
        return super(_MenuIconProxyStyle, self).pixelMetric(metric, option, widget)


def configure_analysis_menu(menu):
    """Use the compact analysis master at its intended 18-pixel size."""
    icon_style = _MenuIconProxyStyle(COMPACT_ANALYSIS_ICON_EXTENT, menu)
    menu.setStyle(icon_style)
    menu._rcms_icon_style = icon_style


def configure_analysis_action_icon(action, icon_name):
    """Attach optically tuned menu and toolbar masters to one QAction."""
    icon = QIcon()
    icon.addFile(
        ":/icons/analyses/compact/{}.svg".format(icon_name),
        QSize(COMPACT_ANALYSIS_ICON_EXTENT, COMPACT_ANALYSIS_ICON_EXTENT),
    )
    icon.addFile(
        ":/icons/analyses/{}.svg".format(icon_name),
        QSize(STANDARD_ANALYSIS_ICON_EXTENT, STANDARD_ANALYSIS_ICON_EXTENT),
    )
    action.setIcon(icon)


def configure_navigation_tool_buttons(buttons):
    """Give outcome-navigation controls a coherent cross-platform scale."""
    for button in buttons:
        button.setIconSize(
            QSize(OUTCOME_NAVIGATION_ICON_EXTENT, OUTCOME_NAVIGATION_ICON_EXTENT)
        )
        # layout-audit: allow=style-metric-control; reason=compact icon control leaves button chrome to the active Qt style
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
