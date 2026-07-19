import importlib.util
import builtins
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "capture_pre_qt6_baseline.py"
BASELINE_DIR = ROOT / "docs" / "verification" / "pre-qt6-baseline"


def _load_script():
    spec = importlib.util.spec_from_file_location("capture_pre_qt6_baseline", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_sample_semantic_snapshots_cover_every_committed_project():
    sample_names = sorted(
        path.name for path in (ROOT / "sample_projects").glob("*.rcms")
    )

    snapshots = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((BASELINE_DIR / "sample-projects").glob("*.json"))
    }

    assert sorted(snapshots) == sample_names
    for name, snapshot in snapshots.items():
        assert snapshot["project_file"] == f"sample_projects/{name}"
        assert snapshot["source_sha256"]
        assert snapshot["dataset"]["studies"]
        assert snapshot["dataset"]["outcomes"]
        assert snapshot["dataset"]["analysis_family"] in {
            "binary",
            "continuous",
            "diagnostic",
        }


def test_qt_port_inventory_classifies_required_surfaces_and_completion_rules():
    module = _load_script()

    inventory = module.build_qt_port_inventory(ROOT)

    assert inventory["schema_version"] == 1
    assert len(inventory["canonical_forms"]) == 29
    assert "src/rc_metastudio/images/icons.qrc" in inventory["resources"]
    assert "src/rc_metastudio/forms/icons_rc.py" in inventory["generated_modules"]
    assert (
        "packaging/pyinstaller/rc-metastudio.spec"
        in inventory["packaging_entry_points"]
    )
    for entry_point in (
        "scripts/package-macos.sh",
        "scripts/resolve_package_ci_metadata.py",
        "scripts/verify_package_release.py",
    ):
        assert entry_point in inventory["packaging_entry_points"]
    for category in (
        "handwritten_qt_modules",
        "qt_bearing_tests",
        "short_enums",
        "signals",
        "removed_or_displaced_apis",
    ):
        assert inventory[category], category

    assert inventory["dynamic_properties"]["application_owned"]
    assert inventory["dynamic_properties"]["allowed_qt_designer"]
    assert all(
        item["property_name"].startswith("RCMS_")
        or item["property_name"].startswith("plotText")
        for item in inventory["dynamic_properties"]["application_owned"]
    )

    rules = {rule["id"]: rule for rule in inventory["zero_legacy_completion_checks"]}
    assert rules["no-pyqt5-imports"]["target"] == 0
    assert rules["no-tracked-generated-qt-python"]["target"] == 0
    assert rules["no-pickle-project-storage"]["target"] == 0


def test_removed_api_detector_accepts_native_pyqt6_locations_and_rejects_legacy_ones():
    module = _load_script()
    native = """
from PyQt6.QtGui import QAction
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6 import QtGui, QtSvgWidgets
import PyQt6.QtGui

action = QAction()
other = QtGui.QAction()
fully_qualified = PyQt6.QtGui.QAction()
item = QGraphicsSvgItem()
other_item = QtSvgWidgets.QGraphicsSvgItem()
dialog.exec()
"""
    legacy = """
from PyQt5.QtWidgets import QAction, QDesktopWidget
from PyQt5.QtSvg import QGraphicsSvgItem
from PyQt5 import QtCore, QtWidgets, QtSvg
import PyQt5.QtWidgets

rx = QtCore.QRegExp('x')
action = QtWidgets.QAction()
fully_qualified = PyQt5.QtWidgets.QAction()
item = QtSvg.QGraphicsSvgItem()
dialog.exec_()
"""

    assert module.detect_removed_or_displaced_apis("native.py", native) == []
    findings = module.detect_removed_or_displaced_apis("legacy.py", legacy)
    assert {item["symbol"] for item in findings} == {
        "QAction",
        "QDesktopWidget",
        "QGraphicsSvgItem",
        "QRegExp",
        "exec_",
    }


def test_dependency_detector_blocks_qt5_and_alternate_bindings_but_allows_pyqt6():
    module = _load_script()

    native = module.detect_legacy_dependency_declarations(
        {
            "pyproject.toml": 'dependencies = ["PyQt6==6.11.0"]',
            "uv.lock": 'name = "pyqt6-qt6"\nversion = "6.11.0"',
        }
    )
    legacy = module.detect_legacy_dependency_declarations(
        {
            "pyproject.toml": 'dependencies = ["PyQt5", "qtpy", "PySide6"]',
            "uv.lock": 'name = "PyQt5-Qt5"\nname = "PyQt5-sip"',
        }
    )

    assert native == {"pyqt5": [], "compatibility": []}
    assert len(legacy["pyqt5"]) == 3
    assert len(legacy["compatibility"]) == 1


