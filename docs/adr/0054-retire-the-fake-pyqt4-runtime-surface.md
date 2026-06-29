# Retire the Fake PyQt4 Runtime Surface

The modern path will no longer install fake `PyQt4` modules or monkeypatch Qt5 with old-style `SIGNAL`, `SLOT`, `QString`, `QVariant`, `QObject.connect`, or `QAbstractItemModel.reset` behavior. Existing project-file read compatibility remains handled by the legacy pickle loader, while modern tests and automation use a small bootstrap helper for R-backend selection only. This keeps the release artifact on an honest PyQt5 surface without losing the ability to open legacy `.oma` files.
