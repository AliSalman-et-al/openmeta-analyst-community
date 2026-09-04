"""Verification and automation workflows for RC MetaStudio."""

from __future__ import annotations

import faulthandler
import hashlib
import json
import os
import platform
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, cast

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QIcon, QPixmap

from rc_metastudio import adaptive_window, app_error_handler, meta_globals
from rc_metastudio import qt6_resources, settings
from rc_metastudio.cocoa_accessibility import (
    bounded_error_message,
    find_accessibility_element,
)
from rc_metastudio.result_text_identity import normalize_packaged_summary_identity
from rc_metastudio.r_call_serialization import serialized_r_call

from rc_metastudio.launch import (
    _configure_application,
    _create_interactive_shell,
    _dispose_new_top_levels,
    _dispose_qobjects,
    _emit_automation_phase,
    _import_main_window,
    _argument_value,
    _show_main_window,
    _top_level_ids,
    _set_application_icon,
    load_R_libraries,
)

PACKAGED_SUMMARY_SHA256_BY_SAMPLE = {
    "amino.rcms": "d37d0aa920c9ae2397b1c44d3fbe9f91d5d89b61fad43ced991148f2e51245d0",
    "BCG.rcms": "2cb1cb0b867b7280a8843f633a9a040f7810d4c9e0ab91ff6333d8110fc41933",
}
AUTOMATION_SMOKE_LOG_ENV = "RCMS_AUTOMATION_SMOKE_LOG"
ADAPTIVE_LAYOUT_EVIDENCE_LOG_ENV = "RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG"
NATIVE_FILE_DIALOG_OBSERVE_DELAY_MS = 250
NATIVE_FILE_DIALOG_TIMEOUT_MS = 10_000
CRITICAL_DIALOG_OBSERVE_DELAY_MS = 100
CRITICAL_DIALOG_TIMEOUT_MS = 5_000


def _write_automation_smoke_log(message):
    log_path = os.environ.get(ADAPTIVE_LAYOUT_EVIDENCE_LOG_ENV) or os.environ.get(
        AUTOMATION_SMOKE_LOG_ENV
    )
    if not log_path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(str(message))
            log_file.write("\n")
    except OSError:
        pass


def _run_automation_smoke(callback):
    try:
        return callback()
    except BaseException as exc:
        _write_automation_smoke_log("".join(traceback.format_exception(exc)))
        raise SystemExit(1) from exc


def dispatch(startup_argv: list[str]) -> int:
    """Dispatch one supported automation command after startup arguments resolve."""
    smoke_log = _argument_value(startup_argv, "--automation-smoke-log")
    if smoke_log:
        os.environ[AUTOMATION_SMOKE_LOG_ENV] = smoke_log
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-smoke":
        sample_path = (
            startup_argv[2]
            if len(startup_argv) > 2
            else os.path.join("sample_projects", "amino.rcms")
        )
        return start_automation_smoke(sample_path)
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-shell-smoke":
        return start_shell_smoke()
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-native-shell-smoke":
        return start_shell_smoke(require_native_window=True)
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-shell-failure-smoke":
        if len(startup_argv) != 3:
            raise SystemExit(
                "--automation-shell-failure-smoke requires r-load or meta-form"
            )
        return start_shell_failure_smoke(startup_argv[2])
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-native-smoke":
        sample_path = (
            startup_argv[2]
            if len(startup_argv) > 2
            else os.path.join("sample_projects", "amino.rcms")
        )
        return _run_automation_smoke(
            lambda: start_automation_smoke(sample_path, require_native_window=True)
        )
    if (
        len(startup_argv) > 1
        and startup_argv[1] == "--automation-package-surface-smoke"
    ):
        if len(startup_argv) != 4:
            raise SystemExit(
                "--automation-package-surface-smoke requires an evidence path and scale."
            )
        _write_automation_smoke_log("packaged-surface:dispatch")
        return _run_automation_smoke(
            lambda: start_package_surface_smoke(startup_argv[2], startup_argv[3])
        )
    if (
        len(startup_argv) > 1
        and startup_argv[1] == "--automation-package-runtime-probe"
    ):
        if len(startup_argv) != 3:
            raise SystemExit(
                "--automation-package-runtime-probe requires an output path."
            )
        return _run_automation_smoke(
            lambda: start_package_runtime_probe(startup_argv[2])
        )
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-wizard-layout-smoke":
        return _run_automation_smoke(start_wizard_layout_smoke)
    if len(startup_argv) > 1 and startup_argv[1] == "--automation-startup-wizard-smoke":
        if len(startup_argv) != 4:
            raise SystemExit(
                "--automation-startup-wizard-smoke requires an evidence path "
                "and project path."
            )
        return start_startup_wizard_smoke(startup_argv[2], startup_argv[3])
    if (
        len(startup_argv) > 1
        and startup_argv[1] == "--automation-adaptive-layout-evidence"
    ):
        if len(startup_argv) < 3:
            raise SystemExit(
                "--automation-adaptive-layout-evidence requires an output directory."
            )
        output_dir = startup_argv[2]
        sample_path = (
            startup_argv[3]
            if len(startup_argv) > 3
            else os.path.join("sample_projects", "amino.rcms")
        )
        return _run_automation_smoke(
            lambda: start_adaptive_layout_evidence(output_dir, sample_path)
        )
    raise SystemExit("Unknown automation command: %s" % startup_argv[1])


def start_automation(phase_callback=None):
    qt6_resources.ensure_application_resources()
    app_error_handler.install_global_exception_handler()
    main_window = _import_main_window()
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    _emit_automation_phase(phase_callback, "application:configured")
    baseline_ids = _top_level_ids(app)
    try:
        settings.setup_directories()
        _emit_automation_phase(phase_callback, "settings:ready")
        if os.environ.get("RCMS_REQUIRE_IN_PROCESS_RPY2") == "1":
            _emit_automation_phase(phase_callback, "r-libraries:start")
            load_R_libraries(app, None, phase_callback=phase_callback)
            _emit_automation_phase(phase_callback, "r-libraries:complete")
        _emit_automation_phase(phase_callback, "meta-form:create:start")
        meta = main_window.MainWindow()
        _emit_automation_phase(phase_callback, "meta-form:create:complete")
        _show_main_window(meta)
        _emit_automation_phase(phase_callback, "main-window:shown")
        return app, meta
    except BaseException:
        _dispose_new_top_levels(app, baseline_ids)
        raise


