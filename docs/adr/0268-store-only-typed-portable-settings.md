# Store only typed portable settings

`QSettings` is a versioned application contract accessed through the settings module, not a store for arbitrary Qt values. Each key has an explicit type, default, validator, and codec, and stored values use portable primitives such as strings, numbers, booleans, and lists. Binding-specific values including `QColor`, `QPoint`, `QRect`, `QByteArray`, and `QVariant` are replaced with validated application-owned representations so settings remain inspectable and stable across Qt and binding upgrades.
