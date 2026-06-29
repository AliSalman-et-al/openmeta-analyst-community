# Target PyQt5 for the First Qt Port

The first Qt migration target will be PyQt5 rather than PySide2 or a dual-binding compatibility layer. The existing application is heavily PyQt4-specific, including generated `pyuic` files, old-style signals, `QString` and `QVariant` usage, and broad `QtGui` imports; PyQt5 is the closest migration path while still moving to Qt 5.

A dual-binding abstraction can be reconsidered after the application runs and the analysis compatibility harness is stable, but adding it during the first port would increase migration surface area without preserving analysis behavior.