def start_automation_smoke(sample_path, require_native_window=False):
    _write_automation_smoke_log("packaged-workflow:start")
    hang_trace = _start_automation_hang_trace()
    app = None
    meta = None
    try:
        app, meta = start_automation(
            phase_callback=lambda phase: _write_automation_smoke_log(
                "packaged-workflow:shell:%s" % phase
            )
        )
        _write_automation_smoke_log("packaged-workflow:shell-created")
        if require_native_window:
            platform_name = app.platformName().lower()
            expected = "windows" if sys.platform == "win32" else "cocoa"
            if platform_name != expected:
                raise SystemExit(
                    "Native smoke loaded Qt platform %s, expected %s."
                    % (platform_name, expected)
                )
            app.processEvents()
            if not meta.isVisible():
                raise SystemExit(
                    "Native smoke main window was not visible on Qt platform %s."
                    % platform_name
                )
            print(
                "Native smoke showed the main window with Qt platform %s."
                % platform_name
            )
        sample_path = os.path.abspath(sample_path)
        _write_automation_smoke_log("packaged-workflow:project-open:start")
        if not meta.open(sample_path, raise_on_error=True):
            raise SystemExit("Could not open smoke-test project: %s" % sample_path)
        _write_automation_smoke_log("packaged-workflow:project-open:return")
        app.processEvents()
        _write_automation_smoke_log("packaged-workflow:sample-opened")
        model = meta.tableView.model()
        if model is None or model.rowCount() < 1:
            raise SystemExit(
                "Smoke-test project opened without table rows: %s" % sample_path
            )

        # Force a real paint pass. Painting queries data()/headerData() for paint
        # roles (e.g. BackgroundColorRole) that offscreen layout never touches, so
        # This catches paint-time model/data regressions in the packaged build. A
        # paint error aborts the process, failing the smoke test with a non-zero
        # exit code rather than shipping a build that crashes on first render.
        _write_automation_smoke_log("packaged-workflow:paint:start")
        _force_table_paint(app, meta)
        _write_automation_smoke_log("packaged-workflow:paint:complete")
        _write_automation_smoke_log("packaged-workflow:project-exercise:start")
        workflow = _exercise_packaged_project_workflow(app, meta, sample_path)
        workflow["sample_projects"] = _exercise_all_packaged_samples(meta, sample_path)
        _write_automation_smoke_log("packaged-workflow:project-exercise:complete")
        _write_automation_smoke_log("packaged-workflow:save-reopen-complete")
        evidence_path = os.environ.get("RCMS_PACKAGE_SMOKE_EVIDENCE")
        if evidence_path:
            evidence = {
                "schema_version": 1,
                "passed": True,
                "platform_plugin": app.platformName().lower(),
                "workflows": workflow,
                "scales": [],
            }
            Path(evidence_path).write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_automation_smoke_log("packaged-workflow:evidence-written")
    finally:
        try:
            if meta is not None:
                # Automation owns this disposable window.  Never let an earlier
                # smoke failure become an unattended save-confirmation dialog that
                # masks the real error until the outer watchdog expires.
                if meta.workspace.document is not None:
                    meta.workspace.mark_saved()
                _write_automation_smoke_log("packaged-workflow:teardown:close:start")
                meta.close()
                _write_automation_smoke_log("packaged-workflow:teardown:close:return")
                app.processEvents()
                _dispose_qobjects(app, (meta,))
                _write_automation_smoke_log(
                    "packaged-workflow:teardown:deferred-delete:complete"
                )
                remaining = app.topLevelWidgets()
                if remaining:
                    raise RuntimeError(
                        "automation teardown retained top-level Qt windows: %s"
                        % ", ".join(type(widget).__name__ for widget in remaining)
                    )
                _write_automation_smoke_log(
                    "packaged-workflow:teardown:top-level-windows:none"
                )
            if app is not None:
                _write_automation_smoke_log("packaged-workflow:teardown:app-quit:start")
                app.quit()
                _write_automation_smoke_log(
                    "packaged-workflow:teardown:app-quit:return"
                )
        finally:
            _stop_automation_hang_trace(hang_trace)
    _write_automation_smoke_log("packaged-workflow:post-close")
    _write_automation_smoke_log("packaged-workflow:return")
    return 0


def _exercise_all_packaged_samples(meta, representative_sample):
    from rc_metastudio import project_adapter, project_format

    sample_root = Path(representative_sample).resolve().parent
    manifest_path = sample_root / "manifest.json"
    manifest = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    manifest_projects = cast(list[dict[str, Any]], manifest["projects"])
    declared = sorted(cast(str, item["file"]) for item in manifest_projects)
    packaged = sorted(path.name for path in sample_root.glob("*.rcms"))
    if declared != packaged:
        raise RuntimeError("packaged sample manifest does not match the project set")

    metadata = {cast(str, item["file"]): item for item in manifest_projects}
    records = []
    for name in declared:
        path = sample_root / name
        raw_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if raw_sha256 != metadata[name]["sha256"]:
            raise RuntimeError("packaged sample hash mismatch: %s" % name)
        document = project_format.load_project(path)
        reconstructed = project_format.reconstruct_analysis_dataset(document)
        if reconstructed.semantic_sha256 != metadata[name]["semantic_sha256"]:
            raise RuntimeError("packaged sample semantic mismatch: %s" % name)
        if not meta.open(str(path), raise_on_error=True):
            raise RuntimeError("packaged application could not open sample: %s" % name)
        observed = cast(
            dict[str, Any],
            project_adapter.dataset_to_project(meta.model.dataset)["dataset"],
        )
        expected = cast(
            dict[str, Any],
            project_adapter.dataset_to_project(
                project_adapter.project_to_dataset(document.project)
            )["dataset"],
        )
        for field in ("title", "analysis_family", "outcomes", "studies"):
            if observed[field] != expected[field]:
                raise RuntimeError(
                    "packaged application loaded different %s semantics: %s"
                    % (field, name)
                )
        records.append(
            {
                "project": name,
                "sha256": raw_sha256,
                "semantic_sha256": reconstructed.semantic_sha256,
                "opened_in_packaged_application": True,
            }
        )
    return {
        "passed": True,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "projects": records,
    }


def _start_automation_hang_trace():
    path = os.environ.get("RCMS_AUTOMATION_HANG_TRACE")
    if not path:
        return None
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    trace = open(path, "a", encoding="utf-8")
    faulthandler.dump_traceback_later(60, repeat=True, file=trace)
    return trace


def _stop_automation_hang_trace(trace):
    if trace is None:
        return
    faulthandler.cancel_dump_traceback_later()
    trace.flush()
    trace.close()


def _native_accessibility_observation(widget):
    """Read the platform accessibility object exposed for a packaged control."""
    if sys.platform != "darwin":
        return {
            "role": "qt-focusable-control",
            "title": widget.accessibleName(),
            "description": widget.accessibleDescription(),
            "is_ignored": widget.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus,
            "exposed": widget.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus,
        }

    import ctypes

    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    message = objc.objc_msgSend

    def selector(name):
        return objc.sel_registerName(name.encode("ascii"))

    def object_message(receiver, name):
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_void_p
        return message(ctypes.c_void_p(receiver), selector(name))

    def object_message_with_object(receiver, name, value):
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_void_p
        return message(
            ctypes.c_void_p(receiver),
            selector(name),
            ctypes.c_void_p(value),
        )

    def ns_string(value):
        string_class = objc.objc_getClass(b"NSString")
        if not string_class:
            raise RuntimeError("Cocoa NSString class is unavailable")
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        message.restype = ctypes.c_void_p
        result = message(
            ctypes.c_void_p(string_class),
            selector("stringWithUTF8String:"),
            value.encode("utf-8"),
        )
        if not result:
            raise RuntimeError("Cocoa NSString construction failed")
        return int(result)

    def responds(receiver, name):
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_bool
        return bool(
            message(
                ctypes.c_void_p(receiver),
                selector("respondsToSelector:"),
                selector(name),
            )
        )

    def text_message(receiver, name):
        if not responds(receiver, name):
            return ""
        value = object_message(receiver, name)
        if not value:
            return ""
        raw = object_message(value, "UTF8String")
        return ctypes.cast(raw, ctypes.c_char_p).value.decode("utf-8") if raw else ""

    def optional_bool_message(receiver, name):
        if not responds(receiver, name):
            return None
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_bool
        return bool(message(ctypes.c_void_p(receiver), selector(name)))

    def array_values(array):
        if not array:
            return []
        message.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        message.restype = ctypes.c_ulong
        count = min(256, int(message(ctypes.c_void_p(array), selector("count"))))
        values = []
        for index in range(count):
            message.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            message.restype = ctypes.c_void_p
            value = message(ctypes.c_void_p(array), selector("objectAtIndex:"), index)
            if value:
                values.append(int(value))
        return values

    def modern_children(receiver):
        if not responds(receiver, "accessibilityChildren"):
            return []
        return array_values(object_message(receiver, "accessibilityChildren"))

    def qnsview_children(receiver):
        legacy_selector = "accessibilityAttributeValue:"
        if not responds(receiver, legacy_selector):
            return [], False
        # Qt 6's QNSView activates the Qt accessibility tree only through its
        # legacy AXChildren attribute handler. Calling accessibilityChildren on
        # the backing view bypasses that activation path.
        children_attribute = ns_string("AXChildren")
        children = object_message_with_object(
            receiver,
            legacy_selector,
            children_attribute,
        )
        return array_values(children), True

    def observe(receiver):
        return {
            "role": text_message(receiver, "accessibilityRole"),
            "title": text_message(receiver, "accessibilityTitle"),
            "description": text_message(receiver, "accessibilityLabel"),
            "is_ignored": optional_bool_message(receiver, "accessibilityIsIgnored"),
        }

    native_view = int(widget.winId())
    roots, bridge_supported = qnsview_children(native_view)
    observation = find_accessibility_element(
        roots,
        expected_role="AXButton",
        expected_title=widget.accessibleName(),
        expected_description=widget.accessibleDescription(),
        observe=observe,
        children=modern_children,
    )
    return {
        **observation,
        "bridge": "accessibilityAttributeValue:AXChildren",
        "bridge_supported": bridge_supported,
        "root_count": len(roots),
    }


