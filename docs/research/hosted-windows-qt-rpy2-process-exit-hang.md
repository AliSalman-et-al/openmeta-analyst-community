# Hosted Windows Qt/rpy2 process-exit hang

**Date:** 2026-07-17
**Scope:** Issue #340, `scripts/native_calculator_smoke.py`, hosted Windows job
`87833066350` in run [`29564204598`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29564204598).

## Executive finding

The latest failure is a real five-minute child-process hang, not a job timeout
that should be solved by increasing `timeout-minutes`. The per-command watchdog
worked: it reported `Native Qt6 calculator smoke timed out after 300 seconds`,
killed the child process tree, and returned exit code 124. In the same run,
Windows source/Fast verification, macOS Intel source/Fast verification, macOS
ARM64 source/Fast verification, and the separate native macOS feasibility run
passed.

The strongest explanation is the unconditional `QSettings.sync()` in
`save_settings()`. The final visible `saved settings` line is printed
immediately before that call. In the exact locked Qt 6.11.1 Windows source,
`QWinSettingsPrivate::sync()` consists of `RegFlushKey(writeHandle())`.
Microsoft documents that `RegFlushKey` is expensive, blocks modifications to
the entire registry hive, and returns only after all dirty data for that hive
has reached the registry store. That is an excellent match for a hosted runner
stall which does not reproduce on a normal interactive workstation.

Removing this explicit sync does not discard Windows setting writes. The same
Qt source writes each value immediately with `RegSetValueEx`; its Windows
`flush()` implementation is deliberately a no-op because Windows handles lazy
persistence. Microsoft states that registry modifications are visible to other
processes without `RegFlushKey` and recommends normal lazy flush unless an
application requires an immediate physical-disk durability guarantee. RC
MetaStudio has no such requirement when saving ordinary UI preferences during
window close.

There is a second, independent harness defect: the calculator script claims to
select the stub backend but accidentally imports and initializes real rpy2/R.
Unlike `native_analysis_smoke.py`, it does not call `install_stub_meta_py_r()`
before importing the legacy GUI modules. The hosted log proves this with
`importing from rpy2`. This adds avoidable startup and a second possible
shutdown hazard, but it is now ranked behind the exact registry-flush boundary.

## Evidence from the failing run and repository

1. The calculator completed its behavioral assertions through the binary edit,
   model update, and main-window close handler. The last burst at
   `08:00:36Z` ended with `saved settings`; the watchdog fired at
   `08:05:34Z`. This is approximately the configured 300-second command limit,
   rather than the workflow's broader job limit.
2. `run_with_timeout.py` inherits the child's streams; it does not use a pipe
   that the parent must drain. The watchdog therefore rules down a parent-side
   output deadlock.
3. `native_calculator_smoke.py` sets `RCMS_STUB_BACKEND=1`, but it later imports
   `binary_data_form`, `continuous_data_form`, and `diagnostic_data_form`
   directly without first installing the stub module. The hosted log confirms
   that real `meta_py_r` and rpy2 were nevertheless imported.
4. `native_analysis_smoke.py` uses the intended ordering: it imports
   `meta_py_r_backend`, calls `install_stub_meta_py_r()`, and only then imports
   legacy GUI modules. The calculator harness should use the same boundary.
5. `tests/r_stack/test_inprocess_rpy2_backend.py` already flushes output and
   calls `os._exit(0)` after passing real-R assertions because its comment says
   embedded-R finalizers can fault during Windows interpreter shutdown. That is
   a direct repository precedent for isolating verification assertions from a
   known-unsafe embedded-runtime teardown.
6. A local interactive-Windows control run of the full calculator harness
   returned normally in about five seconds. The defect is therefore
   environment-sensitive and should be diagnosed on the hosted seam; local
   success does not contradict the hosted shutdown failure.

## What the primary sources establish

### Qt close and settings behavior

