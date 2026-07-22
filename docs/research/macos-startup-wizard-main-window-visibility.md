# macOS startup wizard / main-window visibility research

## Scope and conclusion

RC MetaStudio creates and requests display of `MetaForm`, then immediately enters
`MainWizard.exec()` from `MetaForm.start()`, before it enters the application's
ordinary `QApplication.exec()` loop (`src/rc_metastudio/launch.py` and
`src/rc_metastudio/meta_form.py`). The strongest platform-sensitive risk is this
nested startup event-loop design, not stale saved geometry. Qt explicitly
discourages `QDialog.exec()` because its nested event loop is not fully supported
by some platforms, and recommends asynchronous `open()` plus the `finished()`
signal instead. `QWizard` inherits `QDialog`, so that guidance applies directly.
[Qt `QDialog` documentation](https://doc.qt.io/qt-6/qdialog.html#exec)

The symptom also proves that the shell object and its dataset state survive: the
quit path reaches the main window's unsaved-data confirmation after a dataset is
created. That makes failure to construct the shell or process wizard results a
poor fit. A visibility/activation transition after the startup dialog closes is
the narrower target.

## Repository-specific findings

1. `launch.start()` calls `_create_interactive_shell()`. That function constructs
   `MetaForm`, calls `splash.finish(meta)`, and calls `_show_main_window(meta)`.
   Only after it returns does `start()` call `meta.start()`, which synchronously
   calls `MainWizard.exec()`. Only after the wizard returns does startup reach the
   outer `app.exec()`.

2. The wizard has `parent=self`, where `self` is the main window. Qt says a
   parented dialog remains a top-level window, is centered over the parent's
   top-level window, and shares its taskbar entry. `exec()` makes it modal and
   blocks until accepted or rejected. A parent relationship alone does not
   guarantee stacking; modality controls blocking/stacking behavior.
   [Qt `QDialog` detailed description](https://doc.qt.io/qt-6/qdialog.html#details)

3. `_show_main_window()` delegates to
   `settings.restore_main_window_placement()`. The current placement format is a
   validated JSON `QRect`, not raw `QWidget.saveGeometry()` bytes. It rejects
   malformed data and clamps a valid remembered rectangle into one of
   `QScreen.availableGeometry()` rectangles. Qt defines available geometry as the
   screen rectangle excluding reserved areas such as the menu bar and Dock.
   [Qt `QScreen::availableGeometry`](https://doc.qt.io/qt-6/qscreen.html#availableGeometry-prop)
   Therefore a simply off-screen remembered rectangle is already substantially
   defended against in current source.

4. The adaptive main-window policy requests `WindowMaximized` during
   registration, and placement restore later selects fullscreen, maximized, or
   ordinary `show()`. Qt documents that `setWindowState()` on a hidden widget is
   applied when `show()` is called, but also warns that calling
   `setWindowState()` hides the widget and it must be shown again. The current
   restore function does issue a corresponding show operation, so instrumentation
   should check for a later state mutation rather than assume geometry restore is
   intrinsically broken.
   [Qt `QWidget::setWindowState`](https://doc.qt.io/qt-6/qwidget.html#setWindowState)

5. No startup path calls `raise_()` or `activateWindow()` after the wizard is
   accepted. Qt defines an active window as a *visible* top-level window with
   keyboard focus; `activateWindow()` does nothing if the window is not visible,
   and Qt recommends pairing it with `raise()` when stacking must also be
   ensured. Thus activation is a postcondition, not a substitute for fixing a
   hidden/unexposed window.
   [Qt `QWidget::activateWindow`](https://doc.qt.io/qt-6/qwidget.html#activateWindow),
   [Qt `QWidget::raise`](https://doc.qt.io/qt-6/qwidget.html#raise)

6. Qt says ordinary user interaction generally cannot happen before the main
   application event loop begins; modal widgets are a special case because they
   start a local event loop. That is exactly the current startup shape and
   reinforces why it can behave differently from the normal Windows event path.
   [Qt `QApplication::exec`](https://doc.qt.io/qt-6/qapplication.html#exec)

7. On macOS the expected Qt platform plugin is `cocoa`. This should be asserted
   in the native reproduction so an offscreen/minimal plugin does not produce a
   misleading visibility result.
   [Qt `QGuiApplication::platformName`](https://doc.qt.io/qt-6/qguiapplication.html#platformName-prop)

## Recommended implementation direction

Replace the startup `MainWizard.exec()` call with asynchronous dialog flow after
the outer application loop has started:

- show the main shell first;
- schedule/open the wizard with `QTimer.singleShot(0, ...)` and `QDialog.open()`;
- retain the wizard as an instance attribute until `finished` fires;
- on `Accepted`, consume `get_results()` and update the dataset;
- after the dialog is gone, ensure the shell is not minimized, call `show()` (or
  preserve its requested maximized/fullscreen mode), then `raise_()` and
  `activateWindow()`.

Qt warns that an asynchronously shown dialog must not be a short-lived local
object, because it would be destroyed when the caller returns. Keeping it on the
`MetaForm` instance is therefore required, not merely stylistic.
[Qt modal-dialog guidance](https://doc.qt.io/qt-6/qdialog.html#modal-dialogs)

Do not make `raise_()`/`activateWindow()` the only fix. They cannot reveal a
widget that is actually hidden, and a timing-only foreground request can conceal
the unsupported nested-loop lifecycle rather than remove it.

## Native diagnostic and regression signal

On the real Cocoa build, record the following at four boundaries: immediately
after `_show_main_window`, when the wizard becomes visible, in its `finished`
handler, and one queued event-loop turn later:

- `QGuiApplication.platformName()` (must be `cocoa`);
- `QGuiApplication.applicationState()`;
- `MetaForm.isVisible()`, `isHidden()`, `isMinimized()`, `isMaximized()`, and
  `isActiveWindow()`;
- `MetaForm.windowHandle().isVisible()` and `isExposed()` when a handle exists;
- main frame geometry and every screen's `availableGeometry()`;
- `QApplication.activeModalWidget()` and `activeWindow()`.

Qt distinguishes a requested show from actual exposure: a show event means the
window requested visibility, while successful display is followed by resize and
expose events. A native regression check should therefore assert both Qt widget
visibility and `windowHandle().isExposed()`, then use macOS accessibility or
Computer Use to confirm a discoverable main window after both the create-new and
open-existing wizard paths.
[Qt `QWindow::showEvent`](https://doc.qt.io/qt-6/qwindow.html#showEvent),
[Qt `QWindow::isExposed`](https://doc.qt.io/qt-6/qwindow.html#isExposed)

If the asynchronous conversion does not fix the native failure, the captured
states cleanly separate the next branches:

- visible but not exposed: Cocoa/native-window ordering or invalid state;
- exposed but inactive/behind: explicit raise/activation transition;
- hidden after `finished`: locate the exact later `hide()` or
  `setWindowState()` caller;
- valid exposure but unreachable frame: placement/clamping defect.

## Geometry fallback

If diagnostics identify placement rather than lifecycle, use Qt's standard
`saveGeometry()`/`restoreGeometry()` pair or retain the repository's typed frame
format with its current screen clamp. Qt's `restoreGeometry()` already adjusts
off-screen geometry to available screen geometry. Do not restore arbitrary
unvalidated coordinates and then treat activation as a placement repair.
[Qt restoring-window-geometry guide](https://doc.qt.io/qt-6/restoring-geometry.html),
[Qt `QWidget::restoreGeometry`](https://doc.qt.io/qt-6/qwidget.html#restoreGeometry)