def _persist_package_surface_failure(
    evidence_path, expected_scale, platform_name, stage, diagnostics
):
    """Persist bounded probe state before failing without creating pass evidence."""
    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    failure = {
        "requested": expected_scale,
        "platform_plugin": platform_name,
        "stage": stage,
        "diagnostics": diagnostics,
    }
    evidence.setdefault("failures", []).append(failure)
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_automation_smoke_log(
        "packaged-surface:failed:" + json.dumps(failure, sort_keys=True)
    )


def _record_package_surface_progress(evidence_path, expected_scale, stage):
    """Atomically retain the last bounded surface stage for outer-timeout RCA."""
    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence["surface_progress"] = {
        "requested": expected_scale,
        "stage": stage,
    }
    temporary = path.with_name(path.name + ".surface-progress.tmp")
    temporary.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)
    _write_automation_smoke_log("packaged-surface:" + stage)


def _native_file_dialog_observation(app, parent, checkpoint):
    """Exercise a Cocoa sheet without entering NSOpenPanel's blocking runModal."""
    file_dialog = QtWidgets.QFileDialog(parent, "Packaged native file dialog")
    file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
    file_dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, False)
    file_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    checkpoint("native-file-dialog:configured")
    observation = {
        "dont_use_native_dialog": file_dialog.testOption(
            QtWidgets.QFileDialog.Option.DontUseNativeDialog
        ),
        "window_modality": None,
        "visible_before_cancel": False,
        "cancel_requested": False,
        "finished_signal": False,
        "rejected_signal": False,
        "result": None,
        "rejected_value": int(QtWidgets.QDialog.DialogCode.Rejected),
        "timed_out": False,
        "timeout_ms": NATIVE_FILE_DIALOG_TIMEOUT_MS,
    }
    event_loop = QtCore.QEventLoop()
    observe_timer = QtCore.QTimer()
    observe_timer.setSingleShot(True)
    watchdog = QtCore.QTimer()
    watchdog.setSingleShot(True)

    def finish(result):
        observation["finished_signal"] = True
        observation["result"] = int(result)
        checkpoint("native-file-dialog:finished-signal")
        if event_loop.isRunning():
            event_loop.quit()

    def mark_rejected():
        observation["rejected_signal"] = True
        checkpoint("native-file-dialog:rejected-signal")

    def observe_and_cancel():
        observation["visible_before_cancel"] = file_dialog.isVisible()
        observation["cancel_requested"] = True
        checkpoint("native-file-dialog:reject:start")
        file_dialog.reject()
        checkpoint("native-file-dialog:reject:return")

    def time_out():
        observation["timed_out"] = True
        observation["error_type"] = "TimeoutError"
        observation["error_message"] = bounded_error_message(
            TimeoutError("native file dialog did not reject before its 10 second bound")
        )
        checkpoint("native-file-dialog:timeout")
        file_dialog.reject()
        if event_loop.isRunning():
            event_loop.quit()

    file_dialog.finished.connect(finish)
    file_dialog.rejected.connect(mark_rejected)
    observe_timer.timeout.connect(observe_and_cancel)
    watchdog.timeout.connect(time_out)
    watchdog.start(NATIVE_FILE_DIALOG_TIMEOUT_MS)
    checkpoint("native-file-dialog:open:start")
    file_dialog.open()
    checkpoint("native-file-dialog:open:return")
    observation["window_modality"] = file_dialog.windowModality().name
    observe_timer.start(NATIVE_FILE_DIALOG_OBSERVE_DELAY_MS)
    if not observation["finished_signal"]:
        checkpoint("native-file-dialog:event-loop:start")
        event_loop.exec()
        checkpoint("native-file-dialog:event-loop:return")
    observe_timer.stop()
    watchdog.stop()
    file_dialog.deleteLater()
    checkpoint("native-file-dialog:complete")
    return observation


def _critical_dialog_observation(parent, checkpoint):
    """Show and close the real critical dialog inside one bounded Qt loop."""
    dialog = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Icon.Critical,
        "Packaged critical dialog",
        "Deployment smoke diagnostic",
        QtWidgets.QMessageBox.StandardButton.Ok,
        parent,
    )
    dialog.setOption(QtWidgets.QMessageBox.Option.DontUseNativeDialog, False)
    dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    observation = {
        "dont_use_native_dialog": dialog.testOption(
            QtWidgets.QMessageBox.Option.DontUseNativeDialog
        ),
        "application_dont_use_native_dialogs": QtCore.QCoreApplication.testAttribute(
            QtCore.Qt.ApplicationAttribute.AA_DontUseNativeDialogs
        ),
        "dont_show_on_screen_before_show": dialog.testAttribute(
            QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen
        ),
        "dont_show_on_screen_after_show": None,
        "native_helper_active": False,
        "window_modality": None,
        "visible_before_close": False,
        "critical_icon": False,
        "finished_signal": False,
        "result": None,
        "accepted_value": int(QtWidgets.QDialog.DialogCode.Accepted),
        "timed_out": False,
        "timeout_ms": CRITICAL_DIALOG_TIMEOUT_MS,
    }
    event_loop = QtCore.QEventLoop()
    observe_timer = QtCore.QTimer()
    observe_timer.setSingleShot(True)
    watchdog = QtCore.QTimer()
    watchdog.setSingleShot(True)

    def finish(result):
        observation["finished_signal"] = True
        observation["result"] = int(result)
        checkpoint("critical-dialog:finished-signal")
        if event_loop.isRunning():
            event_loop.quit()

    def observe_and_accept():
        observation["visible_before_close"] = dialog.isVisible()
        observation["critical_icon"] = (
            dialog.icon() == QtWidgets.QMessageBox.Icon.Critical
        )
        checkpoint("critical-dialog:accept:start")
        dialog.accept()
        checkpoint("critical-dialog:accept:return")

    def time_out():
        observation["timed_out"] = True
        observation["error_type"] = "TimeoutError"
        observation["error_message"] = bounded_error_message(
            TimeoutError("critical dialog did not close before its 5 second bound")
        )
        checkpoint("critical-dialog:timeout")
        dialog.reject()
        if event_loop.isRunning():
            event_loop.quit()

    dialog.finished.connect(finish)
    observe_timer.timeout.connect(observe_and_accept)
    watchdog.timeout.connect(time_out)
    watchdog.start(CRITICAL_DIALOG_TIMEOUT_MS)
    checkpoint("critical-dialog:show:start")
    dialog.show()
    checkpoint("critical-dialog:show:return")
    observation["dont_show_on_screen_after_show"] = dialog.testAttribute(
        QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen
    )
    observation["native_helper_active"] = (
        observation["dont_use_native_dialog"] is False
        and observation["application_dont_use_native_dialogs"] is False
        and observation["dont_show_on_screen_before_show"] is False
        and observation["dont_show_on_screen_after_show"] is True
    )
    observation["window_modality"] = dialog.windowModality().name
    observe_timer.start(CRITICAL_DIALOG_OBSERVE_DELAY_MS)
    if not observation["finished_signal"]:
        checkpoint("critical-dialog:event-loop:start")
        event_loop.exec()
        checkpoint("critical-dialog:event-loop:return")
    observe_timer.stop()
    watchdog.stop()
    dialog.deleteLater()
    checkpoint("critical-dialog:complete")
    return observation


def _finish_package_surface_cleanup(app, native_window, checkpoint):
    """Close the disposable native window and drain only deferred deletions."""
    checkpoint("cleanup:native-window-close:start")
    close_accepted = native_window.close()
    checkpoint("cleanup:native-window-close:return")
    checkpoint("cleanup:deferred-delete:start")
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    checkpoint("cleanup:deferred-delete:complete")
    app.quit()
    checkpoint("cleanup:application-quit")
    return {
        "close_accepted": bool(close_accepted),
        "window_visible": native_window.isVisible(),
    }


