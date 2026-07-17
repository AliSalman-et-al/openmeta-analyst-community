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


def test_import_and_strict_ty_use_the_identical_closed_qt_module_set():
    expected = [path.relative_to(ROOT).as_posix() for path in discover_handwritten_qt_files(ROOT)]
    completed = subprocess.run(
        [sys.executable, "scripts/import_qt_modules.py", "--root", ".", "--list"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.splitlines() == expected
    assert any(path.startswith("scripts/") for path in expected)
    assert set(discover_application_qt_modules(ROOT)) < set(discover_handwritten_qt_files(ROOT))

    workflow = (ROOT / "scripts/verify-qt6.ps1").read_text(encoding="utf-8")
    assert "$qtModules = @(uv run python scripts/import_qt_modules.py --root . --list)" in workflow
    assert "ty check" in workflow
    assert "$qtModules" in workflow


def test_final_cutover_audit_has_zero_active_legacy_findings():
    assert audit_cutover(ROOT) == []


def test_strict_ty_suppressions_match_the_reviewed_budget_exactly(tmp_path):
    assert validate_ty_ignore_allowlist(ROOT) == {"files": 14, "total": 30, "maximum": 30}

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
            json.dumps(
                {"schema_version": 2, "maximum_total": 1, "entries": entries}
            ),
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
