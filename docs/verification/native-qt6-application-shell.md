# Native Qt6 application shell

Issue #333 restores the first full user-facing application boundary after the
mechanical PyQt6 cutover. The maintained `rc-metastudio` entry point constructs
one `QApplication`, applies the complete application identity, registers the
binary resource collection, and opens the real `MetaForm` shell.

## Behavioral evidence

`tests/python/gui/test_qt6_application_shell.py` verifies:

- repeated open/close cycles reuse one PyQt6 application and delete each owned
  shell;
- the installed module entry point launches the real shell and exits cleanly;
- menu actions use native `QAction` objects, registered resources, platform
  shortcuts, explicit signal overloads, and exactly-once About and file-dialog
  behavior;
- cancel and failed-save paths retain the live shell;
- injected R-load and partial-shell construction failures release splash,
  window, child, and signal ownership under fatal Qt warnings;
- obsolete Qt5 placement data is removed without resetting domain preferences,
  analysis settings, or recent projects;
- corrupt schema values are parsed without Qt coercion and repaired locally;
- geometry and splitter state use range-checked JSON primitives rather than Qt
  value objects, while portable column-width state survives migration; and
- adaptive-window roles are typed Python state rather than dynamic QObject
  properties.

The maintained Qt6 lane also runs `rc-metastudio
--automation-native-shell-smoke` with `QT_QPA_PLATFORM` unset and
`QT_FATAL_WARNINGS=1`. On Windows it requires the native `qwindows` plugin; on
macOS it requires Cocoa. This smoke does not invoke analysis, so Analysis
Behavior remains synchronous and its R-backed gates remain independently
owned.
