from PyQt5.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QToolButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QWidget,
    QWIDGETSIZE_MAX,
    QWizard,
    QWizardPage,
)

APPLICATION_DIALOG_MINIMUM_WIDTH = 420
APPLICATION_DIALOG_MINIMUM_HEIGHT = 96
APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH = 360

ANALYSIS_DIALOG_MINIMUM_WIDTH = 520
ANALYSIS_DIALOG_MINIMUM_HEIGHT = 160
ANALYSIS_DIALOG_COMBO_MAXIMUM_WIDTH = APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH
ANALYSIS_DIALOG_VALUE_CONTROL_MAXIMUM_WIDTH = 220


def exec_centered(dialog):
    """Center a modal child dialog over its parent before executing it."""
    center_dialog_over_parent(dialog)
    return dialog.exec()


def show_centered(dialog):
    """Center a child dialog over its parent before showing it."""
    center_dialog_over_parent(dialog)
    return dialog.show()


def center_dialog_over_parent(dialog):
    """Center a top-level dialog over its parent window when a parent exists."""
    if dialog is None:
        return

    parent_widget = getattr(dialog, "parentWidget", None)
    if parent_widget is None:
        return

    parent = parent_widget()
    if parent is None:
        return

    dialog.adjustSize()
    dialog_geometry = dialog.frameGeometry()
    parent_geometry = parent.frameGeometry()
    if parent_geometry.isNull():
        parent_geometry = parent.geometry()

    dialog_geometry.moveCenter(parent_geometry.center())
    dialog_geometry.moveTopLeft(
        _clamp_top_left_to_available_screen(
            dialog_geometry.topLeft(),
            dialog_geometry.size(),
            parent_geometry.center(),
        )
    )
    dialog.move(dialog_geometry.topLeft())


def fit_application_dialog_to_contents(root, adjust_root=True):
    """Apply the shared base sizing used by application dialogs."""
    if not _fit_root_is_available(root):
        return
    configure_application_wizard(root)
    fit_option_groups_to_contents(
        root,
        adjust_root=adjust_root,
        minimum_width=APPLICATION_DIALOG_MINIMUM_WIDTH,
        minimum_height=APPLICATION_DIALOG_MINIMUM_HEIGHT,
        stable_root=True,
    )


def configure_application_wizard(wizard):
    """Use one wizard chrome policy for app-owned multi-page dialogs."""
    if not isinstance(wizard, QWizard):
        return

    wizard.setWizardStyle(QWizard.ModernStyle)
    wizard.setOption(QWizard.NoBackButtonOnStartPage, True)
    wizard.setButtonLayout(
        [
            QWizard.Stretch,
            QWizard.BackButton,
            QWizard.NextButton,
            QWizard.FinishButton,
            QWizard.CancelButton,
        ]
    )


def fit_analysis_dialog_to_contents(root, adjust_root=True):
    """Apply the shared width floor used by analysis parameter dialogs."""
    if not _fit_root_is_available(root):
        return
    fit_option_groups_to_contents(
        root,
        adjust_root=adjust_root,
        minimum_width=ANALYSIS_DIALOG_MINIMUM_WIDTH,
        minimum_height=ANALYSIS_DIALOG_MINIMUM_HEIGHT,
        stable_root=True,
    )


def reset_stable_fit_size(root):
    """Allow a stable fitted root to recalculate its size for new content."""
    if not _fit_root_is_available(root):
        return
    root.setProperty("oma_stable_fit_size", None)


def fit_option_groups_to_contents(
    root, adjust_root=True, minimum_width=0, minimum_height=0, stable_root=False
):
    """Prevent dialog contents from being compressed below visible text."""
    if not _fit_root_is_available(root):
        return
    fit_text_to_contents(
        root,
        adjust_root=adjust_root,
        minimum_width=minimum_width,
        minimum_height=minimum_height,
        stable_root=stable_root,
    )


