"""Exercise analysis configuration and progress teardown on the native Qt platform."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from PyQt6 import QtCore, QtWidgets, sip

from rc_metastudio.qt6_ui import prepare_generated_ui_imports


def _phase(name: str) -> None:
    print(f"RCMS_NATIVE_ANALYSIS_PHASE {name}", flush=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_evidence(path: Path) -> dict[str, object]:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence.get("qpa") != "windows":
        raise ValueError("native analysis evidence was not captured with qwindows")
    if evidence.get("request") != {
        "data_type": "binary",
        "method": "binary.random",
        "metric": "OR",
        "workflow": "standard",
    }:
        raise ValueError("native analysis evidence has the wrong typed request")
    if evidence.get("confidence_level") != 90.5:
        raise ValueError("native analysis evidence has the wrong confidence level")
    scenarios = evidence.get("scenarios", {})
    if set(scenarios) != {"success", "backend_failure", "cancel", "close"}:
        raise ValueError("native analysis evidence is missing lifecycle scenarios")
    for name, scenario in scenarios.items():
        expected = {"configuration": True}
        if name in {"success", "backend_failure"}:
            expected["progress"] = True
        if scenario.get("deleted") != expected:
            raise ValueError("native %s surfaces did not complete teardown" % name)
        if scenario.get("top_level_delta") != 0:
            raise ValueError("native %s leaked a top-level widget" % name)
    image = path.parent / "analysis-configuration.png"
    if not image.is_file() or image.stat().st_size != evidence.get("image_size"):
        raise ValueError("native analysis screenshot is missing or has the wrong size")
    if _sha256(image) != evidence.get("image_sha256"):
        raise ValueError("native analysis screenshot hash does not match")
    return evidence


def _install_backend_test_double(
    backend: object, name: str, implementation: Callable[..., object]
) -> None:
    """Patch one explicitly selected R bridge operation for this smoke test."""
    setattr(backend, name, implementation)


def main() -> int:
    prepare_generated_ui_imports()
    repo_root = Path(__file__).resolve().parents[1]
    from rc_metastudio import r_backend, r_bridge

    backend_fake = r_backend.make_test_backend()
    for name in dir(backend_fake):
        if not name.startswith("_"):
            setattr(r_bridge, name, getattr(backend_fake, name))
    _phase("backend-installed")
    from rc_metastudio import app_error_handler, analysis_setup_dialog, progress_dialog

    progress_class = progress_dialog.AnalysisProgressDialog
    created_progress_dialogs = []

    def create_progress_dialog(*args: object, **kwargs: object) -> object:
        progress = progress_class(*args, **kwargs)
        created_progress_dialogs.append(progress)
        return progress

    setattr(
        analysis_setup_dialog.progress_dialog,
        "AnalysisProgressDialog",
        create_progress_dialog,
    )

    backend = analysis_setup_dialog.r_bridge

    _install_backend_test_double(
        backend,
        "dataset_to_simple_binary_r_object",
        lambda *_args, **_kwargs: None,
    )
    _install_backend_test_double(
        backend,
        "get_available_methods",
        lambda **_kwargs: {"Random": "binary.random"},
    )
    setattr(
        backend,
        "get_params",
        lambda method: (
            {"conf.level": "float"},
            {"conf.level": 95.0},
            ["conf.level"],
            {},
        ),
    )
    _install_backend_test_double(
        backend, "get_method_description", lambda _method: "Random-effects analysis"
    )
    _install_backend_test_double(
        backend, "get_analysis_plot_capabilities", lambda *_args, **_kwargs: []
    )

    class Model:
        current_effect = "OR"
        dataset = SimpleNamespace(covariates=[])

        def get_current_outcome_type(self) -> str:
            return "binary"

        def included_studies_have_raw_data(self) -> bool:
            return True

    class Owner(QtWidgets.QWidget):
        results = []

        def analysis(self, _result: object) -> None:
            self.results.append(_result)

    app = app_error_handler.get_or_create_application([])
    owner = Owner()
    baseline = len(app.topLevelWidgets())
    calls = []

    def run_backend(method: str, parameters: dict[str, object]) -> dict[str, object]:
        calls.append({"method": method, "parameters": dict(parameters)})
        return {"texts": {"Summary": "ok"}, "images": {}}

    _install_backend_test_double(backend, "run_binary_analysis", run_backend)
    _install_backend_test_double(backend, "reset_r_working_directory", lambda: None)

    def deferred_delete() -> None:
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete
        )
        app.processEvents()

    def make_configuration() -> Any:
        dialog = analysis_setup_dialog.AnalysisSetupDialog(
            Model(), parent=owner, confidence_level=95.0
        )
        dialog.show()
        app.processEvents()
        return dialog

    configuration = make_configuration()
    _phase("success-configuration-created")
    confidence_input = configuration.parameter_grp_box.findChild(
        QtWidgets.QDoubleSpinBox
    )
    if confidence_input is None:
        raise RuntimeError("confidence-level input is missing")
    confidence_input.setLocale(QtCore.QLocale(QtCore.QLocale.Language.German))
    confidence_input.lineEdit().setText("90,5")
    confidence_input.interpretText()
    request = configuration.analysis_requests()[0]

    evidence_root = repo_root / "build/qt6-verification/native-analysis"
    evidence_root.mkdir(parents=True, exist_ok=True)
    image = evidence_root / "analysis-configuration.png"
    screen = configuration.screen()
    if screen is None:
        raise RuntimeError("analysis configuration is not attached to a screen")
    pixmap = screen.grabWindow(configuration.winId())
    if pixmap.isNull() or not pixmap.save(str(image), "PNG"):
        raise RuntimeError("failed to capture native analysis configuration")

    _phase("success-run-entry")
    original_critical = analysis_setup_dialog.QMessageBox.critical

    def fail_on_unexpected_critical(
        _parent: object, title: str, message: str, *_args: object, **_kwargs: object
    ) -> None:
        raise RuntimeError(f"unexpected {title} dialog: {message}")

    setattr(
        analysis_setup_dialog.QMessageBox,
        "critical",
        fail_on_unexpected_critical,
    )
    try:
        configuration.run_ma()
    finally:
        setattr(
            analysis_setup_dialog.QMessageBox,
            "critical",
            original_critical,
        )
    _phase("success-run-return")
    if not created_progress_dialogs:
        raise RuntimeError("real analysis run did not create AnalysisProgressDialog")
    progress = created_progress_dialogs[-1]
    _phase("success-progress-found")
    deferred_delete()
    _phase("success-deferred-delete-return")
    scenarios = {
        "success": {
            "deleted": {
                "configuration": sip.isdeleted(configuration),
                "progress": sip.isdeleted(progress),
            },
            "top_level_delta": len(app.topLevelWidgets()) - baseline,
        }
    }

    failing = make_configuration()
    _phase("failure-configuration-created")
    progress_count = len(created_progress_dialogs)
    backend.run_binary_analysis = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("native backend failure")
    )
    original_critical = analysis_setup_dialog.QMessageBox.critical
    setattr(
        analysis_setup_dialog.QMessageBox, "critical", lambda *_args, **_kwargs: None
    )
    try:
        _phase("failure-run-entry")
        failing.run_ma()
        _phase("failure-run-return")
    finally:
        setattr(analysis_setup_dialog.QMessageBox, "critical", original_critical)
    if len(created_progress_dialogs) != progress_count + 1:
        raise RuntimeError("failed analysis did not create AnalysisProgressDialog")
    failing_progress = created_progress_dialogs[-1]
    _phase("failure-progress-found")
    deferred_delete()
    _phase("failure-deferred-delete-return")
    scenarios["backend_failure"] = {
        "deleted": {
            "configuration": sip.isdeleted(failing),
            "progress": sip.isdeleted(failing_progress),
        },
        "top_level_delta": len(app.topLevelWidgets()) - baseline,
    }

    cancelled = make_configuration()
    _phase("cancel-configuration-created")
    cancelled.reject()
    deferred_delete()
    _phase("cancel-deferred-delete-return")
    scenarios["cancel"] = {
        "deleted": {"configuration": sip.isdeleted(cancelled)},
        "top_level_delta": len(app.topLevelWidgets()) - baseline,
    }

    closed = make_configuration()
    _phase("close-configuration-created")
    closed.close()
    deferred_delete()
    _phase("close-deferred-delete-return")
    scenarios["close"] = {
        "deleted": {"configuration": sip.isdeleted(closed)},
        "top_level_delta": len(app.topLevelWidgets()) - baseline,
    }
    evidence = {
        "confidence_level": request.parameter_values()["conf.level"],
        "image_sha256": _sha256(image),
        "image_size": image.stat().st_size,
        "qpa": app.platformName(),
        "request": {
            "data_type": request.data_type,
            "method": request.method,
            "metric": request.metric,
            "workflow": request.workflow,
        },
        "backend_calls": calls,
        "scenarios": scenarios,
    }
    evidence_path = evidence_root / "evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_evidence(evidence_path)
    _phase("evidence-validated")
    print(evidence_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
