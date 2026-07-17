"""Exercise analysis configuration and progress teardown on the native Qt platform."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ.setdefault("RCMS_STUB_BACKEND", "1")

from PyQt6 import QtCore, QtWidgets, sip

from rc_metastudio.qt6_ui import prepare_generated_ui_imports


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


def main() -> int:
    prepare_generated_ui_imports()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.append(str(repo_root / "src" / "rc_metastudio"))
    from rc_metastudio import meta_py_r_backend

    meta_py_r_backend.install_stub_meta_py_r()
    import app_error_handler
    import ma_specs

    backend = ma_specs.meta_py_r
    backend.ma_dataset_to_simple_binary_robj = lambda *args, **kwargs: None
    backend.get_available_methods = lambda **kwargs: {"Random": "binary.random"}
    setattr(backend, "get_params", lambda method: (
        {"conf.level": "float"},
        {"conf.level": 95.0},
        ["conf.level"],
        {},
    ))
    backend.get_method_description = lambda method: "Random-effects analysis"
    backend.get_analysis_plot_capabilities = lambda *args, **kwargs: []

    class Model:
        current_effect = "OR"
        dataset = SimpleNamespace(covariates=[])

        def get_current_outcome_type(self):
            return "binary"

        def included_studies_have_raw_data(self):
            return True

    class Owner(QtWidgets.QWidget):
        results = []

        def analysis(self, _result):
            self.results.append(_result)

    app = app_error_handler.get_or_create_application([])
    owner = Owner()
    baseline = len(app.topLevelWidgets())
    calls = []

    def run_backend(method, parameters):
        calls.append({"method": method, "parameters": dict(parameters)})
        return {"texts": {"Summary": "ok"}, "images": {}}

    backend.run_binary_ma = run_backend
    backend.reset_Rs_working_dir = lambda: None

    def deferred_delete():
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete
        )
        app.processEvents()

    def make_configuration():
        dialog = ma_specs.MA_Specs(Model(), parent=owner, conf_level=95.0)
        dialog.show()
        app.processEvents()
        return dialog

    configuration = make_configuration()
    confidence_input = configuration.parameter_grp_box.findChild(QtWidgets.QDoubleSpinBox)
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
    configuration.run_ma()
    progress = configuration.findChild(ma_specs.MetaProgress)
    if progress is None:
        raise RuntimeError("real analysis run did not create MetaProgress")
    deferred_delete()
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
    backend.run_binary_ma = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("native backend failure")
    )
    original_critical = ma_specs.QMessageBox.critical
    setattr(ma_specs.QMessageBox, "critical", lambda *_args, **_kwargs: None)
    try:
        failing.run_ma()
    finally:
        setattr(ma_specs.QMessageBox, "critical", original_critical)
    failing_progress = failing.findChild(ma_specs.MetaProgress)
    if failing_progress is None:
        raise RuntimeError("failed analysis did not create MetaProgress")
    deferred_delete()
    scenarios["backend_failure"] = {
        "deleted": {
            "configuration": sip.isdeleted(failing),
            "progress": sip.isdeleted(failing_progress),
        },
        "top_level_delta": len(app.topLevelWidgets()) - baseline,
    }

    cancelled = make_configuration()
    cancelled.reject()
    deferred_delete()
    scenarios["cancel"] = {
        "deleted": {"configuration": sip.isdeleted(cancelled)},
        "top_level_delta": len(app.topLevelWidgets()) - baseline,
    }

    closed = make_configuration()
    closed.close()
    deferred_delete()
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
    print(evidence_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