def fit_text_to_contents(
    root, adjust_root=True, minimum_width=0, minimum_height=0, stable_root=False
):
    """Prevent visible text-bearing widgets from being compressed below content."""
    if not _fit_root_is_available(root):
        return

    _adopt_fixed_direct_children_into_root_layout(root)

    root_layout = root.layout()
    if root_layout is not None:
        _compact_expanding_vertical_spacers(root_layout)
        root_layout.activate()

    combo_content_expanded = _fit_text_widgets_to_contents(root)

    for group_box in _option_group_boxes(root):
        _raise_maximum_height(group_box, group_box.sizeHint().height())
        group_box.setSizePolicy(
            group_box.sizePolicy().horizontalPolicy(),
            QSizePolicy.Preferred,
        )
        group_box.setMinimumHeight(
            max(group_box.minimumHeight(), group_box.sizeHint().height())
        )

    root_layout = root.layout()
    if root_layout is not None:
        root_layout.activate()

    _fit_embedded_pages_to_contents(root)
    _fit_current_wizard_page_to_contents(root)
    _fit_wizard_page_to_contents(root)

    adjust_root = adjust_root and _root_allows_content_resize(root)
    if adjust_root:
        size_hint = _root_size_hint_for_current_contents(root)
        title_width = _window_title_width_hint(root)
        target_width = max(size_hint.width(), title_width, minimum_width)
        target_height = max(size_hint.height(), minimum_height)
        stable_size = _stable_root_size(root) if stable_root else None
        if stable_size is not None and not combo_content_expanded:
            target_width = max(target_width, stable_size.width())

        target_size = QSize(target_width, target_height)
        _raise_maximum_height(root, target_height)
        _raise_maximum_width(root, target_width)
        root.setMinimumSize(target_size)
        if stable_root:
            root.setProperty("oma_stable_fit_size", target_size)
        if size_hint.isValid():
            root.adjustSize()
        else:
            root.resize(target_size)

    _fill_current_wizard_page_width(root)
    _fill_embedded_pages_to_parent_width(root)

    _install_first_show_refit(
        root,
        adjust_root=adjust_root,
        minimum_width=minimum_width,
        minimum_height=minimum_height,
        stable_root=stable_root,
    )


def configure_compact_table(table, stretch_columns=False):
    """Let compact tables expand horizontally without clipping rows or columns."""
    if table is None:
        return

    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    table.setMinimumWidth(0)
    _raise_maximum_width(table, QWIDGETSIZE_MAX)

    if stretch_columns:
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumWidth(_table_width_for_stretched_content(table))
    else:
        _resize_table_columns_to_contents(table)
        table.setMinimumWidth(_table_width_for_visible_columns(table))

    table.resizeRowsToContents()
    table_height = _table_height_for_visible_rows(table)
    table.setMinimumHeight(table_height)
    table.setMaximumHeight(table_height)


def configure_spreadsheet_table_view(table_view):
    """Preserve content-sized spreadsheet columns inside an expanding viewport."""
    if table_view is None:
        return

    table_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    header = table_view.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(QHeaderView.Interactive)


def _resize_table_columns_to_contents(table):
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        table.setColumnWidth(
            column,
            max(
                table.columnWidth(column),
                table.sizeHintForColumn(column),
                header.sectionSizeHint(column),
            ),
        )


def _table_width_for_visible_columns(table):
    vertical_header_width = 0
    if not table.verticalHeader().isHidden():
        vertical_header_width = table.verticalHeader().sizeHint().width()
    return (
        vertical_header_width
        + sum(table.columnWidth(column) for column in range(table.columnCount()))
        + 2 * table.frameWidth()
    )


def _table_width_for_stretched_content(table):
    column_count = table.columnCount()
    if column_count == 0:
        return _table_width_for_visible_columns(table)

    content_widths = _table_content_widths(table)
    vertical_header_width = 0
    if not table.verticalHeader().isHidden():
        vertical_header_width = table.verticalHeader().sizeHint().width()
    return (
        vertical_header_width
        + max(sum(content_widths), max(content_widths) * column_count)
        + 2 * table.frameWidth()
    )


def _table_content_widths(table):
    header = table.horizontalHeader()
    return [
        max(table.sizeHintForColumn(column), header.sectionSizeHint(column))
        for column in range(table.columnCount())
    ]


