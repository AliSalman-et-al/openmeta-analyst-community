# Build Headless Analysis Regression Before GUI Port

The first migration milestone will be a headless analysis regression harness that can run golden analysis tests against reference outputs before the PyQt5 GUI port is considered complete. The legacy tests currently create a `QApplication` and `MetaForm`, which mixes statistical compatibility, Qt lifecycle behavior, and GUI state; separating the analysis compatibility signal first reduces the number of moving parts when porting to Python 3 and Qt 5.

The GUI migration can still proceed incrementally, but it should not be used as the primary proof that analysis behavior was preserved.
