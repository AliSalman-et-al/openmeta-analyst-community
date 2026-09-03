from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_code_health_emits_machine_readable_evidence_and_report(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"
    report = tmp_path / "report.txt"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/code_health.py",
            "--base",
            "4aa0740",
            "--head",
            "HEAD",
            "--output",
            str(output),
            "--report",
            str(report),
            "--allow-fail",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert set(payload["files"][0]["churn"]) == {"30", "90", "180"}
    assert "hotspot_score" in payload["files"][0]
    assert {"coupling", "cycles", "cognitive_complexity", "maintainability", "defect_history", "gate"} <= payload.keys()
    assert payload["dependency_tooling"]["tool"] == "grimp"
    assert "Code health" in report.read_text(encoding="utf-8")
    assert "Code health" in result.stdout
