from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QToolButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
)

APPLICATION_DIALOG_MINIMUM_WIDTH = 420
APPLICATION_DIALOG_MINIMUM_HEIGHT = 180
APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH = 360

ANALYSIS_DIALOG_MINIMUM_WIDTH = 520
ANALYSIS_DIALOG_MINIMUM_HEIGHT = 260
ANALYSIS_DIALOG_COMBO_MAXIMUM_WIDTH = APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH


def fit_application_dialog_to_contents(root, adjust_root=True):
    """Apply the shared base sizing used by application dialogs."""
    if not _fit_root_is_available(root):
        return
    fit_option_groups_to_contents(
        root,
        adjust_root=adjust_root,
        minimum_width=APPLICATION_DIALOG_MINIMUM_WIDTH,
        minimum_height=APPLICATION_DIALOG_MINIMUM_HEIGHT,
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
    )


def fit_option_groups_to_contents(
    root, adjust_root=True, minimum_width=0, minimum_height=0
):
    """Prevent dialog contents from being compressed below visible text."""
    if not _fit_root_is_available(root):
        return
    fit_text_to_contents(
        root,
        adjust_root=adjust_root,
        minimum_width=minimum_width,
        minimum_height=minimum_height,
    )


def fit_text_to_contents(root, adjust_root=True, minimum_width=0, minimum_height=0):
    """Prevent visible text-bearing widgets from being compressed below content."""
    if not _fit_root_is_available(root):
        return
    root_layout = root.layout()
    if root_layout is not None:
        root_layout.activate()

    _fit_text_widgets_to_contents(root)

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

    if adjust_root:
        size_hint = root.sizeHint()
        title_width = _window_title_width_hint(root)
        target_width = max(size_hint.width(), title_width, minimum_width)
        target_height = max(size_hint.height(), minimum_height)
        _raise_maximum_height(root, target_height)
        _raise_maximum_width(root, target_width)
        root.setMinimumSize(
            root.minimumSize().expandedTo(QSize(target_width, target_height))
        )
        root.adjustSize()


def _fit_root_is_available(root):
    if root is None:
        return False
    try:
        root.layout()
    except RuntimeError:
        return False
    return True


def _fit_text_widgets_to_contents(root):
    for label in root.findChildren(QLabel):
        if _is_hidden_for_fit(label, root) or not str(label.text()).strip():
            continue
        _fit_widget_width_to_hint(label, label.sizeHint().width())

    for combo_box in root.findChildren(QComboBox):
        if _is_hidden_for_fit(combo_box, root):
            continue
        combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        _fit_combo_width_to_contents(combo_box)
        if combo_box.view() is not None:
            combo_box.view().setMinimumWidth(combo_box.minimumWidth())

    for button in root.findChildren(QAbstractButton):
        if isinstance(button, QToolButton):
            continue
        if _is_hidden_for_fit(button, root) or not str(button.text()).strip():
            continue
        _fit_widget_width_to_hint(button, button.sizeHint().width())


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
        widget.setSizePolicy(QSizePolicy.Preferred, widget.sizePolicy().verticalPolicy())


def _fit_combo_width_to_contents(combo_box):
    width = max(combo_box.sizeHint().width(), _combo_contents_width(combo_box))
    target_width = min(width, APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH)
    combo_box.setMinimumWidth(target_width)
    combo_box.setMaximumWidth(max(target_width, APPLICATION_DIALOG_COMBO_MAXIMUM_WIDTH))
    if combo_box.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed:
        combo_box.setSizePolicy(
            QSizePolicy.Preferred, combo_box.sizePolicy().verticalPolicy()
        )


def _combo_contents_width(combo_box):
    if combo_box.count() == 0:
        return 0
    metrics = combo_box.fontMetrics()
    widest_item = max(
        metrics.horizontalAdvance(str(combo_box.itemText(index)))
        for index in range(combo_box.count())
    )
    return widest_item + 48


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