def _table_height_for_visible_rows(table):
    header_height = 0
    if not table.horizontalHeader().isHidden():
        header_height = table.horizontalHeader().sizeHint().height()
    return (
        header_height
        + sum(table.rowHeight(row) for row in range(table.rowCount()))
        + 2 * table.frameWidth()
    )


class _FirstShowRefitFilter(QObject):
    def __init__(self, root):
        super(_FirstShowRefitFilter, self).__init__(root)
        self._root = root
        self._pending = False

    def eventFilter(self, watched, event):
        if watched is self._root and event.type() == QEvent.Show:
            self._queue_refit()
        return False

    def _queue_refit(self):
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(0, self._refit)

    def _refit(self):
        self._pending = False
        if not _fit_root_is_available(self._root):
            return

        options = _first_show_refit_options(self._root)
        if options is None:
            return
        reset_stable_fit_size(self._root)
        fit_text_to_contents(self._root, **options)


def _install_first_show_refit(
    root, adjust_root=True, minimum_width=0, minimum_height=0, stable_root=False
):
    if not _fit_root_is_available(root):
        return

    root.setProperty(
        "oma_first_show_refit_options",
        {
            "adjust_root": adjust_root,
            "minimum_width": minimum_width,
            "minimum_height": minimum_height,
            "stable_root": stable_root,
        },
    )
    if getattr(root, "_oma_first_show_refit_filter", None) is not None:
        return

    event_filter = _FirstShowRefitFilter(root)
    root.installEventFilter(event_filter)
    root._oma_first_show_refit_filter = event_filter


def _first_show_refit_options(root):
    options = root.property("oma_first_show_refit_options")
    if not isinstance(options, dict):
        return None
    return {
        "adjust_root": bool(options.get("adjust_root", True)),
        "minimum_width": int(options.get("minimum_width", 0)),
        "minimum_height": int(options.get("minimum_height", 0)),
        "stable_root": bool(options.get("stable_root", False)),
    }


def _fit_root_is_available(root):
    if root is None:
        return False
    try:
        root.layout()
    except RuntimeError:
        return False
    return True


def _adopt_fixed_direct_children_into_root_layout(root):
    if root.layout() is not None or not isinstance(root, QDialog):
        return

    direct_children = [
        child
        for child in root.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)
        if not child.isHidden() and not child.isWindow()
    ]
    if not direct_children:
        return

    rows = _direct_child_geometry_rows(direct_children)
    margins = _direct_child_layout_margins(root, direct_children)
    horizontal_spacing = _direct_child_horizontal_spacing(rows)
    vertical_spacing = _direct_child_vertical_spacing(rows)

    root_layout = QGridLayout(root)
    root_layout.setContentsMargins(*margins)
    if horizontal_spacing is not None:
        root_layout.setHorizontalSpacing(horizontal_spacing)
    if vertical_spacing is not None:
        root_layout.setVerticalSpacing(vertical_spacing)

    column_count = max(len(row_children) for row_children in rows)
    for row_index, row_children in enumerate(rows):
        for column_index, child in enumerate(row_children):
            if len(row_children) == 1 or column_index == len(row_children) - 1:
                _allow_layout_child_horizontal_expansion(child)
            column_span = column_count if len(row_children) == 1 else 1
            root_layout.addWidget(child, row_index, column_index, 1, column_span)
        if row_children:
            root_layout.setColumnStretch(len(row_children) - 1, 1)


def _direct_child_layout_margins(root, children):
    contents = root.contentsRect()
    left = min(max(0, child.geometry().left() - contents.left()) for child in children)
    top = min(max(0, child.geometry().top() - contents.top()) for child in children)
    right = min(
        max(0, contents.right() - child.geometry().right()) for child in children
    )
    bottom = min(
        max(0, contents.bottom() - child.geometry().bottom()) for child in children
    )
    return left, top, right, bottom


def _allow_layout_child_horizontal_expansion(widget):
    policy = widget.sizePolicy()
    if policy.horizontalPolicy() != QSizePolicy.Expanding:
        widget.setSizePolicy(QSizePolicy.Expanding, policy.verticalPolicy())


