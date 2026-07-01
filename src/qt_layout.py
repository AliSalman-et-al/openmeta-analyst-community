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
)


def fit_option_groups_to_contents(root, adjust_root=True):
    """Prevent dialog contents from being compressed below visible text."""
    fit_text_to_contents(root, adjust_root=adjust_root)


def fit_text_to_contents(root, adjust_root=True):
    """Prevent visible text-bearing widgets from being compressed below content."""
    if root.layout() is not None:
        root.layout().activate()

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

    if root.layout() is not None:
        root.layout().activate()

    if adjust_root:
        size_hint = root.sizeHint()
        title_width = _window_title_width_hint(root)
        _raise_maximum_height(root, size_hint.height())
        _raise_maximum_width(root, max(size_hint.width(), title_width))
        root.setMinimumSize(
            root.minimumSize().expandedTo(size_hint.expandedTo(QSize(title_width, 0)))
        )
        root.adjustSize()


def _fit_text_widgets_to_contents(root):
    for label in root.findChildren(QLabel):
        if _is_hidden_for_fit(label, root) or not str(label.text()).strip():
            continue
        _fit_widget_width_to_hint(label, label.sizeHint().width())

    for combo_box in root.findChildren(QComboBox):
        if _is_hidden_for_fit(combo_box, root):
            continue
        combo_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        _fit_widget_width_to_hint(
            combo_box,
            max(combo_box.sizeHint().width(), _combo_contents_width(combo_box)),
        )
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
        if current.isHidden():
            return True
        current = current.parentWidget()
    return False


def _fit_widget_width_to_hint(widget, width):
    _raise_maximum_width(widget, width)
    widget.setMinimumWidth(max(widget.minimumWidth(), width))
    if widget.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed:
        widget.setSizePolicy(QSizePolicy.Preferred, widget.sizePolicy().verticalPolicy())


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
        if not group_box.isHidden() and _has_visible_option_button(group_box)
    ]


def _has_visible_option_button(group_box):
    option_buttons = group_box.findChildren(QCheckBox) + group_box.findChildren(
        QRadioButton
    )
    return any(
        not button.isHidden() and str(button.text()).strip()
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
