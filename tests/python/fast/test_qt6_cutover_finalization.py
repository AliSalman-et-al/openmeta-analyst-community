import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from rc_metastudio.qt6_cutover import (
    CutoverAuditError,
    _ty_ignore_entries,
    audit_cutover,
    discover_application_qt_modules,
    discover_handwritten_qt_files,
    validate_legacy_test_classification,
    validate_ty_ignore_allowlist,
)


ROOT = Path(__file__).resolve().parents[3]
_IMPORT_AUDIT_SPEC = importlib.util.spec_from_file_location(
    "qt_import_audit_test", ROOT / "scripts" / "import_qt_modules.py"
)
assert _IMPORT_AUDIT_SPEC is not None and _IMPORT_AUDIT_SPEC.loader is not None
qt_import_audit = importlib.util.module_from_spec(_IMPORT_AUDIT_SPEC)
_IMPORT_AUDIT_SPEC.loader.exec_module(qt_import_audit)


def test_import_and_strict_ty_use_the_identical_closed_qt_module_set(
    monkeypatch, tmp_path
):
    real_subprocess_run = subprocess.run
    expected = [
        path.relative_to(ROOT).as_posix()
        for path in discover_handwritten_qt_files(ROOT)
    ]
    completed = subprocess.run(
        [sys.executable, "scripts/import_qt_modules.py", "--root", ".", "--list"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.splitlines() == expected
    assert any(path.startswith("scripts/") for path in expected)
    assert set(discover_application_qt_modules(ROOT)) < set(
        discover_handwritten_qt_files(ROOT)
    )

    workflow = (ROOT / "scripts/verify-qt6.ps1").read_text(encoding="utf-8")
    assert (
        "$qtModules = @(uv run python scripts/import_qt_modules.py --root . --list)"
        in workflow
    )
    assert "ty check" in workflow
    assert "$qtModules" in workflow
    calls = []

    def complete(command, **kwargs):
        calls.append((command, kwargs))
        relative = command[-1]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=qt_import_audit._success_marker(relative) + "\n",
            stderr="",
        )

    monkeypatch.setattr(qt_import_audit.subprocess, "run", complete)
    results = qt_import_audit.import_modules(ROOT, tmp_path)
    expected = [
        path.relative_to(ROOT).as_posix()
        for path in discover_handwritten_qt_files(ROOT)
    ]

    assert [result["module"] for result in results] == expected
    assert len(calls) == len(expected) == 45
    assert sum(path.startswith("scripts/") for path in expected) == 7
    for (command, kwargs), relative in zip(calls, expected, strict=True):
        assert command[:4] == [sys.executable, "-W", "error", "-c"]
        assert command[-1] == relative
        assert "spec_from_file_location" in command[4]
        assert "exec_module(module)" in command[4]
        assert "os.environ['RCMS_STUB_BACKEND'] = '1'" in command[4]
        assert "install_meta_py_r_backend()" in command[4]
        assert "initialized the real rpy2 backend" in command[4]
        assert kwargs["env"]["PYTHONWARNINGS"] == "error"
        assert kwargs["timeout"] == 30
        assert kwargs["check"] is False

    drift_root = tmp_path / "drift"
    source = drift_root / "src" / "rc_metastudio"
    scripts = drift_root / "scripts"
    source.mkdir(parents=True)
    scripts.mkdir()
    (source / "application_surface.py").write_text(
        "from PyQt6 import QtCore\n", encoding="utf-8"
    )
    (scripts / "new_verification_surface.py").write_text(
        "from PyQt6 import QtGui\n", encoding="utf-8"
    )

    def fail_new_script(command, **kwargs):
        relative = command[-1]
        return subprocess.CompletedProcess(
            command,
            int(relative.startswith("scripts/")),
            stdout=(
                ""
                if relative.startswith("scripts/")
                else qt_import_audit._success_marker(relative) + "\n"
            ),
            stderr="new script warning" if relative.startswith("scripts/") else "",
        )

    monkeypatch.setattr(qt_import_audit.subprocess, "run", fail_new_script)
    report = tmp_path / "report.json"

    assert (
        qt_import_audit.main(
            [
                "--root",
                str(drift_root),
                "--build-root",
                str(drift_root / "build"),
                "--report",
                str(report),
            ]
        )
        == 1
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert [entry["module"] for entry in payload["modules"]] == [
        "scripts/new_verification_surface.py",
        "src/rc_metastudio/application_surface.py",
    ]
    assert payload["modules"][0]["returncode"] == 1

    monkeypatch.setattr(qt_import_audit.subprocess, "run", real_subprocess_run)
    real_root = tmp_path / "real-subprocess"
    package = real_root / "src" / "rc_metastudio"
    scripts = real_root / "scripts"
    package.mkdir(parents=True)
    scripts.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "qt6_ui.py").write_text(
        "def prepare_generated_ui_imports():\n    return None\n", encoding="utf-8"
    )
    (package / "qt6_resources.py").write_text(
        "def ensure_application_resources():\n    return None\n", encoding="utf-8"
    )
    (package / "meta_py_r_backend.py").write_text(
        "import os\n"
        "import sys\n"
        "import types\n"
        "def install_meta_py_r_backend():\n"
        "    if os.environ.get('RCMS_STUB_BACKEND') != '1':\n"
        "        import rpy2\n"
        "    backend = types.ModuleType('rc_metastudio.meta_py_r')\n"
        "    backend._oma_stub_backend = True\n"
        "    sys.modules['rc_metastudio.meta_py_r'] = backend\n"
        "    sys.modules['meta_py_r'] = backend\n"
        "    return backend\n",
        encoding="utf-8",
    )
    (scripts / "rpy2.py").write_text(
        "raise AssertionError('the real analysis backend was initialized')\n",
        encoding="utf-8",
    )
    (scripts / "backend_surface.py").write_text(
        "from PyQt6 import QtCore\n"
        "import meta_py_r\n"
        "assert meta_py_r._oma_stub_backend is True\n",
        encoding="utf-8",
    )
    (scripts / "warning_surface.py").write_text(
        "from PyQt6 import QtCore\n"
        "import warnings\n"
        "warnings.warn('fixture import warning', UserWarning)\n",
        encoding="utf-8",
    )
    (scripts / "early_exit_surface.py").write_text(
        "from PyQt6 import QtCore\nimport sys\nsys.exit(0)\n",
        encoding="utf-8",
    )
    guarded_main_marker = real_root / "guarded-main-ran"
    (scripts / "guarded_surface.py").write_text(
        "from pathlib import Path\n"
        "from PyQt6 import QtCore\n"
        "if __name__ == '__main__':\n"
        f"    Path({str(guarded_main_marker)!r}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8",
    )

    real_results = {
        result["module"]: result
        for result in qt_import_audit.import_modules(real_root, real_root / "build")
    }

    assert set(real_results) == {
        "scripts/backend_surface.py",
        "scripts/early_exit_surface.py",
        "scripts/guarded_surface.py",
        "scripts/warning_surface.py",
    }
    assert real_results["scripts/backend_surface.py"]["returncode"] == 0
    assert real_results["scripts/backend_surface.py"]["stderr"] == ""
    assert real_results["scripts/warning_surface.py"]["returncode"] != 0
    assert (
        "fixture import warning" in real_results["scripts/warning_surface.py"]["stderr"]
    )
    assert real_results["scripts/early_exit_surface.py"]["returncode"] != 0
    assert (
        "before its success marker"
        in real_results["scripts/early_exit_surface.py"]["stderr"]
    )
    assert real_results["scripts/guarded_surface.py"]["returncode"] == 0
    assert real_results["scripts/guarded_surface.py"]["stderr"] == ""
    assert not guarded_main_marker.exists()


def test_final_cutover_audit_has_zero_active_legacy_findings():
    assert audit_cutover(ROOT) == []


def test_strict_ty_suppressions_match_the_reviewed_budget_exactly(tmp_path):
    assert validate_ty_ignore_allowlist(ROOT) == {
        "files": 14,
        "total": 31,
        "maximum": 31,
    }

    original = """\
class Owner:
    def eventFilter(  # ty: ignore[invalid-method-override] -- verified stub mismatch
        self, watched: object | None, event: object | None
    ) -> bool:
        return watched is not None and event is not None
"""
    mutations = {
        "signature": original.replace("event: object | None", "event: str | None"),
        "owner": original.replace("class Owner:", "class RenamedOwner:"),
        "rule": original.replace(
            "ignore[invalid-method-override]", "ignore[unresolved-attribute]"
        ),
    }
    for name, mutated in mutations.items():
        root = tmp_path / name
        source = root / "src/example.py"
        source.parent.mkdir(parents=True)
        source.write_text(original, encoding="utf-8")
        entries = _ty_ignore_entries(root)
        config = root / "config"
        config.mkdir()
        (config / "qt6-ty-ignore-allowlist.json").write_text(
            json.dumps({"schema_version": 2, "maximum_total": 1, "entries": entries}),
            encoding="utf-8",
        )
        assert validate_ty_ignore_allowlist(root) == {
            "files": 1,
            "total": 1,
            "maximum": 1,
        }
        source.write_text(mutated, encoding="utf-8")
        with pytest.raises(CutoverAuditError, match="allowlist drifted"):
            validate_ty_ignore_allowlist(root)


def test_legacy_test_classification_covers_the_frozen_inventory_exactly():
    result = validate_legacy_test_classification(ROOT)
    assert result["classified"] == 27
    assert result["classified_deleted_nodes"] == 12
    assert result["decisions"] == {
        "ported": 24,
        "retired": 1,
        "rewritten-at-stronger-seam": 2,
    }


def test_classification_rejects_missing_or_unnamed_replacement_evidence(tmp_path):
    baseline = {
        "qt_bearing_tests": ["tests/old.py"],
        "generated_modules": [],
    }
    classification = {
        "schema_version": 1,
        "classifications": [
            {
                "legacy_test": "tests/old.py",
                "decision": "retired",
                "evidence": [],
            }
        ],
    }
    (tmp_path / "docs/verification/pre-qt6-baseline").mkdir(parents=True)
    (tmp_path / "docs/verification/pre-qt6-baseline/qt-port-inventory.json").write_text(
        json.dumps(baseline), encoding="utf-8"
    )
    (tmp_path / "docs/verification/qt6-legacy-test-classification.json").write_text(
        json.dumps(classification), encoding="utf-8"
    )

    with pytest.raises(CutoverAuditError, match="named stronger evidence"):
        validate_legacy_test_classification(tmp_path)


def test_cutover_audit_rejects_runtime_pickle_and_generated_python(tmp_path):
    source = tmp_path / "src/rc_metastudio"
    forms = source / "forms"
    forms.mkdir(parents=True)
    (source / "reader.py").write_text("import pickle\n", encoding="utf-8")
    (forms / "ui_generated.py").write_text(
        "# Form implementation generated from reading ui file\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.setuptools.package-data]\nrc_metastudio = ["forms/*.py"]\n',
        encoding="utf-8",
    )

    findings = audit_cutover(tmp_path)
    assert {finding.rule for finding in findings} == {
        "generated-python",
        "pickle-project-runtime",
        "python-package-input",
    }
