# Type every Qt item-model role

Every custom Qt item model will define and test an explicit PyQt6 role and value-type contract. Implementations use scoped `Qt.ItemDataRole`, item-flag, orientation, and check-state enums; return only documented native Python or Qt value types for each role; return `None` when data is unavailable; and reject invalid edits deliberately. Model tests cover valid and invalid `QModelIndex` inputs, flags, headers, editing, reset behavior, and signal payloads. Legacy `QVariant.value()` handling is removed.