def start_package_surface_smoke(evidence_path, expected_scale):
    """Exercise native package-only Qt surfaces at a requested scale factor."""

    def checkpoint(stage):
        _record_package_surface_progress(evidence_path, expected_scale, stage)

    checkpoint("entry")
    app_error_handler.install_global_exception_handler()
    checkpoint("application:create:start")
    app = app_error_handler.get_or_create_application(sys.argv)
    checkpoint("application:create:complete")
    _configure_application(app)
    checkpoint("application:configured")
    qt6_resources.ensure_application_resources()
    checkpoint("resources:ready")
    from PyQt6 import QtNetwork

    checkpoint("network-module:ready")
    platform_name = app.platformName().lower()
    if sys.platform == "win32" and platform_name != "windows":
        raise SystemExit("Package surface smoke did not load qwindows.")
    if sys.platform == "darwin" and platform_name != "cocoa":
        raise SystemExit("Package surface smoke did not load Cocoa.")

    clipboard = app.clipboard()
    checkpoint("clipboard:ready")
    clipboard_text = "RC MetaStudio clipboard – München – 1,25"
    clipboard.setText(clipboard_text)
    if clipboard.text() != clipboard_text:
        raise SystemExit("Package surface smoke clipboard round-trip failed.")
    checkpoint("clipboard:round-trip:complete")

    locale = QtCore.QLocale(QtCore.QLocale.Language.German)
    value, valid = locale.toDouble("1,25")
    if not valid or value != 1.25:
        raise SystemExit("Package surface smoke locale parsing failed.")

    if (
        QIcon(":/icons/actions/copy.svg").isNull()
        or QPixmap(":/misc/meta.png").isNull()
    ):
        raise SystemExit("Package surface smoke could not load binary resources.")
    tls_backends = list(QtNetwork.QSslSocket.availableBackends())
    if sys.platform == "win32" and "schannel" not in [
        backend.lower() for backend in tls_backends
    ]:
        raise SystemExit("Package surface smoke did not load the Schannel TLS backend.")
    if sys.platform == "darwin" and not tls_backends:
        raise SystemExit("Package surface smoke did not load a TLS backend.")
    available_styles = list(QtWidgets.QStyleFactory.keys())
    if not available_styles or app.style() is None:
        raise SystemExit("Package surface smoke found no Qt style plugin/style.")
    image_formats = sorted(
        value.data().decode("ascii").lower()
        for value in QtGui.QImageReader.supportedImageFormats()
    )
    if not {"ico", "jpeg", "svg"} <= set(image_formats):
        raise SystemExit(
            "Package surface smoke did not load required image/SVG plugins."
        )
    checkpoint("runtime-surfaces:ready")

    native_window = QtWidgets.QMainWindow()
    native_window.setWindowTitle("RC MetaStudio package surfaces")
    menu_bar = cast(QtWidgets.QMenuBar, native_window.menuBar())
    menu = cast(QtWidgets.QMenu, menu_bar.addMenu("Package smoke"))
    menu.addAction("Verified action")
    accessible_control = QtWidgets.QPushButton(
        "Accessible package control", native_window
    )
    accessible_control.setObjectName("packagedAccessibilityControl")
    accessible_control.setAccessibleName("Packaged accessibility control")
    accessible_control.setAccessibleDescription(
        "Verifies packaged Qt accessibility metadata."
    )
    accessible_control.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow, True)
    next_control = QtWidgets.QLineEdit(native_window)
    next_control.setObjectName("packagedKeyboardTraversalTarget")
    body = QtWidgets.QWidget(native_window)
    body_layout = QtWidgets.QVBoxLayout(body)
    body_layout.addWidget(accessible_control)
    body_layout.addWidget(next_control)
    native_window.setCentralWidget(body)
    native_window.setTabOrder(accessible_control, next_control)
    checkpoint("native-window:show:start")
    native_window.show()
    checkpoint("native-window:events:start")
    app.processEvents()
    checkpoint("native-window:visible")
    native_menu = {
        "is_native": bool(menu_bar.isNativeMenuBar()),
        "menu_count": len(menu_bar.actions()),
        "action_count": len(menu.actions()),
    }
    if (
        native_menu["menu_count"] < 1
        or native_menu["action_count"] < 1
        or (sys.platform == "darwin" and native_menu["is_native"] is not True)
    ):
        raise SystemExit(
            "Package surface smoke could not exercise the native menu bar."
        )
    accessible_control.setFocus()
    app.processEvents()
    focus_before = app.focusWidget()
    for event_type in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        app.sendEvent(
            accessible_control,
            QtGui.QKeyEvent(
                event_type,
                QtCore.Qt.Key.Key_Tab,
                QtCore.Qt.KeyboardModifier.NoModifier,
            ),
        )
    app.processEvents()
    focus_after = app.focusWidget()
    checkpoint("accessibility:observe:start")
    try:
        native_accessibility = (
            _native_accessibility_observation(accessible_control)
            if sys.platform == "darwin"
            else {}
        )
    except Exception as error:
        native_accessibility = {
            "role": "",
            "title": "",
            "description": "",
            "is_ignored": None,
            "exposed": False,
            "source": "accessibility-tree",
            "bridge": "accessibilityAttributeValue:AXChildren",
            "bridge_supported": False,
            "root_count": 0,
            "visited_nodes": 0,
            "observed_states": {},
            "error_type": type(error).__name__,
            "error_message": bounded_error_message(error),
        }
    accessibility = {
        "focus_before": focus_before.objectName() if focus_before else None,
        "focus_after_tab": focus_after.objectName() if focus_after else None,
        "accessible_name": accessible_control.accessibleName(),
        "accessible_description": accessible_control.accessibleDescription(),
        "native": native_accessibility,
    }
    checkpoint("accessibility:observed")
    if (
        accessibility["accessible_name"] != "Packaged accessibility control"
        or accessibility["accessible_description"]
        != "Verifies packaged Qt accessibility metadata."
        or (
            sys.platform == "darwin"
            and (
                accessibility["focus_before"] != "packagedAccessibilityControl"
                or accessibility["focus_after_tab"] != "packagedKeyboardTraversalTarget"
                or accessibility["native"].get("role") != "AXButton"
                or accessibility["native"].get("title")
                != "Packaged accessibility control"
                or accessibility["native"].get("description")
                != "Verifies packaged Qt accessibility metadata."
                or accessibility["native"].get("is_ignored") is not False
                or accessibility["native"].get("exposed") is not True
                or accessibility["native"].get("source") != "accessibility-tree"
                or accessibility["native"].get("bridge")
                != "accessibilityAttributeValue:AXChildren"
                or accessibility["native"].get("bridge_supported") is not True
                or int(accessibility["native"].get("root_count", 0)) < 1
            )
        )
    ):
        _persist_package_surface_failure(
            evidence_path,
            expected_scale,
            platform_name,
            "accessibility",
            accessibility,
        )
        raise SystemExit(
            "Package surface smoke could not exercise accessibility metadata."
        )

    try:
        native_file_dialog = _native_file_dialog_observation(
            app, native_window, checkpoint
        )
    except Exception as error:
        native_file_dialog = {
            "dont_use_native_dialog": False,
            "window_modality": None,
            "visible_before_cancel": False,
            "cancel_requested": False,
            "finished_signal": False,
            "rejected_signal": False,
            "result": None,
            "rejected_value": int(QtWidgets.QDialog.DialogCode.Rejected),
            "timed_out": False,
            "timeout_ms": NATIVE_FILE_DIALOG_TIMEOUT_MS,
            "error_type": type(error).__name__,
            "error_message": bounded_error_message(error),
        }
    if (
        native_file_dialog["dont_use_native_dialog"] is not False
        or native_file_dialog["window_modality"] != "WindowModal"
        or native_file_dialog["visible_before_cancel"] is not True
        or native_file_dialog["cancel_requested"] is not True
        or native_file_dialog["finished_signal"] is not True
        or native_file_dialog["rejected_signal"] is not True
        or native_file_dialog["result"] != native_file_dialog["rejected_value"]
        or native_file_dialog["timed_out"] is not False
        or native_file_dialog["timeout_ms"] != NATIVE_FILE_DIALOG_TIMEOUT_MS
    ):
        _persist_package_surface_failure(
            evidence_path,
            expected_scale,
            platform_name,
            "native-file-dialog",
            native_file_dialog,
        )
        raise SystemExit(
            "Package surface smoke could not exercise the native file dialog."
        )

    try:
        critical_dialog = _critical_dialog_observation(native_window, checkpoint)
    except Exception as error:
        critical_dialog = {
            "dont_use_native_dialog": False,
            "application_dont_use_native_dialogs": False,
            "dont_show_on_screen_before_show": None,
            "dont_show_on_screen_after_show": None,
            "native_helper_active": False,
            "window_modality": None,
            "visible_before_close": False,
            "critical_icon": False,
            "finished_signal": False,
            "result": None,
            "accepted_value": int(QtWidgets.QDialog.DialogCode.Accepted),
            "timed_out": False,
            "timeout_ms": CRITICAL_DIALOG_TIMEOUT_MS,
            "error_type": type(error).__name__,
            "error_message": bounded_error_message(error),
        }
    critical_dialog_invalid = (
        critical_dialog["window_modality"] != "WindowModal"
        or critical_dialog["visible_before_close"] is not True
        or critical_dialog["critical_icon"] is not True
        or critical_dialog["finished_signal"] is not True
        or critical_dialog["result"] != critical_dialog["accepted_value"]
        or critical_dialog["timed_out"] is not False
        or critical_dialog["timeout_ms"] != CRITICAL_DIALOG_TIMEOUT_MS
    )
    if sys.platform == "darwin":
        critical_dialog_invalid = critical_dialog_invalid or (
            critical_dialog["dont_use_native_dialog"] is not False
            or critical_dialog["application_dont_use_native_dialogs"] is not False
            or critical_dialog["dont_show_on_screen_before_show"] is not False
            or critical_dialog["dont_show_on_screen_after_show"] is not True
            or critical_dialog["native_helper_active"] is not True
        )
    if critical_dialog_invalid:
        _persist_package_surface_failure(
            evidence_path,
            expected_scale,
            platform_name,
            "critical-dialog",
            critical_dialog,
        )
        raise SystemExit("Package surface smoke could not show a critical dialog.")

    checkpoint("display-metrics:observe:start")
    primary = app.primaryScreen()
    if (
        primary is None
        or primary.devicePixelRatio() <= 0
        or primary.logicalDotsPerInch() <= 0
    ):
        raise SystemExit("Package surface smoke found invalid display metrics.")

    requested_scale = float(expected_scale)
    environment_scale = float(os.environ.get("QT_SCALE_FACTOR", "0"))
    observed_dpr = float(primary.devicePixelRatio())
    baseline_dpr = float(os.environ.get("RCMS_PACKAGE_BASELINE_DPR", "0"))
    expected_dpr = baseline_dpr * requested_scale
    tolerance = 0.05
    if abs(environment_scale - requested_scale) > 1e-9:
        raise SystemExit(
            "Package surface smoke scale environment differs from request."
        )
    if baseline_dpr <= 0 or abs(observed_dpr - expected_dpr) > tolerance:
        raise SystemExit(
            "Package surface smoke observed DPR %.4f, expected %.4f ± %.4f."
            % (observed_dpr, expected_dpr, tolerance)
        )

    cleanup = _finish_package_surface_cleanup(app, native_window, checkpoint)
    if cleanup["close_accepted"] is not True or cleanup["window_visible"] is not False:
        _persist_package_surface_failure(
            evidence_path,
            expected_scale,
            platform_name,
            "cleanup",
            cleanup,
        )
        raise SystemExit(
            "Package surface smoke could not cleanly close its native window."
        )

    checkpoint("evidence:write:start")
    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence.pop("surface_progress", None)
    evidence.setdefault("scales", []).append(
        {
            "requested": expected_scale,
            "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR"),
            "device_pixel_ratio": observed_dpr,
            "baseline_device_pixel_ratio": baseline_dpr,
            "expected_device_pixel_ratio": expected_dpr,
            "dpr_tolerance": tolerance,
            "logical_dpi": primary.logicalDotsPerInch(),
            "clipboard": True,
            "critical_dialog": critical_dialog,
            "binary_resources": True,
            "native_menu": native_menu,
            "native_file_dialog": native_file_dialog,
            "accessibility": accessibility,
            "tls_backends": tls_backends,
            "active_style": app.style().objectName(),
            "available_styles": available_styles,
            "image_formats": image_formats,
            "locale": "de_DE",
            "platform_plugin": platform_name,
            "cleanup": cleanup,
        }
    )
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_automation_smoke_log("packaged-surface:scale-%s-passed" % expected_scale)
    return 0


