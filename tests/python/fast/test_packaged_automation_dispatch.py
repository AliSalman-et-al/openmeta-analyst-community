# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import sys
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
            ["RCMetaStudio", "--automation-package-open-report", "open.json", "sample.rcms"],
            "start_package_open_report",
            ("open.json", "sample.rcms"),
        ),
        (
            ["RCMetaStudio", "--automation-package-edit-save", "edit.json", "sample.rcms", "dest.rcms", "name", "Edited"],
            "start_package_edit_save",
            ("edit.json", "sample.rcms", "dest.rcms", "name", "Edited"),
        ),
        (
            ["RCMetaStudio", "--automation-package-analyze", "analysis.json", "sample.rcms", "binary.random"],
            "start_package_analyze",
            ("analysis.json", "sample.rcms", "binary.random"),
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
    with pytest.raises(SystemExit, match="open-report requires"):
        automation.dispatch(["RCMetaStudio", "--automation-package-open-report"])
    with pytest.raises(SystemExit, match="edit-save requires"):
        automation.dispatch(["RCMetaStudio", "--automation-package-edit-save"])
    with pytest.raises(SystemExit, match="analyze requires"):
        automation.dispatch(["RCMetaStudio", "--automation-package-analyze"])


def test_surface_hook_observes_and_closes_the_composed_main_window(monkeypatch):
    from rc_metastudio import automation

    class App:
        def __init__(self):
            self.process_events = 0
            self.quit_called = False
            self.delete_target = None

        def processEvents(self):
            self.process_events += 1
            if self.delete_target is not None:
                self.delete_target.deleted = True

        def quit(self):
            self.quit_called = True

    class Window:
        def __init__(self):
            self.close_calls = 0
            self.visible = False
            self.deleted = False

        def close(self):
            self.close_calls += 1
            return True

        def isVisible(self):
            if self.deleted:
                raise RuntimeError("wrapped C/C++ object has been deleted")
            return self.visible

    app, window = App(), Window()
    app.delete_target = window
    written = {}
    monkeypatch.setattr(automation, "start_automation", lambda: (app, window))
    monkeypatch.setattr(
        automation,
        "_surface_record",
        lambda *args: {"window_is_composed": args[-2] is window},
    )
    monkeypatch.setattr(automation, "_write_json", lambda path, value: written.update({path: value}))
    monkeypatch.setattr(automation, "dispose_qobjects", lambda *_args: None)

    assert automation.start_package_surface_smoke("surface.json", "1.25") == 0
    assert written["surface.json"]["window_is_composed"] is True
    assert written["surface.json"]["cleanup"] == {
        "close_accepted": True,
        "window_visible": False,
    }
    assert window.close_calls == 1
    assert app.quit_called is True


def test_automation_delegates_application_composition_to_launch(monkeypatch):
    from rc_metastudio import automation, launch

    expected = (object(), object())
    calls = []
    monkeypatch.setattr(
        launch,
        "compose_application",
        lambda **kwargs: calls.append(kwargs) or expected,
    )

    assert automation.start_automation() == expected
    assert calls == [{"phase_callback": None}]


def test_atomic_project_hooks_report_failed_open_without_using_blank_workspace(
    monkeypatch,
):
    from rc_metastudio import automation

    class Window:
        def open(self, *_args, **_kwargs):
            return False

        @property
        def tableView(self):
            raise AssertionError("a failed open must not edit the blank workspace")

        def save(self):
            raise AssertionError("a failed open must not save the blank workspace")

    written = {}
    monkeypatch.setattr(automation, "start_automation", lambda: (object(), Window()))
    monkeypatch.setattr(automation, "_configure_package_locale", lambda: None)
    monkeypatch.setattr(
        automation,
        "_close_automation_window",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        automation,
        "_write_json",
        lambda path, value: written.setdefault(path, value),
    )

    assert automation.start_package_edit_save(
        "edit.json", "missing.rcms", "destination.rcms", "name", "Edited"
    ) == 0
    assert automation.start_package_analyze(
        "analysis.json", "missing.rcms", "binary.random"
    ) == 0
    assert written["edit.json"]["opened"] is False
    assert written["edit.json"]["edited"] is False
    assert written["edit.json"]["saved"] is False
    assert written["analysis.json"]["opened"] is False


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
    for marker in (
        "locale_variants",
        "expected_normalized_summary_sha256",
        "normalize_packaged_summary_identity",
        "raw_summary_sha256",
        "Packaged Smoke",
        "binary.random",
    ):
        assert marker not in source
    assert "QLocale.setDefault" in source
    assert 'os.environ.get("RCMS_PACKAGE_LOCALE")' in source
    assert "importlib.import_module" not in source
    assert "from rpy2" not in source
    assert "packaged_runtime_observation" in source


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


def test_assembler_runtime_probe_is_neutral_under_scale_smoke(monkeypatch, tmp_path):
    from scripts import assemble_packaged_smoke_evidence as assembler

    runtime_probe = tmp_path / "runtime-probe.json"
    surface_directory = tmp_path / "surface-records"
    calls = []

    def fake_run(command, *, check, env=None):
        calls.append((command, env))
        if command[1] == "--automation-package-runtime-probe":
            runtime_probe.write_text(
                json.dumps({"qt": {"baseline_device_pixel_ratio": 1.0}}),
                encoding="utf-8",
            )
        else:
            Path(command[2]).write_text(
                json.dumps({"requested": command[3]}), encoding="utf-8"
            )

    monkeypatch.setenv("QT_SCALE_FACTOR", "1.75")
    monkeypatch.setattr(assembler.subprocess, "run", fake_run)

    assembler.capture_atomic_observations(
        tmp_path / "RCMetaStudio.exe",
        runtime_probe=runtime_probe,
        surface_directory=surface_directory,
    )

    assert calls[0][1] is not None
    assert "QT_SCALE_FACTOR" not in calls[0][1]


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
