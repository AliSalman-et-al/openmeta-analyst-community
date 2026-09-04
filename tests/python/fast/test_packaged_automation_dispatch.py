from __future__ import annotations

import json
from pathlib import Path
import sys

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


def test_surface_focus_observation_traverses_from_window_not_application():
    from rc_metastudio import automation

    class App:
        def __init__(self):
            self.current = None

        def processEvents(self):
            pass

        def focusWidget(self):
            return self.current

    class Control:
        def __init__(self, app):
            self.app = app

        def setFocus(self):
            self.app.current = self

    class Window:
        def __init__(self, app, target):
            self.app = app
            self.target = target
            self.calls = []

        def focusNextPrevChild(self, forward):
            self.calls.append(forward)
            self.app.current = self.target
            return True

    app = App()
    target = object()
    control = Control(app)
    window = Window(app, target)

    focus_before, focus_after = automation._observe_surface_focus(
        app, window, control
    )

    assert focus_before is control
    assert focus_after is target
    assert window.calls == [True]


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
            {"operation": "analysis", "locale": "en_US", "decimal_point": ".", "input": "1.2", "canonical_value": 1.2, "summary": "Binary Random-Effects Model\nEstimate 1", "svg_paths": {"forest": str(tmp_path / "forest.svg")}},
            {"operation": "locale", "locale": "de_DE", "decimal_point": ",", "input": "1,2", "canonical_value": 1.2, "summary": "Binary Random-Effects Model\nEstimate 1", "svg_paths": {"forest": str(tmp_path / "forest.svg")}},
        ],
        "edit_observed": True,
        "analysis_observed": True,
        "reopen_observed": True,
        "analysis_after_reopen_observed": True,
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
    assert "QLocale.setDefault" in source
    assert 'os.environ.get("RCMS_PACKAGE_LOCALE")' in source


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


def test_assembler_keeps_surface_directory_records_in_place(monkeypatch, tmp_path):
    from scripts import assemble_packaged_smoke_evidence as assembler

    surface_directory = tmp_path / "surface-records"
    surface_directory.mkdir()
    record = surface_directory / "surface-1.25.json"
    record.write_text(json.dumps({"requested": "1.25"}), encoding="utf-8")
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "summary": "summary",
                "svg_paths": {},
                "locale_inputs": [
                    {
                        "operation": "analysis",
                        "locale": "en_US",
                        "decimal_point": ".",
                        "input": "1.2",
                        "canonical_value": 1.2,
                        "summary": "summary",
                        "svg_paths": {},
                    },
                    {
                        "operation": "locale",
                        "locale": "de_DE",
                        "decimal_point": ",",
                        "input": "1,2",
                        "canonical_value": 1.2,
                        "summary": "summary",
                        "svg_paths": {},
                    },
                ],
                "edit_observed": True,
                "analysis_observed": True,
                "reopen_observed": True,
                "analysis_after_reopen_observed": True,
            }
        ),
        encoding="utf-8",
    )
    samples = tmp_path / "samples.json"
    samples.write_text("{}", encoding="utf-8")
    output = tmp_path / "packaged-smoke.json"
    monkeypatch.setattr(
        assembler,
        "capture_atomic_observations",
        lambda executable, runtime_probe, surface_directory: [record],
    )
    monkeypatch.setattr(
        assembler,
        "capture_workflow_observations",
        lambda executable, sample, output: None,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble_packaged_smoke_evidence.py",
            "--workflow-observation",
            str(workflow),
            "--surface-records",
            str(surface_directory),
            "--sample-observations",
            str(samples),
            "--sample",
            "BCG.rcms",
            "--sample-path",
            str(tmp_path / "sample.rcms"),
            "--executable",
            str(tmp_path / "RCMetaStudio.exe"),
            "--runtime-probe",
            str(tmp_path / "runtime-probe.json"),
            "--surface-directory",
            str(surface_directory),
            "--output",
            str(output),
        ],
    )

    assert assembler.main() == 0
    assert surface_directory.is_dir()
    assert json.loads(output.read_text(encoding="utf-8"))["scales"] == [
        {"requested": "1.25"}
    ]


def test_assembler_runs_surface_probes_with_requested_scale_and_locale():
    source = Path("scripts/assemble_packaged_smoke_evidence.py").read_text(encoding="utf-8")
    assert 'environment["QT_SCALE_FACTOR"] = scale' in source
    assert 'environment["RCMS_PACKAGE_BASELINE_DPR"] = baseline' in source
    assert 'environment["RCMS_PACKAGE_LOCALE"] = "de_DE"' in source


def test_assembler_rejects_unobserved_reopen_analysis(tmp_path):
    from scripts import assemble_packaged_smoke_evidence as assembler

    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({"edit_observed": True, "analysis_observed": True, "reopen_observed": True, "analysis_after_reopen_observed": False}), encoding="utf-8")
    surfaces = tmp_path / "surfaces.json"
    surfaces.write_text("[]", encoding="utf-8")
    samples = tmp_path / "samples.json"
    samples.write_text("{}", encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        assembler.assemble(workflow_observation=workflow, surface_records=surfaces, sample_observations=samples, sample="BCG.rcms", output=tmp_path / "out.json")


def test_assembler_rejects_reused_locale_operation_observation(tmp_path):
    from scripts import assemble_packaged_smoke_evidence as assembler

    svg = tmp_path / "forest.svg"
    svg.write_text("<svg />", encoding="utf-8")
    locale = {
        "operation": "analysis",
        "locale": "en_US",
        "decimal_point": ".",
        "input": "1.2",
        "canonical_value": 1.2,
        "summary": "summary",
        "svg_paths": {"forest": str(svg)},
    }
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({
        "summary": "summary",
        "svg_paths": {"forest": str(svg)},
        "locale_inputs": [locale, {**locale, "locale": "de_DE", "decimal_point": ",", "input": "1,2"}],
        "edit_observed": True,
        "analysis_observed": True,
        "reopen_observed": True,
        "analysis_after_reopen_observed": True,
    }), encoding="utf-8")
    surfaces = tmp_path / "surfaces.json"
    surfaces.write_text("[]", encoding="utf-8")
    samples = tmp_path / "samples.json"
    samples.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="distinct locale operations"):
        assembler.assemble(workflow_observation=workflow, surface_records=surfaces, sample_observations=samples, sample="BCG.rcms", output=tmp_path / "out.json")