def _verified_frozen_runtime_shared_library(configured, api_bridge_path):
    """Return the private R library after validating the frozen runtime closure."""
    derivation = configured.get("derivation") or {}
    direct_spike = configured.get("direct_spike") is True
    executable_root = Path(sys.executable).resolve().parent
    if direct_spike:
        frameworks = executable_root.parent / "Frameworks"
        if not api_bridge_path.is_relative_to(frameworks.resolve()):
            raise RuntimeError(
                "Direct-spike rpy2 API bridge is outside the app framework tree."
            )
        shared_r_path = (Path(configured["R_HOME"]) / "lib" / "libR.dylib").resolve()
        if not shared_r_path.is_relative_to(frameworks.resolve()):
            raise RuntimeError("Direct-spike libR is outside the app framework tree.")
    elif derivation:
        final_identity = derivation.get("final", {})
        api_record = final_identity.get("api_bridge", {})
        expected_api_bridge = (
            executable_root / str(api_record.get("path", ""))
        ).resolve()
        if api_bridge_path != expected_api_bridge or hashlib.sha256(
            api_bridge_path.read_bytes()
        ).hexdigest() != api_record.get("sha256"):
            raise RuntimeError(
                "Loaded rpy2 API bridge differs from the authenticated kit derivation."
            )
        r_shared_record = final_identity.get("r_shared_library", {})
        shared_r_path = (
            executable_root / str(r_shared_record.get("path", ""))
        ).resolve()
    else:
        if not api_bridge_path.is_relative_to(executable_root):
            raise RuntimeError(
                "Loaded rpy2 API bridge is outside the frozen application bundle."
            )
        shared_r_path = (Path(configured["R_HOME"]) / "bin" / "x64" / "R.dll").resolve()
        if (
            not shared_r_path.is_relative_to(executable_root)
            or not shared_r_path.is_file()
        ):
            raise RuntimeError(
                "Frozen application is missing its private R shared library."
            )
    return shared_r_path, direct_spike