def test_native_pyqt6_fixture_reaches_all_zero_legacy_targets(tmp_path):
    module = _load_script()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "native"\nversion = "1"\ndependencies = ["PyQt6==6.11.0"]\n',
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "pyqt6-qt6"\nversion = "6.11.0"\n',
        encoding="utf-8",
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.py").write_text(
        "from PyQt6.QtGui import QAction\n"
        "from PyQt6.QtSvgWidgets import QGraphicsSvgItem\n"
        "action = QAction()\nitem = QGraphicsSvgItem()\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)

    report = module.run_zero_legacy_detectors(tmp_path)

    assert report["passed"] is True
    assert all(check["current_count"] == 0 for check in report["checks"])


def test_all_zero_legacy_checks_have_executable_detectors():
    module = _load_script()

    report = module.run_zero_legacy_detectors(ROOT)

    assert len(report["checks"]) == 8
    assert all(check["target"] == 0 for check in report["checks"])
    assert all(type(check["current_count"]) is int for check in report["checks"])
    assert all(check["detector"] for check in report["checks"])
    assert report["passed"] is all(
        check["current_count"] == 0 for check in report["checks"]
    )


def test_zero_legacy_report_cli_writes_machine_readable_report(tmp_path):
    report_path = tmp_path / "zero-legacy.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--legacy-report", str(report_path)],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["checks"]) == 8


def test_one_time_capture_refuses_post_baseline_input_drift(monkeypatch, tmp_path):
    module = _load_script()
    monkeypatch.setattr(
        module,
        "baseline_input_drift",
        lambda _root: ["src/rc_metastudio/launch.py"],
    )

    with pytest.raises(module.BaselineDriftError, match="launch.py"):
        module.write_baseline(ROOT, output_dir=tmp_path)


def test_checked_in_baseline_evidence_is_reproducible():
    module = _load_script()

    assert module.validate_checked_in_baseline(ROOT) == []


def test_forward_validation_does_not_import_pyqt5_or_execute_pickle(monkeypatch):
    module = _load_script()
    real_import = builtins.__import__

    def reject_legacy_import(name, *args, **kwargs):
        if name.startswith("PyQt5") or name in {"pickle", "project_pickle"}:
            raise AssertionError(f"forward validation imported {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_legacy_import)

    assert module.validate_checked_in_baseline(ROOT) == []


def test_baseline_retains_actual_golden_outputs_and_rendered_interface_payloads(
    tmp_path,
):
    manifest = json.loads((BASELINE_DIR / "manifest.json").read_text(encoding="utf-8"))

    module = _load_script()
    errors, golden = module.inspect_observed_golden_bundle(
        BASELINE_DIR / "observed-golden-baseline.zip"
    )
    assert errors == []
    assert golden["source_commit"] == manifest["source_commit"]
    assert golden["passed"] is True
    assert len(golden["outputs"]) == 11
    assert all(
        output["numeric_sections"] or output["text_sections"]
        for output in golden["outputs"]
    )
    assert all(output["artifacts"] for output in golden["outputs"])

    tampered_bundle = tmp_path / "local-debug-golden-baseline.zip"
    source_bundle = BASELINE_DIR / "observed-golden-baseline.zip"
    with (
        zipfile.ZipFile(source_bundle) as source,
        zipfile.ZipFile(
            tampered_bundle, "w", compression=zipfile.ZIP_DEFLATED
        ) as target,
    ):
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "manifest.json":
                tampered_manifest = json.loads(payload)
                tampered_manifest["curated_golden_set"][0].update(
                    authority="local-debug",
                    authoritative=False,
                    capture_mode="local-debug",
                )
                payload = json.dumps(tampered_manifest).encode("utf-8")
            target.writestr(info, payload)

    tamper_errors, _summary = module.inspect_observed_golden_bundle(tampered_bundle)
    assert any("not authoritative" in error for error in tamper_errors)

    rendered = manifest["rendered_interface_evidence"]
    assert {item["surface"] for item in rendered} == {
        "startup-welcome",
        "new-dataset-data-type",
    }
    for item in rendered:
        payload = ROOT / item["path"]
        assert payload.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_baseline_is_explicitly_diagnostic_and_not_a_forward_ci_target():
    manifest = json.loads((BASELINE_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["support_policy"] == {
        "diagnostic_only": True,
        "forward_ci": False,
        "packaged": False,
        "supported_runtime": False,
    }
    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )
    assert manifest["tag"] not in workflows
