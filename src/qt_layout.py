from PyQt5.QtWidgets import QCheckBox, QGroupBox, QRadioButton, QSizePolicy


def fit_option_groups_to_contents(root, adjust_root=True):
    """Prevent checkbox/radio groups from being compressed below their labels."""
    if root.layout() is not None:
        root.layout().activate()

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
        _raise_maximum_height(root, size_hint.height())
        _raise_maximum_width(root, size_hint.width())
        root.setMinimumSize(root.minimumSize().expandedTo(size_hint))
        root.adjustSize()


def _option_group_boxes(root):
    return [
        group_box
        for group_box in root.findChildren(QGroupBox)
        if not group_box.isHidden() and _has_visible_option_button(group_box)
    ]


def _has_visible_option_button(group_box):
    option_buttons = (
        group_box.findChildren(QCheckBox) +
        group_box.findChildren(QRadioButton)
    )
    return any(not button.isHidden() and str(button.text()).strip() for button in option_buttons)


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
