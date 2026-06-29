import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_openmetar_r_manifests.py"
DEPENDENCY_MANIFEST = Path("docs") / "modernization" / "OpenMetaR-r-dependencies.json"
DRIFT_MANIFEST = Path("docs") / "modernization" / "OpenMetaR-statistical-drift.json"
OPENMETAR_PACKAGE = REPO_ROOT / "src" / "R" / "OpenMetaR"
OPENMETAR_R_DIR = OPENMETAR_PACKAGE / "R"
OPENMETAR_DESCRIPTION = OPENMETAR_PACKAGE / "DESCRIPTION"
OPENMETAR_NAMESPACE = OPENMETAR_PACKAGE / "NAMESPACE"

LEGACY_EXPORT_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9._]*)\s*<-\s*function\s*\(", re.MULTILINE)
S4_CLASS_PATTERN = re.compile(r"setClass\(\s*[\"']([^\"']+)[\"']")


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


def read_description_fields():
    fields = {}
    current_key = None
    for line in OPENMETAR_DESCRIPTION.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line[0].isspace() and current_key is not None:
            fields[current_key] += " " + line.strip()
            continue
        key, value = line.split(":", 1)
        current_key = key
        fields[key] = value.strip()
    return fields


def parse_packages(field_value):
    packages = set()
    for entry in field_value.split(","):
        name = entry.strip().split(" ", 1)[0]
        if name:
            packages.add(name)
    return packages


def legacy_exported_functions_from_source():
    names = set()
    for path in OPENMETAR_R_DIR.glob("*.r"):
        names.update(LEGACY_EXPORT_PATTERN.findall(path.read_text(encoding="utf-8")))
    return names


def s4_classes_from_source():
    names = set()
    for path in OPENMETAR_R_DIR.glob("*.r"):
        names.update(S4_CLASS_PATTERN.findall(path.read_text(encoding="utf-8")))
    return names


def namespace_entries(directive):
    text = OPENMETAR_NAMESPACE.read_text(encoding="utf-8")
    entries = set()
    for match in re.finditer(rf"^{directive}\(([^)]*)\)$", text, flags=re.MULTILINE):
        entries.update(name.strip() for name in match.group(1).split(",") if name.strip())
    return entries


def test_openmetar_description_declares_only_direct_package_dependencies():
    fields = read_description_fields()

    assert parse_packages(fields["Depends"]) == {"R"}
    assert parse_packages(fields["Imports"]) == {
        "boot",
        "grDevices",
        "graphics",
        "grid",
        "HSROC",
        "lme4",
        "methods",
        "metafor",
        "stats",
        "utils",
    }
    assert parse_packages(fields["Suggests"]) == {"roxygen2"}
    assert "igraph" not in fields["Imports"]
    assert "Hmisc" not in fields["Imports"]
    assert "exportPattern" not in OPENMETAR_NAMESPACE.read_text(encoding="utf-8")


def test_openmetar_source_uses_namespace_imports_instead_of_attach_calls():
    package_attach_pattern = re.compile(r"\b(?:library|require)\s*\(")

    offenders = []
    for path in OPENMETAR_R_DIR.glob("*.r"):
        if package_attach_pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_openmetar_namespace_preserves_legacy_export_surface_explicitly():
    expected_functions = legacy_exported_functions_from_source()
    actual_exports = namespace_entries("export")

    assert expected_functions
    assert actual_exports == expected_functions
    assert {"binary.random.parameters", "diagnostic.hsroc.pretty.names", "gimpute.cont.data"} <= actual_exports


def test_openmetar_namespace_preserves_s4_classes_explicitly():
    expected_classes = s4_classes_from_source()
    actual_classes = namespace_entries("exportClasses")

    assert actual_classes == expected_classes
