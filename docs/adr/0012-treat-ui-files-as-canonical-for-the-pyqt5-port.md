# Treat UI Files as Canonical for the PyQt5 Port

Qt Designer `.ui` files will be treated as the canonical UI definitions during the PyQt5 port, and generated Python UI modules should be regenerated with the PyQt5 UI compiler rather than manually hand-ported from PyQt4 output. The repository contains both `.ui` files and generated PyQt4 `ui_*.py` files, so editing generated code directly would create noisy diffs and risk preserving stale compiler output.

Manual changes should target the `.ui` files or application code that consumes the generated classes; generated UI modules should be reproducible build artifacts.
