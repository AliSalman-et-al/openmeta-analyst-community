def to_native_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return str(value, encoding="utf8")
    return str(value)


def is_blank(value):
    return to_native_text(value).strip() == ""