def _direct_child_geometry_rows(children):
    rows = []
    current_row = []
    current_bottom = None
    for child in sorted(children, key=lambda child: child.geometry().top()):
        child_top = child.geometry().top()
        if current_bottom is None or child_top <= current_bottom:
            current_row.append(child)
            current_bottom = (
                child.geometry().bottom()
                if current_bottom is None
                else max(current_bottom, child.geometry().bottom())
            )
            continue

        rows.append(sorted(current_row, key=lambda widget: widget.geometry().left()))
        current_row = [child]
        current_bottom = child.geometry().bottom()

    if current_row:
        rows.append(sorted(current_row, key=lambda widget: widget.geometry().left()))
    return rows


def _direct_child_horizontal_spacing(rows):
    gaps = []
    for row in rows:
        previous_right = None
        for child in row:
            if previous_right is not None:
                gap = child.geometry().left() - previous_right - 1
                if gap >= 0:
                    gaps.append(gap)
            previous_right = max(
                child.geometry().right(),
                previous_right
                if previous_right is not None
                else child.geometry().right(),
            )
    if not gaps:
        return None
    return min(gaps)


def _direct_child_vertical_spacing(rows):
    gaps = []
    previous_bottom = None
    for row in rows:
        row_top = min(child.geometry().top() for child in row)
        row_bottom = max(child.geometry().bottom() for child in row)
        if previous_bottom is not None:
            gap = row_top - previous_bottom - 1
            if gap >= 0:
                gaps.append(gap)
        previous_bottom = (
            row_bottom if previous_bottom is None else max(previous_bottom, row_bottom)
        )
    if not gaps:
        return None
    return min(gaps)


def _window_state_blocks_content_fit(root):
    is_maximized = getattr(root, "isMaximized", None)
    is_full_screen = getattr(root, "isFullScreen", None)
    return (callable(is_maximized) and is_maximized()) or (
        callable(is_full_screen) and is_full_screen()
    )


def _root_allows_content_resize(root):
    return isinstance(root, QDialog) and not _window_state_blocks_content_fit(root)


def _stable_root_size(root):
    stable_size = root.property("oma_stable_fit_size")
    if isinstance(stable_size, QSize) and stable_size.isValid():
        return stable_size
    return None


def _fit_wizard_page_to_contents(root):
    if not isinstance(root, QWizardPage):
        return
    _fit_embedded_page_to_contents(root)


def _fit_current_wizard_page_to_contents(root):
    if not isinstance(root, QWizard):
        return
    current_page = root.currentPage()
    if current_page is None:
        return
    _fit_wizard_page_to_contents(current_page)


def _fill_current_wizard_page_width(root):
    if not isinstance(root, QWizard):
        return

    current_page = root.currentPage()
    if current_page is None:
        return

    page_parent = current_page.parentWidget()
    if page_parent is None:
        return

    parent_contents_width = page_parent.contentsRect().width()
    if parent_contents_width <= 0:
        return

    horizontal_inset = max(0, current_page.geometry().left()) * 2
    target_width = max(0, parent_contents_width - horizontal_inset)
    if target_width <= 0:
        return

    _raise_maximum_width(current_page, target_width)
    _set_fit_minimum_size(
        current_page, QSize(target_width, current_page.sizeHint().height())
    )
    if current_page.layout() is not None:
        current_page.layout().activate()


def _fit_embedded_pages_to_contents(root):
    for tab_widget in root.findChildren(QTabWidget):
        for index in range(tab_widget.count()):
            _fit_embedded_page_to_contents(tab_widget.widget(index))

    for stacked_widget in root.findChildren(QStackedWidget):
        for index in range(stacked_widget.count()):
            _fit_embedded_page_to_contents(stacked_widget.widget(index))


def _fill_embedded_pages_to_parent_width(root):
    for tab_widget in root.findChildren(QTabWidget):
        for index in range(tab_widget.count()):
            _fill_page_to_parent_width(tab_widget.widget(index))

    for stacked_widget in root.findChildren(QStackedWidget):
        for index in range(stacked_widget.count()):
            _fill_page_to_parent_width(stacked_widget.widget(index))


