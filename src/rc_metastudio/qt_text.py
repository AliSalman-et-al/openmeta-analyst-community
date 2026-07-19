import math


def to_native_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return str(value, encoding="utf8")
    return str(value)


def is_blank(value):
    return to_native_text(value).strip() == ""


def parse_decimal(value):
    """Parse deliberate dot- or comma-decimal interface input.

    Project and R boundaries remain dot-decimal.  The interface accepts one
    decimal convention at a time and rejects ambiguous thousands/grouping
    syntax rather than silently changing a scientific value.
    """

    text, valid = normalize_decimal_text(value)
    if not valid or not text:
        return 0.0, False
    try:
        number = float(text)
    except (TypeError, ValueError):
        return 0.0, False
    return (number, True) if math.isfinite(number) else (0.0, False)


def normalize_decimal_text(value):
    """Return unambiguous finite numeric text in dot-decimal form."""

    text = to_native_text(value).strip()
    if not text:
        return "", True
    if "," in text:
        if "." in text or text.count(",") != 1:
            return "", False
        text = text.replace(",", ".")
    try:
        number = float(text)
    except (TypeError, ValueError):
        return "", False
    return (text, True) if math.isfinite(number) else ("", False)
