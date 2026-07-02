from PyQt5 import QtCore


def is_invalid_qvariant(value):
    return isinstance(value, QtCore.QVariant) and not value.isValid()


def to_native_text(value):
    if value is None or is_invalid_qvariant(value):
        return ""
    if hasattr(value, "toString"):
        value = value.toString()
    if hasattr(value, "toUtf8"):
        return str(value.toUtf8(), encoding="utf8")
    if isinstance(value, bytes):
        return str(value, encoding="utf8")
    return str(value)


def is_blank(value):
    return to_native_text(value).strip() == ""
