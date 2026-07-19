# Add a focused Qt6 strict verification lane

RC MetaStudio will add a dedicated Qt6 strict verification lane that rejects active PyQt5 references, Qt5Compat, binding facades, short enums, stale PyQt5-generated markers, and known removed APIs; treats Python warnings as errors; and imports every Qt-bearing module. `QT_FATAL_WARNINGS=1` will be enabled only for focused GUI and native packaged-smoke coverage after known benign warnings are controlled, rather than globally, so Qt or platform-plugin noise cannot turn unrelated tests into opaque process aborts.
