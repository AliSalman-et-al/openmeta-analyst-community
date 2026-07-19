"""Publication-oriented limits for user-authored plot text."""

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QToolTip

PLOT_TEXT_INPUT_LIMIT = 80


def apply_plot_text_input_limits(surface):
    """Limit plot-only labels without constraining data or numeric fields."""
    message = (
        "Plot labels are limited to %d characters for publication readability."
        % (PLOT_TEXT_INPUT_LIMIT,)
    )
    for name in (
        "col1_str_edit",
        "col2_str_edit",
        "col3_str_edit",
        "col4_str_edit",
        "x_lbl_le",
    ):
        widget = getattr(surface, name, None)
        if widget is None:
            continue
        widget.setMaxLength(PLOT_TEXT_INPUT_LIMIT)
        widget.setProperty("plotTextInputLimit", PLOT_TEXT_INPUT_LIMIT)
        widget.setProperty("plotTextWasEdited", False)
        widget.setToolTip(message)
        widget.textEdited.connect(
            lambda _text, w=widget: w.setProperty("plotTextWasEdited", True)
        )
        if hasattr(widget, "inputRejected"):
            widget.inputRejected.connect(
                lambda w=widget, text=message: QToolTip.showText(
                    w.mapToGlobal(QPoint(0, w.height())), text, w
                )
            )


def set_plot_text_value(widget, value):
    """Load bounded text while retaining an untouched legacy value losslessly."""
    text = str(value)
    widget.setProperty("plotTextOriginalValue", None)
    widget.setProperty("plotTextWasEdited", False)
    limit = widget.property("plotTextInputLimit")
    if limit is not None and len(text) > int(limit):
        message = (
            "This saved label exceeded the %d-character publication limit and was "
            "shortened for editing. The original is retained unless you change it."
            % int(limit)
        )
        widget.setToolTip(message)
        widget.setStyleSheet("border: 1px solid #b7791f;")
        widget.setProperty("plotTextWasTruncated", True)
        widget.setProperty("plotTextOriginalValue", text)
    widget.setText(text)


def plot_text_value(widget):
    """Return an untouched legacy value, or the user's bounded replacement."""
    original = widget.property("plotTextOriginalValue")
    if original is not None and not widget.property("plotTextWasEdited"):
        return str(original)
    return widget.text()
