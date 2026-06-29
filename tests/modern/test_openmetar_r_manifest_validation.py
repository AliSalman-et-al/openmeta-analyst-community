import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_openmetar_r_manifests.py"
DEPENDENCY_MANIFEST = Path("docs") / "modernization" / "openmetar-r-dependencies.json"
DRIFT_MANIFEST = Path("docs") / "modernization" / "openmetar-statistical-drift.json"


def copy_modernization_docs(tmp_path):
    docs_root = tmp_path / "docs" / "modernization"
    shutil.copytree(REPO_ROOT / "docs" / "modernization", docs_root)
    return tmp_path


def run_validator(root, *args):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_openmetar_r_manifests_validate():
    result = run_validator(REPO_ROOT)

    assert result.returncode == 0, result.stderr
    assert "validated OpenMetaR R dependency and drift manifests" in result.stdout


def test_direct_and_app_bundle_dependencies_must_stay_separate(tmp_path):
    root = copy_modernization_docs(tmp_path)
    manifest_path = root / DEPENDENCY_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["app_r_bundle_dependencies"].append(
        {
            "name": "metafor",
            "source": "cran",
            "reason": "invalid duplicate across manifest sections",
            "evidence": ["test"],
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "dependencies must be separated" in result.stderr
    assert "metafor" in result.stderr


def test_drift_manifest_preserves_review_record_schema(tmp_path):
    root = copy_modernization_docs(tmp_path)
    manifest_path = root / DRIFT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reviewed_drift_required_fields"].remove("independent_validation_signal")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "reviewed_drift_required_fields missing independent_validation_signal" in result.stderr


def test_manifest_records_empty_direct_test_dependency_scope(tmp_path):
    root = copy_modernization_docs(tmp_path)
    manifest_path = root / DEPENDENCY_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["empty_scope_rationale"]["test"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "empty_scope_rationale.test" in result.stderr


def test_installed_version_report_parses_rscript_output(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_openmetar_r_manifests", VALIDATOR)
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)

    def fake_run(command, text, stdout, stderr, check):
        assert command[:2] == ["Rscript", "-e"]
        assert command[3:] == ["R", "metafor", "HSROC"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="R\t4.6.0\nR\t4.6.0\nmetafor\t4.9-17\nHSROC\tNA\n",
            stderr="",
        )

    monkeypatch.setattr(validator.subprocess, "run", fake_run)

    report = validator.report_installed_versions("Rscript", ["R", "metafor", "HSROC"])

    assert report == {
        "r_version": "4.6.0",
        "packages": {
            "R": "4.6.0",
            "metafor": "4.9-17",
            "HSROC": None,
        },
    }


def test_report_installed_versions_surfaces_rscript_failure(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_openmetar_r_manifests", VALIDATOR)
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)

    def fake_run(command, text, stdout, stderr, check):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="R is unavailable")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)

    with pytest.raises(validator.ValidationError, match="R is unavailable"):
        validator.report_installed_versions("Rscript", ["metafor"])
