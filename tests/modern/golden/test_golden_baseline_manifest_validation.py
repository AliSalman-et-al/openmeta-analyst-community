import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "scripts" / "validate_golden_baseline_manifests.py"


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


def test_manifest_completeness_mode_reports_no_pending_trace_entries(tmp_path):
    root = copy_modernization_docs(tmp_path)

    result = run_validator(root)

    assert result.returncode == 0, result.stderr
    assert "no pending trace entries" in result.stdout


def test_strict_no_pending_mode_accepts_current_traceability(tmp_path):
    root = copy_modernization_docs(tmp_path)

    result = run_validator(root, "--strict-no-pending")

    assert result.returncode == 0, result.stderr
    assert "validated strict no-pending mode" in result.stdout


def test_non_pending_trace_must_point_to_known_target(tmp_path):
    root = copy_modernization_docs(tmp_path)
    traceability_path = root / "docs" / "modernization" / "workflow-traceability.json"
    traceability = json.loads(traceability_path.read_text(encoding="utf-8"))
    traceability["workflows"][7]["trace"] = ["missing-golden-row"]
    traceability_path.write_text(json.dumps(traceability), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert "missing-golden-row" in result.stderr


def test_baseline_manifest_requires_capture_metadata_contract(tmp_path):
    root = copy_modernization_docs(tmp_path)
    manifest_path = (
        root / "docs" / "modernization" / "comprehensive-golden-baseline-manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["capture_metadata"]["required_fields"].remove("baseline_environment")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_validator(root)

    assert result.returncode == 1
    assert (
        "capture_metadata.required_fields missing baseline_environment" in result.stderr
    )