`QWidget.close()` synchronously sends a close event. If accepted, the widget is
hidden; it is only deleted automatically when `WA_DeleteOnClose` is set. The
last primary window can emit `lastWindowClosed`, and the application normally
quits after that signal when `quitOnLastWindowClosed` is true
([Qt `QWidget::close`](https://doc.qt.io/qt-6/qwidget.html#close),
[Qt `QGuiApplication::lastWindowClosed`](https://doc.qt.io/qt-6/qguiapplication.html#lastWindowClosed)).
Changing `quitOnLastWindowClosed` can affect event-loop termination, but it does
not bypass the synchronous close event or native-window teardown.

`QApplication.exec()` waits until `exit()` is called, while a modal dialog may
run a local event loop even when the application-level loop was never entered.
Qt recommends putting cleanup on `aboutToQuit()` because the top-level event
loop is not guaranteed to return on every platform
([Qt `QApplication::exec`](https://doc.qt.io/qt-6/qapplication.html#exec)). The
calculator harness uses modal dialog loops but does not enter a top-level
`app.exec()` loop, so merely toggling last-window auto-quit is not evidence that
the process has completed normal Qt teardown.

`QSettings.sync()` writes pending changes **and** imports changes made by other
processes. On Windows, the default native format is stored in the registry
([Qt `QSettings`](https://doc.qt.io/qt-6/qsettings.html#sync),
[Qt platform-specific settings notes](https://doc.qt.io/qt-6/qsettings.html#platform-specific-notes)).

The decisive implementation detail is visible in Qt 6.11.1 itself:
`QWinSettingsPrivate::set()` calls `RegSetValueEx`, `sync()` calls
`RegFlushKey(writeHandle())`, and `flush()` does nothing with the comment
“Windows does this for us”
([Qt 6.11.1 `qsettings_win.cpp`](https://github.com/qt/qtbase/blob/v6.11.1/src/corelib/io/qsettings_win.cpp)).
Microsoft says `RegFlushKey` blocks registry-hive modifications system-wide,
returns only after the whole hive's dirty data is written to disk, and should
only be called explicitly for an immediate persistence guarantee. It also says
changes are visible without it and lazy flush is most efficient
([Microsoft `RegFlushKey`](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regflushkey)).

Qt requires running `QThread` instances to finish explicitly; `wait()` blocks
until the thread and its cleanup have completed. Nothing in the current harness
or hosted output identifies a live `QThread`, so this is a diagnostic check, not
the leading hypothesis
([Qt `QThread`](https://doc.qt.io/qt-6/qthread.html#wait)).

### rpy2 and embedded-R shutdown

In the exact rpy2 3.6.7 source, `rpy2.rinterface.initr()` registers
`endr(0)` with Python `atexit`
([rpy2 3.6.7 `rinterface/__init__.py`](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_7/rpy2-rinterface/src/rpy2/rinterface/__init__.py)).
Its `endr()` implementation takes the global R lock and calls, in order,
`R_dot_Last()`, `R_RunExitFinalizers()`, `Rf_KillAllDevices()`,
`R_CleanTempDir()`, `R_gc()`, and `Rf_endEmbeddedR()`
([rpy2 3.6.7 `embedded.py`](https://github.com/rpy2/rpy2/blob/RELEASE_3_6_7/rpy2-rinterface/src/rpy2/rinterface_lib/embedded.py)).
Any one of those native calls can make Python appear to have finished its own
code while the process remains alive.

rpy2's official low-level documentation explicitly cautions that ending an
embedded R should be considered carefully and that an ended R cannot be safely
restarted in the same process
([rpy2 low-level interface](https://rpy2.github.io/doc/v3.6.x/html/rinterface.html)).
The R Core manual likewise treats embedded R as a frontend integration and says
R API calls are generally required on the R main thread; Windows embedding has
additional frontend callback and event-processing responsibilities
([R Core, Writing R Extensions: threading and Windows embedding](https://stat.ethz.ch/R-manual/R-devel/doc/manual/R-exts.html#Embedding-R-under-Windows)).

No extra Python thread is required for this failure. CPython waits for live
non-daemon Python threads before completing program exit, but the observed
rpy2 import alone does not start its optional interactive event-processing
thread. A thread inventory is still a cheap exclusion probe
([Python `threading` thread objects](https://docs.python.org/3.11/library/threading.html#thread-objects)).

### Why the log endpoint is ambiguous

CPython documents that non-interactive stdout is block-buffered, whereas stderr
is line-buffered. `print(..., flush=True)` or `python -u` is necessary for
reliable phase markers in a hosted subprocess
([Python standard streams](https://docs.python.org/3.11/library/sys.html#sys.stdin)).
Therefore the absence of the final evidence JSON from the Actions log does not
prove that execution never reached it.

Python's `faulthandler.dump_traceback_later()` uses a watchdog thread and can
dump all Python thread stacks after a deadline, including on Windows. It cannot
name the exact native C frame when the main thread is inside rpy2/Qt, but it can
show the last Python call boundary
([Python `faulthandler`](https://docs.python.org/3.11/library/faulthandler.html#faulthandler.dump_traceback_later)).

## Ranked hypotheses

| Rank | Hypothesis | Confidence | Evidence and discriminator |
|---|---|---:|---|
| 1 | `QSettings.sync()` blocks in Windows `RegFlushKey` while flushing the hosted runner's entire user registry hive. | High | The last visible line is immediately before `sync()`; locked Qt 6.11.1 maps it directly to `RegFlushKey`; Microsoft documents the exact expensive, hive-wide blocking behavior. Add flushed markers before/after as confirmation. |
| 2 | Accidental real-rpy2 initialization later reaches the registered embedded-R `atexit` teardown. | Medium | Hosted log proves rpy2 import despite the stub flag; exact rpy2 source registers multi-stage native teardown; repo real-R tests already bypass Windows finalizers after assertions. It becomes leading only if an `after sync/after close` marker appears. |
| 3 | `window.close()` returns from the Python override but blocks in Qt's native-window destruction path. | Low | The identical failure persisted after removing the post-close event pump and disabling last-window auto-quit. A marker after `settings.sync()` and before/after `window.close()` discriminates it. |
| 4 | Interpreter waits for a non-daemon Python thread or running `QThread`. | Low | No current code or output identifies one. Log `threading.enumerate()` and all owned `QThread.isRunning()` states before return. |
| 5 | The timeout is simply too short or the watchdog is broken. | Ruled out | The watchdog fired at the configured 300 seconds, killed the child tree, and returned 124. |

## Recommended implementation sequence

1. **Remove the unconditional `settings.sync()` from `save_settings()`.** This
   avoids `RegFlushKey` on Windows while retaining the actual `RegSetValueEx`
   writes and normal OS lazy persistence. Add a Windows contract test that
   `save_settings()` does not explicitly call `sync()`, then write settings and
   verify immediate readback through a second `QSettings` object. This tests
   the user-visible persistence contract without demanding whole-hive
   physical-disk durability on every window close.
2. **Prove the boundary in the next hosted run.** Run the child unbuffered
   (`python -u`) and emit `flush=True` markers before/after the former sync
   boundary, return from `MetaForm.closeEvent`, entry/return of `window.close()`,
   evidence validation, and final `main()` return. Enable
   `faulthandler.dump_traceback_later(30, repeat=True)` until hosted proof is
   captured. These diagnostics should be removed or made opt-in after proof.
3. **Correct the calculator harness's backend boundary.** Before any legacy GUI
   import, call `meta_py_r_backend.install_stub_meta_py_r()`, exactly as
   `native_analysis_smoke.py` already does. Then assert that the selected module
   has `_oma_stub_backend is True` and that `rpy2.rinterface` is absent from
   `sys.modules`. This is not reduced coverage: the calculator test replaces
   every R calculation it uses and is intended to validate native Qt dialog,
   capture, model, undo, dirty-state, and rollback behavior. Real R/rpy2 is
   covered separately by the full R-stack verification immediately preceding
   the native smoke section.
4. **Keep the 300-second watchdog as a fail-fast guard, not as the fix.** Once
   accidental R initialization is removed, the calculator command should take
   seconds. A tighter 60-second guard is reasonable only after hosted timing is
   demonstrated; the workflow-level limit need not grow.
5. **If a dedicated real-R shutdown test is required, isolate it explicitly.**
   Exercise a representative real R call, flush and validate all evidence, and
   instrument `rpy2.rinterface.endr(0)` as its own phase. Do not let accidental
   imports in a calculator test stand in for an application shutdown contract.
   If clean `endr()` remains unsafe on hosted Windows, a verification-only
   `os._exit(0)` is defensible only after all assertions and artifact validation
   succeed, matching the existing R-stack subprocess precedent. It must not be
   used in the production application, where it would skip normal cleanup.
6. **Do not replace the registry with a test-only settings format merely to
   pass CI.** The root fix should remove an unnecessary durability flush while
   retaining production-format registry writes and readback coverage.

## Expected speed impact

Removing the unnecessary whole-hive registry flush should eliminate the
five-minute forced timeout and also make normal Windows app closure more
responsive. Correcting the unintended embedded-R initialization additionally
removes avoidable R startup. Neither change skips calculator assertions,
production-format settings readback, or evidence validation. The vertical
slice should save roughly five minutes per Windows run plus R import time
without weakening its quality gates.