def _fill_page_to_parent_width(page):
    if page is None:
        return

    page_parent = page.parentWidget()
    if page_parent is None:
        return

    parent_contents_width = page_parent.contentsRect().width()
    if parent_contents_width <= 0:
        return

    horizontal_inset = max(0, page.geometry().left()) * 2
    target_width = max(0, parent_contents_width - horizontal_inset)
    if target_width <= 0:
        return

    _raise_maximum_width(page, target_width)
    _set_fit_minimum_size(page, QSize(target_width, page.sizeHint().height()))
    if page.layout() is not None:
        page.layout().activate()


def _fit_embedded_page_to_contents(page):
    if page is None:
        return
    target_size = page.sizeHint()
    page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    _raise_maximum_height(page, QWIDGETSIZE_MAX)
    _raise_maximum_width(page, QWIDGETSIZE_MAX)
    _set_fit_minimum_size(page, target_size)


def _set_fit_minimum_size(widget, target_size):
    base_size = _fit_base_minimum_size(widget)
    widget.setMinimumSize(base_size.expandedTo(target_size))


def _fit_base_minimum_size(widget):
    base_size = widget.property("oma_fit_base_minimum_size")
    if isinstance(base_size, QSize):
        return base_size

    base_size = widget.minimumSize()
    widget.setProperty("oma_fit_base_minimum_size", base_size)
    return base_size


def _root_size_hint_for_current_contents(root):
    size_hint = root.sizeHint()
    if not size_hint.isValid():
        return _direct_child_contents_size_hint(root)
    if not isinstance(root, QWizard):
        return size_hint

    current_page = root.currentPage()
    if current_page is None:
        return size_hint

    current_hint = current_page.sizeHint()
    if not current_hint.isValid():
        return size_hint

    page_heights = [
        page.sizeHint().height()
        for page_id in root.pageIds()
        for page in [root.page(page_id)]
        if page is not None and page.sizeHint().isValid()
    ]
    if not page_heights:
        return size_hint

    max_page_height = max(page_heights)
    if size_hint.height() >= max_page_height:
        chrome_height = size_hint.height() - max_page_height
    else:
        chrome_height = max(0, size_hint.height() - current_hint.height())
    return QSize(size_hint.width(), current_hint.height() + chrome_height)


def _direct_child_contents_size_hint(root):
    contents_rect = None
    for child in root.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
        if child.isHidden():
            continue
        child_rect = child.geometry()
        if child_rect.isNull():
            continue
        contents_rect = (
            child_rect if contents_rect is None else contents_rect.united(child_rect)
        )

    if contents_rect is None:
        return QSize(-1, -1)

    right_margin = max(0, contents_rect.left())
    bottom_margin = max(0, contents_rect.top())
    return QSize(
        contents_rect.right() + 1 + right_margin,
        contents_rect.bottom() + 1 + bottom_margin,
    )


def _compact_expanding_vertical_spacers(layout):
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue

        child_layout = item.layout()
        if child_layout is not None:
            _compact_expanding_vertical_spacers(child_layout)
            continue

        widget = item.widget()
        if widget is not None and widget.layout() is not None:
            _compact_expanding_vertical_spacers(widget.layout())
            continue

        spacer = item.spacerItem()
        if spacer is None:
            continue
        if not spacer.expandingDirections() & Qt.Vertical:
            continue

        hint = spacer.sizeHint()
        horizontal_policy = spacer.sizePolicy().horizontalPolicy()
        spacer.changeSize(
            hint.width(),
            0,
            horizontal_policy,
            QSizePolicy.Minimum,
        )