@serialized_r_call
def start_package_runtime_probe(output_path):
    """Report the runtime actually loaded by the assembled frozen executable."""
    import importlib
    import importlib.metadata

    from PyQt6 import sip

    from rc_metastudio import project_format, r_runtime

    project_schema_members = ["manifest.json", "project.json", "state.json"]
    for member in project_schema_members:
        project_format._schema(1, member)
    configured = r_runtime.configure_bundled_r_environment()
    api_bridge = importlib.import_module("_rinterface_cffi_api")
    from rpy2 import robjects
    from rpy2.rinterface_lib import openrlib

    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    primary = app.primaryScreen()
    if primary is None:
        raise SystemExit("Frozen runtime probe found no primary screen.")
    r_home_values = cast(
        Any, robjects.r("normalizePath(R.home(), winslash='/', mustWork=TRUE)")
    )
    r_version_values = cast(Any, robjects.r("as.character(getRversion())"))
    r_library_values = cast(
        Any, robjects.r("normalizePath(.libPaths(), winslash='/', mustWork=TRUE)")
    )
    r_home = str(r_home_values[0])
    r_version = str(r_version_values[0])
    r_library_paths = [str(value) for value in r_library_values]
    api_bridge_path = Path(str(api_bridge.__file__)).resolve()
    shared_r_path, direct_spike = _verified_frozen_runtime_shared_library(
        configured, api_bridge_path
    )
    macos_r_policy = None
    if sys.platform == "darwin":
        tcltk_available = bool(
            cast(
                Any,
                robjects.r("isTRUE(requireNamespace('tcltk', quietly=TRUE))"),
            )[0]
        )
        tcltk_loaded = bool(cast(Any, robjects.r("'tcltk' %in% loadedNamespaces()"))[0])
        aqua = bool(cast(Any, robjects.r("capabilities('aqua')"))[0])
        bitmap_type = str(cast(Any, robjects.r("getOption('bitmapType')"))[0])
        png_path = str(
            cast(
                Any,
                robjects.r(
                    "output <- tempfile(fileext='.png'); grDevices::png(output); "
                    "graphics::plot(1, 1); grDevices::dev.off(); output"
                ),
            )[0]
        )
        png = Path(png_path)
        if (
            tcltk_available
            or tcltk_loaded
            or not aqua
            or bitmap_type != "quartz"
            or not png.is_file()
        ):
            raise SystemExit(
                "Packaged macOS R runtime violates the non-X11 Quartz policy."
            )
        macos_r_policy = {
            "tcltk_available": tcltk_available,
            "tcltk_loaded": tcltk_loaded,
            "aqua": aqua,
            "bitmap_type": bitmap_type,
            "default_png": {
                "size": png.stat().st_size,
                "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
            },
        }
        if macos_r_policy["default_png"]["size"] <= 0:
            raise SystemExit("Packaged macOS default Quartz png probe failed.")
        png.unlink()
    probe = {
        "schema_version": 1,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": {
            "version": platform.python_version(),
            "executable": str(Path(sys.executable).resolve()),
            "architecture": platform.machine(),
            "bundle_root": str(Path(getattr(sys, "_MEIPASS", "")).resolve()),
        },
        "qt": {
            "pyqt_version": QtCore.PYQT_VERSION_STR,
            "compiled_qt_version": QtCore.QT_VERSION_STR,
            "runtime_qt_version": QtCore.qVersion(),
            "sip_runtime_version": sip.SIP_VERSION_STR,
            "platform_plugin": app.platformName().lower(),
            "plugins_path": QtCore.QLibraryInfo.path(
                QtCore.QLibraryInfo.LibraryPath.PluginsPath
            ),
            "library_paths": list(app.libraryPaths()),
            "scale_factor_environment": os.environ.get("QT_SCALE_FACTOR"),
            "baseline_device_pixel_ratio": float(primary.devicePixelRatio()),
            "baseline_logical_dpi": float(primary.logicalDotsPerInch()),
        },
        "rpy2": {
            "distribution_version": importlib.metadata.version("rpy2"),
            "rinterface_distribution_version": importlib.metadata.version(
                "rpy2-rinterface"
            ),
            "robjects_distribution_version": importlib.metadata.version(
                "rpy2-robjects"
            ),
            "cffi_mode": os.environ.get("RPY2_CFFI_MODE"),
            "loaded_cffi_mode": openrlib.cffi_mode.name,
            "api_bridge_loaded": openrlib.cffi_mode.name == "API",
            "api_bridge_path": str(api_bridge_path),
            "api_bridge_sha256": hashlib.sha256(
                api_bridge_path.read_bytes()
            ).hexdigest(),
        },
        "project_schemas": {
            "version": 1,
            "validated_members": project_schema_members,
        },
        "r": {
            "version": r_version,
            "home": r_home,
            "library_paths": r_library_paths,
            "configured_home": configured.get("R_HOME"),
            "configured_library": configured.get("R_LIBS"),
            "macos_product_profile": macos_r_policy,
            "shared_library_path": str(shared_r_path),
            "shared_library_sha256": hashlib.sha256(
                shared_r_path.read_bytes()
            ).hexdigest(),
            "direct_spike": direct_spike,
            "lc_numeric": os.environ.get("LC_NUMERIC"),
        },
    }
    if configured.get("kit_sha256") is not None:
        probe["r"]["kit_sha256"] = configured["kit_sha256"]
    Path(output_path).write_text(
        json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_automation_smoke_log("packaged-runtime-probe:passed")
    return 0


def _exercise_packaged_project_workflow(app, meta, sample_path):
    from rc_metastudio import project_format

    expected_summary_sha256 = _expected_packaged_summary_sha256(sample_path)
    model = meta.tableView.model()
    study_index = model.index(0, model.NAME)
    edited_name = "Packaged Smoke – München"
    if not model.setData(study_index, edited_name):
        raise SystemExit("Packaged smoke could not edit representative data.")
    if model.data(study_index, QtCore.Qt.ItemDataRole.DisplayRole) != edited_name:
        raise SystemExit("Packaged smoke edit did not round-trip through the model.")

    save_root = Path(tempfile.mkdtemp(prefix="rcms-packaged-smoke-"))
    raw_index = model.index(0, model.RAW_DATA[0])
    original_raw = model.data(raw_index, QtCore.Qt.ItemDataRole.DisplayRole)
    numeric_value = float(str(original_raw).replace(",", "."))
    dot_text = "%.1f" % numeric_value
    comma_text = dot_text.replace(".", ",")

    variants = []
    for locale_name, numeric_text, destination in (
        ("en_US", dot_text, save_root / "dot-decimal.rcms"),
        ("de_DE", comma_text, save_root / "comma-decimal.rcms"),
    ):
        locale = QtCore.QLocale(locale_name)
        parsed_value, parsed = locale.toDouble(numeric_text)
        if not parsed or parsed_value != numeric_value:
            raise SystemExit(
                "Packaged smoke could not parse the %s locale boundary." % locale_name
            )
        if locale_name == "de_DE":
            if not meta.open(os.path.abspath(sample_path), raise_on_error=True):
                raise SystemExit(
                    "Packaged smoke could not reset the locale comparison project."
                )
            model = meta.tableView.model()
            study_index = model.index(0, model.NAME)
            raw_index = model.index(0, model.RAW_DATA[0])
            if not model.setData(study_index, edited_name):
                raise SystemExit(
                    "Packaged smoke could not repeat the representative edit."
                )
        if not model.setData(raw_index, numeric_text):
            raise SystemExit("Packaged smoke rejected %s numeric input." % locale_name)
        result = _assert_standard_binary_summary_is_formatted(meta)
        identity = _packaged_result_identity(result, expected_summary_sha256)
        _write_automation_smoke_log(
            "packaged-workflow:analysis-%s-complete" % locale_name
        )
        meta.out_path = str(destination)
        if meta.save() is not True or not destination.is_file():
            raise SystemExit(
                "Packaged smoke could not save the %s project." % locale_name
            )
        variants.append(
            {
                "locale": locale_name,
                "input": numeric_text,
                "canonical_value": numeric_value,
                "raw_summary_sha256": identity["raw_summary_sha256"],
                "normalized_summary_sha256": identity["normalized_summary_sha256"],
                "svg_sha256": identity["svg_sha256"],
                "path": destination,
            }
        )

    dot_project = project_format.load_project(variants[0]["path"]).project
    comma_project = project_format.load_project(variants[1]["path"]).project
    if dot_project != comma_project:
        raise SystemExit("Dot/comma packaged inputs did not persist canonically.")
    if variants[0]["raw_summary_sha256"] != variants[1]["raw_summary_sha256"]:
        raise SystemExit("Dot/comma packaged analyses produced different result text.")
    if variants[0]["svg_sha256"] != variants[1]["svg_sha256"]:
        raise SystemExit("Dot/comma packaged analyses produced different SVG content.")

    saved_path = variants[1]["path"]
    if not meta.open(str(saved_path), raise_on_error=True):
        raise SystemExit("Packaged smoke could not reopen the saved project.")
    reopened = meta.tableView.model()
    reopened_index = reopened.index(0, reopened.NAME)
    if reopened.data(reopened_index, QtCore.Qt.ItemDataRole.DisplayRole) != edited_name:
        raise SystemExit("Packaged smoke save/reopen lost the representative edit.")
    reopened_identity = _packaged_result_identity(
        _assert_standard_binary_summary_is_formatted(meta), expected_summary_sha256
    )
    if reopened_identity["raw_summary_sha256"] != variants[1]["raw_summary_sha256"]:
        raise SystemExit("Reopened packaged analysis changed result text.")
    if reopened_identity["svg_sha256"] != variants[1]["svg_sha256"]:
        raise SystemExit("Reopened packaged analysis changed SVG content.")
    return {
        "automation_entry_point": True,
        "converted_sample": Path(sample_path).name,
        "representative_edit": True,
        "real_r_analysis": True,
        "result_text": True,
        "expected_normalized_summary_sha256": expected_summary_sha256,
        "raw_summary_sha256": reopened_identity["raw_summary_sha256"],
        "normalized_summary_sha256": reopened_identity["normalized_summary_sha256"],
        "svg_sha256": reopened_identity["svg_sha256"],
        "locale_variants": [
            {key: value for key, value in variant.items() if key != "path"}
            for variant in variants
        ],
        "save_reopen": True,
        "analysis_after_reopen": True,
    }


def _expected_packaged_summary_sha256(sample_path):
    sample_name = Path(sample_path).name
    try:
        return PACKAGED_SUMMARY_SHA256_BY_SAMPLE[sample_name]
    except KeyError as exc:
        raise SystemExit("Unsupported packaged smoke sample: %s" % sample_name) from exc


def _packaged_result_identity(result, expected_summary_sha256):
    summary = result.get("texts", {}).get("Summary", "").replace("\r\n", "\n")
    raw_summary_sha256 = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    normalized_summary = normalize_packaged_summary_identity(summary)
    normalized_summary_sha256 = hashlib.sha256(
        normalized_summary.encode("utf-8")
    ).hexdigest()
    if normalized_summary_sha256 != expected_summary_sha256:
        raise SystemExit(
            "Packaged summary identity mismatch: %s != %s. Normalized summary: %r"
            % (
                normalized_summary_sha256,
                expected_summary_sha256,
                normalized_summary,
            )
        )
    display_images = result.get("display_images", {})
    svg_hashes = {}
    for label, raw_path in sorted(display_images.items()):
        path = Path(raw_path)
        if path.suffix.lower() != ".svg":
            continue
        payload = path.read_bytes() if path.is_file() else b""
        if b"<svg" not in payload[:4096].lower():
            raise SystemExit(
                "Packaged smoke analysis produced an invalid SVG: %s" % path
            )
        svg_hashes[label] = hashlib.sha256(payload).hexdigest()
    if not svg_hashes:
        raise SystemExit("Packaged smoke analysis produced no display SVG.")
    return {
        "raw_summary_sha256": raw_summary_sha256,
        "normalized_summary_sha256": normalized_summary_sha256,
        "svg_sha256": svg_hashes,
    }


def start_shell_smoke(require_native_window=False):
    """Exercise the maintained full shell without invoking analysis."""
    app, meta = start_automation()
    try:
        if require_native_window:
            platform_name = app.platformName().lower()
            expected = "windows" if sys.platform == "win32" else "cocoa"
            if platform_name != expected:
                raise SystemExit(
                    "Native shell smoke loaded Qt platform %s, expected %s."
                    % (platform_name, expected)
                )
        app.processEvents()
        if not meta.isVisible():
            raise SystemExit("Application shell did not become visible.")
        if meta.menuBar() is None or not meta.menuBar().actions():
            raise SystemExit("Application shell did not expose its menus.")
        print(
            "Application shell smoke passed with Qt platform %s."
            % app.platformName().lower()
        )
    finally:
        if meta.workspace.document is not None:
            meta.workspace.mark_saved()
        meta.close()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()
    if meta in app.topLevelWidgets():
        raise SystemExit("Application shell remained owned after close.")
    return 0


class _InjectedStartupFailure(RuntimeError):
    pass


def start_shell_failure_smoke(stage):
    """Prove startup failures release every newly owned top-level object."""
    if stage not in {"r-load", "meta-form"}:
        raise SystemExit("Unknown shell failure stage: %s" % stage)
    app = app_error_handler.get_or_create_application(sys.argv)
    _configure_application(app)
    baseline_ids = _top_level_ids(app)

    def r_loader(_app, _splash):
        if stage == "r-load":
            raise _InjectedStartupFailure(stage)

    def meta_factory():
        if stage == "meta-form":
            partial = QtWidgets.QMainWindow()
            partial.setWindowTitle("Injected partial shell")
            partial.show()
            app.processEvents()
            raise _InjectedStartupFailure(stage)
        return QtWidgets.QMainWindow()

    def main_window_loader():
        return type("MainWindowModule", (), {"MainWindow": meta_factory})

    try:
        _create_interactive_shell(app, main_window_loader, r_loader)
    except _InjectedStartupFailure:
        pass
    else:
        raise SystemExit("Injected startup failure did not fire: %s" % stage)

    leaked = [
        widget for widget in app.topLevelWidgets() if id(widget) not in baseline_ids
    ]
    if leaked:
        raise SystemExit(
            "Startup failure leaked top-level objects at %s: %s"
            % (stage, [type(widget).__name__ for widget in leaked])
        )
    print("Application shell failure teardown passed at %s." % stage)
    return 0


def start_adaptive_layout_evidence(output_dir, sample_path):
    """Run the packaged native adaptive-layout evidence workflow."""
    from scripts import adaptive_layout_evidence

    adaptive_layout_evidence.configure_isolated_evidence_settings(output_dir)
    app, meta = start_automation()
    adaptive_layout_evidence.run_native_adaptive_layout_evidence(
        app,
        meta,
        sample_path,
        output_dir,
    )
    return 0


def start_wizard_layout_smoke():
    app_error_handler.install_global_exception_handler()
    app = app_error_handler.get_or_create_application(sys.argv)
    app.setApplicationName(meta_globals.APPLICATION_NAME)
    app.setOrganizationName(meta_globals.ORGANIZATION_NAME)
    _set_application_icon(app)
    settings.setup_directories()

    from rc_metastudio import main_wizard

    parent_shell = QtWidgets.QMainWindow()
    # layout-audit: allow=verification-layout-fixture; reason=automation smoke fixture exercises a representative viewport
    parent_shell.resize(1600, 900)
    parent_shell.show()
    _flush_gui_events(app)

    scenarios = [
        ("startup welcome", main_wizard.MainWizard(), []),
        (
            "parented startup welcome",
            main_wizard.MainWizard(parent=parent_shell),
            [],
        ),
        (
            "new dataset",
            main_wizard.MainWizard(path="new_dataset"),
            [
                ("select", main_wizard.Page_DataType, "twoarm_proportions_Button"),
                ("next", main_wizard.Page_ChooseMetric, None),
                ("text", main_wizard.Page_OutcomeName, "Packaged Layout Smoke"),
            ],
        ),
        (
            "csv import",
            main_wizard.MainWizard(path="csv_import"),
            [
                ("select", main_wizard.Page_DataType, "twoarm_proportions_Button"),
                ("next", main_wizard.Page_ChooseMetric, None),
                ("text", main_wizard.Page_OutcomeName, "Packaged Layout Smoke"),
                ("next", main_wizard.Page_CsvImport, None),
            ],
        ),
    ]

    try:
        for scenario_name, wizard, actions in scenarios:
            stable_geometry = _show_wizard_for_layout_smoke(app, wizard, scenario_name)
            for action, expected_page_id, value in actions:
                _advance_wizard_layout_smoke_page(
                    app, wizard, action, expected_page_id, value
                )
                _assert_wizard_layout_smoke_page(
                    app, wizard, scenario_name, stable_geometry
                )
    finally:
        for _scenario_name, wizard, _actions in scenarios:
            wizard.close()
        parent_shell.close()
        app.processEvents()
    return 0


def _show_wizard_for_layout_smoke(app, wizard, scenario_name):
    wizard.restart()
    wizard.show()
    _flush_gui_events(app)
    _assert_wizard_layout_smoke_page(app, wizard, scenario_name)
    return _window_frame_tuple(wizard)


def _advance_wizard_layout_smoke_page(app, wizard, action, expected_page_id, value):
    if wizard.currentId() != expected_page_id:
        wizard.next()
        _flush_gui_events(app)
    if wizard.currentId() != expected_page_id:
        raise SystemExit(
            "Wizard layout smoke expected page %s but reached %s"
            % (expected_page_id, wizard.currentId())
        )

    page = wizard.currentPage()
    if action == "select":
        getattr(page, value).click()
    elif action == "text":
        page.outcome_name_LineEdit.setText(value)
    elif action != "next":
        raise SystemExit("Unknown wizard layout smoke action: %s" % action)
    _flush_gui_events(app)


def _assert_wizard_layout_smoke_page(
    app, wizard, scenario_name, expected_geometry=None
):
    _flush_gui_events(app)
    page = wizard.currentPage()
    if page is None:
        raise SystemExit("Wizard layout smoke has no current page: %s" % scenario_name)

    parent = page.parentWidget()
    if parent is None:
        raise SystemExit(
            "Wizard layout smoke page has no body parent: %s" % scenario_name
        )

    if page.layout() is not None:
        page.layout().activate()
    _flush_gui_events(app)

    body_rect = parent.contentsRect()
    if body_rect.width() <= 0 or body_rect.height() <= 0:
        raise SystemExit("Wizard layout smoke saw an empty body: %s" % scenario_name)
    if wizard.wizardStyle() != QtWidgets.QWizard.WizardStyle.ModernStyle:
        raise SystemExit("Wizard layout smoke expected ModernStyle: %s" % scenario_name)
    if (
        adaptive_window.adaptive_window_state(wizard).policy.archetype
        is not adaptive_window.WindowArchetype.WORKFLOW
    ):
        raise SystemExit(
            "Wizard layout smoke expected Workflow Window policy: %s" % scenario_name
        )
    overflow = page.findChild(QtWidgets.QScrollArea, "pageScrollArea")
    if overflow is None or not overflow.widgetResizable():
        raise SystemExit(
            "Wizard layout smoke expected a page Overflow Boundary: %s" % scenario_name
        )
    for button_role in (
        QtWidgets.QWizard.WizardButton.BackButton,
        QtWidgets.QWizard.WizardButton.NextButton,
        QtWidgets.QWizard.WizardButton.FinishButton,
        QtWidgets.QWizard.WizardButton.CancelButton,
    ):
        if overflow.isAncestorOf(wizard.button(button_role)):
            raise SystemExit(
                "Wizard navigation entered page overflow: %s" % scenario_name
            )
    if (
        expected_geometry is not None
        and _window_frame_tuple(wizard) != expected_geometry
    ):
        raise SystemExit(
            "Visible Workflow Window geometry changed between pages: %s" % scenario_name
        )
    if page.sizeHint().width() <= 0 or page.sizeHint().height() <= 0:
        raise SystemExit(
            "Wizard layout smoke saw an invalid page size hint: %s" % scenario_name
        )
    if page.width() <= 0 or page.height() <= 0:
        raise SystemExit("Wizard layout smoke saw an unsized page: %s" % scenario_name)

    _assert_visible_children_are_laid_out(page, scenario_name)
    pixmap = wizard.grab()
    image = pixmap.toImage()
    if pixmap.isNull() or image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise SystemExit("Wizard layout smoke could not render: %s" % scenario_name)


def _window_frame_tuple(window):
    geometry = window.frameGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()


def _assert_visible_children_are_laid_out(page, scenario_name):
    for child in page.findChildren(QtWidgets.QWidget):
        if child is page or child.isWindow() or not child.isVisible():
            continue
        object_name = child.objectName()
        if not object_name or object_name.startswith("qt_"):
            continue
        if child.width() <= 0 or child.height() <= 0:
            raise SystemExit(
                "Wizard child was not laid out in %s: %s"
                % (scenario_name, object_name or child.__class__.__name__)
            )


def _flush_gui_events(app):
    for _index in range(3):
        app.processEvents()


def start_startup_wizard_smoke(evidence_path, sample_path):
    """Exercise the real wizard-to-workspace transition in a packaged app."""
    qt6_resources.ensure_application_resources()
    app_error_handler.install_global_exception_handler()
    app = app_error_handler.get_or_create_application(list(sys.argv))
    _configure_application(app)
    baseline_ids = _top_level_ids(app)
    result = {"completed": False}

    try:
        settings.setup_directories()
        meta = _create_interactive_shell(app, _import_main_window, load_R_libraries)

        def complete_wizard():
            wizard = getattr(meta, "_startup_wizard", None)
            if wizard is None or not wizard.isVisible():
                raise SystemExit("Startup wizard did not become visible.")
            if not meta.open(sample_path):
                raise SystemExit(
                    "Startup wizard could not open project: %s" % sample_path
                )
            wizard.accept()

        def verify_workspace():
            handle = meta.windowHandle()
            geometry = meta.frameGeometry()
            model = meta.tableView.model()
            evidence = {
                "schema_version": 1,
                "platform_plugin": app.platformName().lower(),
                "project": Path(sample_path).name,
                "visible": meta.isVisible(),
                "active": meta.isActiveWindow(),
                "minimized": meta.isMinimized(),
                "maximized": meta.isMaximized(),
                "exposed": bool(handle and handle.isExposed()),
                "frame": [
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height(),
                ],
                "rows": model.rowCount() if model is not None else 0,
            }
            failures = []
            if not evidence["visible"]:
                failures.append("workspace is not visible")
            if evidence["minimized"]:
                failures.append("workspace is minimized")
            if not evidence["exposed"]:
                failures.append("native workspace is not exposed")
            if geometry.width() <= 0 or geometry.height() <= 0:
                failures.append("workspace has an empty native frame")
            if evidence["rows"] < 1:
                failures.append("opened project has no table rows")
            evidence["passed"] = not failures
            evidence["failures"] = failures
            Path(evidence_path).write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result["completed"] = True
            if meta.workspace.document is not None:
                meta.workspace.mark_saved()
            meta.close()
            app.exit(0 if not failures else 1)

        meta.start()
        QtCore.QTimer.singleShot(100, complete_wizard)
        QtCore.QTimer.singleShot(750, verify_workspace)
        QtCore.QTimer.singleShot(30_000, lambda: app.exit(124))
        exit_code = app.exec()
        if not result["completed"]:
            raise SystemExit(
                "Startup wizard smoke timed out before producing evidence."
            )
        return exit_code
    finally:
        _dispose_new_top_levels(app, baseline_ids)


def assert_opened_project_for_startup_smoke(
    app, meta, sample_path, opened, completion_marker=None
):
    try:
        if not opened:
            raise SystemExit("Could not open startup project: %s" % sample_path)
        app.processEvents()
        model = meta.tableView.model()
        if model is None or model.rowCount() < 1:
            raise SystemExit(
                "Startup project opened without table rows: %s" % sample_path
            )
        _force_table_paint(app, meta)
        _write_automation_smoke_log("startup-project:normal-entry-point-passed")
    finally:
        meta.close()
        app.processEvents()
    completion_marker = completion_marker or os.environ.get(
        "RCMS_STARTUP_COMPLETION_MARKER"
    )
    if completion_marker:
        Path(completion_marker).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pid": os.getpid(),
                    "platform_plugin": app.platformName().lower(),
                    "project": Path(sample_path).name,
                    "post_close": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _write_automation_smoke_log("startup-project:launchservices-completion-written")
    return 0


def _assert_standard_binary_summary_is_formatted(meta):
    from rc_metastudio import main_window

    captured = {}
    original_analysis = meta.analysis

    def capture_analysis(result):
        captured["result"] = result

    specs = main_window.analysis_setup_dialog.AnalysisSetupDialog(
        meta.model,
        parent=meta,
        confidence_level=meta.model.get_confidence_level(),
    )
    try:
        if specs.available_method_d is None:
            raise SystemExit("Packaged summary smoke test found no analysis methods.")
        if "binary.random" not in set(specs.available_method_d.values()):
            raise SystemExit(
                "Packaged summary smoke test could not find binary.random."
            )
        specs.current_method = "binary.random"
        specs.current_param_vals = {}
        specs.setup_params()
        specs.current_param_vals.update(specs.current_defaults)

        meta.analysis = capture_analysis
        specs.run_ma()
    finally:
        meta.analysis = original_analysis
        specs.close()

    result = captured.get("result")
    if not result:
        raise SystemExit(
            "Packaged summary smoke test did not produce analysis results."
        )
    summary = result.get("texts", {}).get("Summary", "")
    required = [
        "Binary Random-Effects Model",
        "Metric: Odds Ratio",
        "Model Results",
        "Estimate",
        "Lower bound (95% CI)",
        "Upper bound (95% CI)",
        "p-value",
        "Heterogeneity",
    ]
    missing = [text for text in required if text not in summary]
    if missing:
        raise SystemExit(
            "Packaged summary smoke test missing expected text: %s" % ", ".join(missing)
        )
    leaks = ["$model.title", "$arrays", 'attr(,"class")']
    leaked = [text for text in leaks if text in summary]
    if leaked:
        raise SystemExit(
            "Packaged summary smoke test saw raw R list output: %s" % ", ".join(leaked)
        )
    return result


def _force_table_paint(app, meta):
    """Renders every cell and both headers so paint-time data() bugs surface here."""
    view = meta.tableView
    # layout-audit: allow=verification-layout-fixture; reason=automation smoke fixture exercises a representative viewport
    view.resize(1400, 900)
    app.processEvents()
    model = view.model()
    for row in range(model.rowCount()):
        view.scrollTo(model.index(row, 0))
        app.processEvents()
        view.viewport().grab()
    view.horizontalHeader().grab()
    view.verticalHeader().grab()
    app.processEvents()
