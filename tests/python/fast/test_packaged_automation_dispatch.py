from __future__ import annotations

import json

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


def test_emitted_workflow_evidence_is_accepted_by_deployment_validators(
    monkeypatch, tmp_path
):
    from rc_metastudio import automation
    from scripts import inspect_macos_deployment, inspect_windows_deployment

    digest = "a" * 64
    workflow = {
        "automation_entry_point": True,
        "converted_sample": "BCG.rcms",
        "representative_edit": True,
        "real_r_analysis": True,
        "result_text": True,
        "expected_normalized_summary_sha256": inspect_macos_deployment.EXPECTED_SUMMARY_SHA256_BY_SAMPLE["BCG.rcms"],
        "raw_summary_sha256": digest,
        "normalized_summary_sha256": inspect_macos_deployment.EXPECTED_SUMMARY_SHA256_BY_SAMPLE["BCG.rcms"],
        "svg_sha256": {"forest": digest},
        "locale_variants": [
            {"locale": "en_US", "raw_summary_sha256": digest, "normalized_summary_sha256": inspect_macos_deployment.EXPECTED_SUMMARY_SHA256_BY_SAMPLE["BCG.rcms"]},
            {"locale": "de_DE", "raw_summary_sha256": digest, "normalized_summary_sha256": inspect_macos_deployment.EXPECTED_SUMMARY_SHA256_BY_SAMPLE["BCG.rcms"]},
        ],
        "save_reopen": True,
        "analysis_after_reopen": True,
        "sample_projects": {"passed": True, "manifest_sha256": digest, "projects": [{"project": "BCG.rcms", "sha256": digest, "semantic_sha256": digest, "opened_in_packaged_application": True}]},
    }

    class Workspace:
        document = None

        def mark_saved(self):
            pass

    class Window:
        workspace = Workspace()

        def open(self, path, raise_on_error=True):
            return True

        def close(self):
            return True

    class App:
        def platformName(self):
            return "cocoa"

        def processEvents(self):
            pass

        def quit(self):
            pass

    evidence_path = tmp_path / "smoke.json"
    log_path = tmp_path / "smoke.log"
    monkeypatch.setenv("RCMS_PACKAGE_SMOKE_EVIDENCE", str(evidence_path))
    monkeypatch.setenv("RCMS_AUTOMATION_SMOKE_LOG", str(log_path))
    monkeypatch.setattr(automation, "start_automation", lambda: (App(), Window()))
    monkeypatch.setattr(automation, "_dispose_qobjects", lambda *args: None)
    monkeypatch.setattr(automation, "_exercise_packaged_project_workflow", lambda *args: workflow.copy())
    monkeypatch.setattr(automation, "_sample_project_observations", lambda *args: workflow["sample_projects"])

    assert automation.start_automation_smoke("BCG.rcms") == 0
    emitted = json.loads(evidence_path.read_text(encoding="utf-8"))
    inspect_macos_deployment.validate_packaged_workflow_evidence(emitted)
    finalized = inspect_windows_deployment.finalize_smoke_evidence(evidence_path, log_path)
    assert finalized["execution"]["clean_exit"] is True
