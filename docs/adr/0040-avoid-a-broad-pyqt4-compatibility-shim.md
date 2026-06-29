# Avoid a Broad PyQt4 Compatibility Shim

Removed or deprecated Qt4 APIs should be replaced locally with direct PyQt5 equivalents when the migration path is obvious. Small focused Qt compatibility helpers are acceptable when the same pattern repeats across multiple compatibility slices, but the port should not introduce a broad fake-PyQt4 shim layer.

A broad shim would hide real Qt5 behavior differences and become a second framework to maintain.

The temporary `src/pyqt4_compat.py` helper was allowed only as an automation or test bootstrap helper while compatibility slices were being brought up. It was not the production migration strategy for Release Cutover, and production code should not depend on fake `PyQt4` modules, broad builtin monkeypatches, or R-stack stubs from that retired helper.
