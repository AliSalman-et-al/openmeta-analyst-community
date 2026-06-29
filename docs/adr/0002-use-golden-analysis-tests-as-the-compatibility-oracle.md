# Use Golden Analysis Tests as the Compatibility Oracle

OpenMeta[Analyst] Community will treat the current Python 2.7, PyQt4, and bundled R-package application as the reference implementation for analysis behavior during the Python 3 and Qt 5 migration. Compatibility should be proven through golden analysis tests built from existing sample data and legacy test coverage, with numerically equivalent analysis outputs under explicit tolerances, stable result text where practical, and generated plots checked for equivalent analysis content rather than pixel-perfect rendering.

This keeps the modernization focused on preserving statistical behavior while allowing GUI rendering, formatting, and toolkit-level presentation details to change where Qt 5 makes exact reproduction impractical.
