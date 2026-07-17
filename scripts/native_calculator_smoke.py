"""Exercise calculator transactions through the visible native workspace action."""

from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import sys

os.environ.setdefault("RCMS_STUB_BACKEND", "1")

from PyQt6 import QtCore, QtGui, QtWidgets

from rc_metastudio.qt6_resources import ensure_application_resources
from rc_metastudio.qt6_ui import prepare_generated_ui_imports
from rc_metastudio.runtime_types import required


def _write_evidence(path: Path, evidence: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_visible_calculator(
    dialog: QtWidgets.QDialog,
) -> tuple[QtGui.QPixmap | QtGui.QImage, str]:
    """Capture a visible calculator even when hosted screen capture is unavailable."""
    screen = required(dialog.screen(), "calculator screen")
    pixmap = screen.grabWindow(dialog.winId())
    if not pixmap.isNull():
        return pixmap, "QScreen.grabWindow"
    pixmap = dialog.grab()
    if not pixmap.isNull():
        return pixmap, "QWidget.grab fallback"

    ratio = max(1.0, dialog.devicePixelRatioF())
    image = QtGui.QImage(
        max(1, math.ceil(dialog.width() * ratio)),
        max(1, math.ceil(dialog.height() * ratio)),
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.setDevicePixelRatio(ratio)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    if not painter.isActive():
        raise RuntimeError("failed to allocate software calculator capture")
    try:
        dialog.render(painter)
    finally:
        painter.end()
    return image, "QWidget.render(QImage) fallback"


def close_automation_window(
    app: QtWidgets.QApplication, window: QtWidgets.QWidget
) -> None:
    """Close without triggering last-window quit or pumping teardown events."""
    previous_auto_quit = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    try:
        setattr(window, "current_data_unsaved", False)
        window.close()
    finally:
        app.setQuitOnLastWindowClosed(previous_auto_quit)


def validate_evidence_bundle(evidence_root: Path) -> list[dict[str, object]]:
    """Validate a native calculator evidence bundle after download or relocation."""
    evidence_root = evidence_root.resolve()
    manifest_path = evidence_root / "evidence.json"
    evidence = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, list):
        raise ValueError("native calculator evidence must be a JSON array")

    calculator_records = [record for record in evidence if "calculator" in record]
    if {record.get("calculator") for record in calculator_records} != {
        "binary",
        "continuous",
        "diagnostic",
    }:
        raise ValueError("native calculator evidence must cover all calculators")

    for record in calculator_records:
        if record.get("capture_method") not in {
            "QScreen.grabWindow",
            "QWidget.grab fallback",
            "QWidget.render(QImage) fallback",
        }:
            raise ValueError("calculator capture method is invalid")
        relative_text = record.get("image")
        if not isinstance(relative_text, str) or not relative_text:
            raise ValueError("calculator image path must be a non-empty string")
        if "\\" in relative_text:
            raise ValueError("calculator image path must use canonical POSIX separators")
        relative = PurePosixPath(relative_text)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "." in relative.parts
            or str(relative) != relative_text
        ):
            raise ValueError("calculator image path must be relative and canonical")
        image_path = (evidence_root / Path(*relative.parts)).resolve()
        if not image_path.is_relative_to(evidence_root):
            raise ValueError("calculator image path escapes the evidence root")
        if not image_path.is_file():
            raise ValueError("calculator image is missing: %s" % relative_text)
        with image_path.open("rb") as image_handle:
            if image_handle.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("calculator image is not a PNG: %s" % relative_text)
        expected_size = record.get("image_size")
        if not isinstance(expected_size, int) or expected_size <= 0:
            raise ValueError("calculator image size must be a positive integer")
        if image_path.stat().st_size != expected_size:
            raise ValueError("calculator image size does not match: %s" % relative_text)
        expected_hash = record.get("image_sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError("calculator image SHA256 is invalid")
        if _sha256(image_path) != expected_hash:
            raise ValueError("calculator image SHA256 does not match: %s" % relative_text)
    return evidence


def main() -> int:
    prepare_generated_ui_imports()
    ensure_application_resources()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.append(str(repo_root / "src" / "rc_metastudio"))

    import binary_data_form
    import continuous_data_form
    import diagnostic_data_form
    import launch
    import ma_data_table_model

    binary_data_form.meta_py_r.get_mult_from_r = lambda _level: 1.96
    setattr(binary_data_form.meta_py_r, "binary_convert_scale", lambda value, *args, **kwargs: value)
    binary_data_form.meta_py_r.impute_bin_data = lambda _data: {"FAIL": True}
    binary_data_form.meta_py_r.effect_for_study = lambda *args, **kwargs: {
        "calc_scale": (1.2, 0.8, 1.8)
    }
    setattr(binary_data_form.meta_py_r, "effect_triplet", lambda result, scale, metric=None: result[scale])
    setattr(continuous_data_form.meta_py_r, "continuous_convert_scale", lambda value, *args, **kwargs: value)
    continuous_data_form.meta_py_r.impute_cont_data = (
        lambda _data, _alpha: {"succeeded": False, "comment": "complete input"}
    )
    continuous_data_form.meta_py_r.continuous_effect_for_study = (
        lambda *args, **kwargs: {"calc_scale": (1.5, 1.0, 2.0)}
    )
    setattr(continuous_data_form.meta_py_r, "effect_triplet", lambda result, scale, metric=None: result[scale])
    continuous_data_form.meta_py_r.back_calc_cont_data = (
        lambda *args, **kwargs: {"FAIL": True}
    )
    setattr(diagnostic_data_form.meta_py_r, "diagnostic_convert_scale", lambda value, *args, **kwargs: value)
    diagnostic_data_form.meta_py_r.impute_diag_data = lambda _data: {
        "TP": None,
        "FP": None,
        "FN": None,
        "TN": None,
    }
    diagnostic_data_form.meta_py_r.diagnostic_effects_for_study = (
        lambda *args, metrics, **kwargs: {
            metric: {"calc_scale": (0.8, 0.7, 0.9)} for metric in metrics
        }
    )
    setattr(diagnostic_data_form.meta_py_r, "effect_triplet", lambda result, scale, metric=None: result[scale])
    setattr(diagnostic_data_form.QMessageBox, "warning", lambda *args, **kwargs: None)
    setattr(ma_data_table_model.meta_py_r, "binary_convert_scale", lambda value, *args, **kwargs: value)
    setattr(ma_data_table_model.meta_py_r, "continuous_convert_scale", lambda value, *args, **kwargs: value)
    setattr(ma_data_table_model.meta_py_r, "diagnostic_convert_scale", lambda value, *args, **kwargs: value)

    evidence_root = repo_root / "build/qt6-verification/native-calculators"
    evidence_path = evidence_root / "evidence.json"
    evidence: list[dict[str, object]] = []
    app, window = launch.start_automation()
    cases = (
        ("binary", "proportions", "OR", binary_data_form.BinaryDataForm2),
        ("continuous", "means", "MD", continuous_data_form.ContinuousDataForm),
        ("diagnostic", None, "Sens", diagnostic_data_form.DiagnosticDataForm),
    )
    try:
        window.show()
        app.processEvents()
        for data_type, sub_type, effect, expected_type in cases:
            window._handle_wizard_results(
                {
                    "path": "new_dataset",
                    "outcome_info": {
                        "arms": "two",
                        "data_type": data_type,
                        "sub_type": sub_type,
                        "effect": effect,
                        "metric_choices": [],
                        "name": "%s native smoke" % data_type.title(),
                    },
                    "csv_data": None,
                    "selected_dataset": None,
                }
            )
            model = window.model
            table_view = window.tableView
            unit = model.get_current_ma_unit_for_study(0)
            if data_type == "binary":
                unit.get_raw_data_for_group(model.current_txs[0])[:] = [6, 20]
                unit.get_raw_data_for_group(model.current_txs[1])[:] = [8, 22]
            elif data_type == "continuous":
                unit.get_raw_data_for_group(model.current_txs[0])[:] = [10, 94, 2]
                unit.get_raw_data_for_group(model.current_txs[1])[:] = [12, 90, 3]
            else:
                unit.get_raw_data_for_group(model.current_txs[0])[:] = [12, 3, 4, 21]
            before = list(unit.get_raw_data_for_group(model.current_txs[0]))
            table_view.undoStack.clear()
            table_view.undoStack.setClean()
            window.current_data_unsaved = False
            captured: list[dict[str, object]] = []
            callback_errors: list[BaseException] = []

            def exercise_and_close() -> None:
                try:
                    dialog = next(
                        widget
                        for widget in QtWidgets.QApplication.topLevelWidgets()
                        if isinstance(widget, expected_type) and widget.isVisible()
                    )
                    app.processEvents()
                    ok = dialog.buttonBox.button(
                        QtWidgets.QDialogButtonBox.StandardButton.Ok
                    )
                    if not required(ok, "calculator OK button").isDefault():
                        raise RuntimeError("OK is not the default calculator action")
                    if data_type == "binary":
                        if not isinstance(dialog, binary_data_form.BinaryDataForm2):
                            raise RuntimeError("binary calculator opened the wrong dialog")
                        expected_focus = dialog.raw_data_table
                    elif data_type == "continuous":
                        if not isinstance(dialog, continuous_data_form.ContinuousDataForm):
                            raise RuntimeError("continuous calculator opened the wrong dialog")
                        expected_focus = dialog.simple_table
                    else:
                        if not isinstance(dialog, diagnostic_data_form.DiagnosticDataForm):
                            raise RuntimeError("diagnostic calculator opened the wrong dialog")
                        expected_focus = dialog.two_by_two_table
                    if dialog.focusWidget() is not expected_focus:
                        raise RuntimeError("calculator did not assign initial table focus")

                    if data_type == "binary":
                        assert isinstance(dialog, binary_data_form.BinaryDataForm2)
                        dialog.raw_data_table.setCurrentCell(0, 0)
                        required(dialog.raw_data_table.item(0, 0), "binary smoke cell").setText("7")
                        action = "valid edit and accept"
                        expected_result = "accepted"
                    elif data_type == "continuous":
                        assert isinstance(dialog, continuous_data_form.ContinuousDataForm)
                        dialog.simple_table.setCurrentCell(0, 1)
                        required(dialog.simple_table.item(0, 1), "continuous smoke cell").setText("95,5")
                        action = "comma-decimal edit and accept"
                        expected_result = "accepted"
                    else:
                        assert isinstance(dialog, diagnostic_data_form.DiagnosticDataForm)
                        dialog.two_by_two_table.setCurrentCell(0, 0)
                        required(dialog.two_by_two_table.item(0, 0), "diagnostic smoke cell").setText("13,5")
                        if required(dialog.two_by_two_table.item(0, 0), "diagnostic smoke cell").text() != "12":
                            raise RuntimeError("invalid diagnostic count did not roll back")
                        action = "invalid edit and cancel rollback"
                        expected_result = "rejected"
                    app.processEvents()

                    image_path = evidence_root / (data_type + ".png")
                    pixmap, capture_method = capture_visible_calculator(dialog)
                    if pixmap.isNull() or not pixmap.save(str(image_path), "PNG"):
                        raise RuntimeError(
                            "failed to capture visible %s calculator" % data_type
                        )
                    if image_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                        raise RuntimeError(
                            "calculator capture is not an intact PNG: %s" % data_type
                        )
                    captured.append(
                        {
                            "action": action,
                            "calculator": data_type,
                            "capture_method": capture_method,
                            "default_accept": True,
                            "dialog": expected_type.__name__,
                            "expected_result": expected_result,
                            "height": dialog.frameGeometry().height(),
                            "image": image_path.relative_to(evidence_root).as_posix(),
                            "image_sha256": _sha256(image_path),
                            "image_size": image_path.stat().st_size,
                            "initial_focus": expected_focus.objectName(),
                            "qpa": app.platformName(),
                            "visible": dialog.isVisible(),
                            "width": dialog.frameGeometry().width(),
                        }
                    )
                    if data_type == "diagnostic":
                        dialog.reject()
                    else:
                        dialog.accept()
                except BaseException as error:
                    callback_errors.append(error)
                    for widget in QtWidgets.QApplication.topLevelWidgets():
                        if isinstance(widget, QtWidgets.QDialog) and widget.isVisible():
                            widget.reject()

            QtCore.QTimer.singleShot(150, exercise_and_close)
            table_view.row_header_clicked(0)
            if callback_errors:
                raise callback_errors[0]
            if not captured:
                raise RuntimeError("native %s calculator was not exercised" % data_type)

            after = model.get_current_ma_unit_for_study(0).get_raw_data_for_group(
                model.current_txs[0]
            )
            if data_type == "binary" and after != [7, 21]:
                raise RuntimeError("binary accepted edit did not reach the model")
            if data_type == "continuous" and after != [10.0, 95.5, 2.0]:
                raise RuntimeError("continuous accepted edit did not reach the model")
            if data_type == "diagnostic" and after != before:
                raise RuntimeError("diagnostic cancel mutated the model")
            accepted = data_type != "diagnostic"
            if table_view.undoStack.count() != int(accepted):
                raise RuntimeError("calculator transaction created the wrong undo state")
            if window.current_data_unsaved is not accepted:
                raise RuntimeError("calculator transaction created the wrong dirty state")
            captured[0]["model_after"] = list(after)
            captured[0]["model_nonmutation"] = not accepted
            captured[0]["undo_commands"] = table_view.undoStack.count()
            evidence.extend(captured)
    except BaseException as error:
        evidence.append(
            {
                "error": "%s: %s" % (type(error).__name__, error),
                "qpa": app.platformName(),
            }
        )
        raise
    finally:
        _write_evidence(evidence_path, evidence)
        close_automation_window(app, window)

    validate_evidence_bundle(evidence_root)
    print(evidence_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--validate-only"]:
        root = Path(__file__).resolve().parents[1]
        validate_evidence_bundle(root / "build/qt6-verification/native-calculators")
        raise SystemExit(0)
    raise SystemExit(main())
