from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("argv", "attribute", "expected"),
    [
        (
            ["RCMetaStudio", "--automation-package-runtime-probe", "probe.json"],
            "start_package_runtime_probe",
            ("probe.json",),
        ),
        (
            ["RCMetaStudio", "--automation-package-surface-smoke", "smoke.json", "1.25"],
            "start_package_surface_smoke",
            ("smoke.json", "1.25"),
        ),
        (
            ["RCMetaStudio", "--automation-startup-wizard-smoke", "wizard.json", "sample.rcms"],
            "start_startup_wizard_smoke",
            ("wizard.json", "sample.rcms"),
        ),
        (
            ["RCMetaStudio", "--automation-package-operation", "operation.json", "sample.rcms", "analysis", "de_DE"],
            "start_package_operation",
            ("operation.json", "sample.rcms", "analysis", "de_DE"),
        ),
    ],
)
def test_packaged_qualification_commands_reach_shipped_hooks(
    monkeypatch, argv, attribute, expected
):
    from rc_metastudio import automation

    calls = []
    monkeypatch.setattr(
        automation,
        attribute,
        lambda *args: calls.append(args) or 17,
    )

    assert automation.dispatch(argv) == 17
    assert calls == [expected]


def test_packaged_qualification_commands_validate_their_arguments():
    from rc_metastudio import automation

    with pytest.raises(SystemExit, match="runtime-probe requires"):
        automation.dispatch(["RCMetaStudio", "--automation-package-runtime-probe"])
    with pytest.raises(SystemExit, match="surface-smoke requires"):
        automation.dispatch(["RCMetaStudio", "--automation-package-surface-smoke"])
    with pytest.raises(SystemExit, match="startup-wizard-smoke requires"):
        automation.dispatch(["RCMetaStudio", "--automation-startup-wizard-smoke"])
    with pytest.raises(SystemExit, match="package-operation requires"):
        automation.dispatch(["RCMetaStudio", "--automation-package-operation"])


def test_developer_assembly_emits_evidence_accepted_by_both_inspectors(
    monkeypatch, tmp_path
):
    from scripts import assemble_packaged_smoke_evidence as assembler
    from scripts import inspect_macos_deployment, inspect_windows_deployment

    digest = "a" * 64
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({
        "summary": "Binary Random-Effects Model\nEstimate 1",
        "svg_paths": {"forest": str(tmp_path / "forest.svg")},
        "locale_inputs": [
            {"locale": "en_US", "input": "1.2", "canonical_value": 1.2, "summary": "Binary Random-Effects Model\nEstimate 1", "svg_paths": {"forest": str(tmp_path / "forest.svg")}},
            {"locale": "de_DE", "input": "1,2", "canonical_value": 1.2, "summary": "Binary Random-Effects Model\nEstimate 1", "svg_paths": {"forest": str(tmp_path / "forest.svg")}},
        ],
        "edit_observed": True,
        "analysis_observed": True,
        "reopen_observed": True,
    }), encoding="utf-8")
    (tmp_path / "forest.svg").write_text("<svg />", encoding="utf-8")
    surfaces_path = tmp_path / "surfaces.json"
    surfaces_path.write_text("[]", encoding="utf-8")
    samples_path = tmp_path / "samples.json"
    samples_path.write_text(json.dumps({"passed": True, "manifest_sha256": digest, "projects": [{"project": "BCG.rcms", "sha256": digest, "semantic_sha256": digest, "opened_in_packaged_application": True}]}), encoding="utf-8")
    output = tmp_path / "evidence.json"
    evidence = assembler.assemble(workflow_observation=workflow_path, surface_records=surfaces_path, sample_observations=samples_path, sample="BCG.rcms", output=output)
    expected = evidence["workflows"]["normalized_summary_sha256"]
    monkeypatch.setitem(inspect_macos_deployment.EXPECTED_SUMMARY_SHA256_BY_SAMPLE, "BCG.rcms", expected)
    inspect_macos_deployment.validate_packaged_workflow_evidence(evidence)
    log = tmp_path / "smoke.log"
    log.write_text("packaged-workflow:post-close\n", encoding="utf-8")
    finalized = inspect_windows_deployment.finalize_smoke_evidence(output, log)
    assert finalized["execution"]["clean_exit"] is True


def test_frozen_hook_contains_no_scenario_or_result_comparison_logic():
    source = Path("src/rc_metastudio/automation.py").read_text(encoding="utf-8")
    for marker in ("locale_variants", "expected_normalized_summary_sha256", "normalize_packaged_summary_identity", "raw_summary_sha256"):
        assert marker not in source


def test_package_pipelines_assemble_atomic_observations_before_validation():
    windows = Path("scripts/build-windows-package.ps1").read_text(encoding="utf-8")
    macos = Path("scripts/build-macos-package.sh").read_text(encoding="utf-8")
    for script in (windows, macos):
        assert "assemble_packaged_smoke_evidence.py" in script
        assert "workflow-observation" in script
        assert "sample-observations" in script
        assert "surface-records" in script
        assert "--workflow-observation" in script
        assert "--surface-records" in script
        assert "--sample-observations" in script
        assert "--sample-root" in script
        assert "--executable" in script
        assert "--output" in script
