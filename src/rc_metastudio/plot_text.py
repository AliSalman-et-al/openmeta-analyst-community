"""Publication-oriented limits for user-authored plot text."""

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QToolTip

PLOT_TEXT_INPUT_LIMIT = 80

# These values are emitted by the generated Qt forms for an untouched plot
# option.  Keep the list at the presentation boundary so renderers receive a
# real unset value rather than having to know about a GUI placeholder.
PLOT_DEFAULT_TEXT_SENTINELS = frozenset(
    ("", "[default]", "<default>", "(default)", "default")
)


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


def normalize_plot_text_value(value, *, was_edited=False):
    """Convert an untouched GUI default placeholder to an unset value.

    A researcher may deliberately use one of these strings as a label.  Such
    an edited value is therefore retained; only an untouched form default is
    normalized.  The pure value-level helper is also useful to non-Qt callers
    that already know whether a value came from an edited control.
    """
    if value is None:
        return None
    text = str(value)
    if not was_edited and text.strip().casefold() in PLOT_DEFAULT_TEXT_SENTINELS:
        return None
    return value


def plot_parameter_text_value(widget):
    """Return a plot text control's value with default placeholders unset."""
    return normalize_plot_text_value(
        plot_text_value(widget),
        was_edited=bool(widget.property("plotTextWasEdited")),
    )