def _fit_text_widgets_to_contents(root):
    combo_content_expanded = False
    for label in root.findChildren(QLabel):
        if _is_hidden_for_fit(label, root) or not str(label.text()).strip():
            continue
        if label.wordWrap():
            label.setMinimumWidth(0)
            continue
        _fit_widget_width_to_hint(label, label.sizeHint().width())

    for combo_box in root.findChildren(QComboBox):
        if _is_hidden_for_fit(combo_box, root):
            continue
        previous_minimum_width = combo_box.minimumWidth()
        combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        _fit_combo_width_to_contents(combo_box)
        combo_content_expanded = (
            combo_content_expanded or combo_box.minimumWidth() > previous_minimum_width
        )
        if combo_box.view() is not None:
            combo_box.view().setMinimumWidth(combo_box.minimumWidth())

    for button in root.findChildren(QAbstractButton):
        if isinstance(button, QToolButton):
            continue
        if _is_hidden_for_fit(button, root) or not str(button.text()).strip():
            continue
        _fit_widget_width_to_hint(button, button.sizeHint().width())
    return combo_content_expanded


def _is_hidden_for_fit(widget, root):
    current = widget
    while current is not None and current is not root:
        if current.isHidden() and not _is_hidden_page_for_fit(current):
            return True
        current = current.parentWidget()
    return False


def _is_hidden_page_for_fit(widget):
    parent = widget.parentWidget()
    if isinstance(parent, QTabWidget) and parent.indexOf(widget) >= 0:
        return True
    if isinstance(parent, QStackedWidget) and parent.indexOf(widget) >= 0:
        return True
    return False


def _fit_widget_width_to_hint(widget, width):
    _raise_maximum_width(widget, width)
    widget.setMinimumWidth(max(widget.minimumWidth(), width))
    if widget.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed:
        widget.setSizePolicy(
            QSizePolicy.Preferred, widget.sizePolicy().verticalPolicy()
        )


def _fit_combo_width_to_contents(combo_box):
    width = _combo_contents_width(combo_box)
    target_maximum_width = _combo_maximum_width(combo_box)
    target_width = min(width, target_maximum_width)
    combo_box.setMinimumWidth(target_width)
    combo_box.setMaximumWidth(target_maximum_width)
    combo_box.setSizePolicy(
        QSizePolicy.Maximum, combo_box.sizePolicy().verticalPolicy()
    )


def _combo_contents_width(combo_box):
    if combo_box.count() == 0:
        return combo_box.sizeHint().width()
    metrics = combo_box.fontMetrics()
    widest_item = max(
        metrics.horizontalAdvance(str(combo_box.itemText(index)))
        for index in range(combo_box.count())
    )
    return widest_item + 48


def _combo_maximum_width(combo_box):
    explicit_cap = combo_box.property("oma_maximum_value_control_width")
    if isinstance(explicit_cap, int) and explicit_cap > 0:
        return min(explicit_cap, APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH)
    return APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH


def _window_title_width_hint(root):
    title = str(root.windowTitle()).strip()
    if not title:
        return 0
    return root.fontMetrics().horizontalAdvance(title) + 96


def _option_group_boxes(root):
    return [
        group_box
        for group_box in root.findChildren(QGroupBox)
        if not _is_hidden_for_fit(group_box, root)
        and _has_visible_option_button(group_box, root)
    ]


def _has_visible_option_button(group_box, root):
    option_buttons = group_box.findChildren(QCheckBox) + group_box.findChildren(
        QRadioButton
    )
    return any(
        not _is_hidden_for_fit(button, root) and str(button.text()).strip()
        for button in option_buttons
    )


def _clamp_top_left_to_available_screen(top_left, size, screen_point):
    screen = QGuiApplication.screenAt(screen_point) or QGuiApplication.primaryScreen()
    if screen is None:
        return top_left

    available = screen.availableGeometry()
    min_x = available.left()
    min_y = available.top()
    max_x = available.right() - size.width() + 1
    max_y = available.bottom() - size.height() + 1

    return QPoint(
        _clamp(top_left.x(), min_x, max(min_x, max_x)),
        _clamp(top_left.y(), min_y, max(min_y, max_y)),
    )


def _clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def _raise_maximum_height(widget, height):
    maximum = widget.maximumSize()
    if maximum.height() < height:
        maximum.setHeight(height)
        widget.setMaximumSize(maximum)


def _raise_maximum_width(widget, width):
    maximum = widget.maximumSize()
    if maximum.width() < width:
        maximum.setWidth(width)
        widget.setMaximumSize(maximum)
