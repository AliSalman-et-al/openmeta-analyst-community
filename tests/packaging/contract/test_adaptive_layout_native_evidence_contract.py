# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Release contracts for native adaptive-layout package evidence."""

import hashlib
import importlib.util
import json
import platform
from pathlib import Path

import pytest
from PyQt5 import QtGui


ROOT = Path(__file__).resolve().parents[3]


def _text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_packagers_retain_opt_in_controlled_adaptive_layout_evidence():
    windows = _text("scripts", "build-windows-package.ps1")
    macos = _text("scripts", "build-macos-package.sh")

    assert "Invoke-PackagedAdaptiveLayoutEvidence" in windows
    assert '"--automation-adaptive-layout-evidence"' in windows
    assert "$quotedOutputDir" in windows
    assert "$quotedSamplePath" in windows
    assert 'QT_QPA_PLATFORM = "offscreen"' not in windows[
        windows.index("function Invoke-PackagedAdaptiveLayoutEvidence") :
        windows.index("function Invoke-PackagedWizardLayoutSmokeTest")
    ]
    evidence_block = windows[
        windows.index("function Invoke-PackagedAdaptiveLayoutEvidence") :
        windows.index("function Invoke-PackagedWizardLayoutSmokeTest")
    ]
    assert "-WindowStyle Hidden" not in evidence_block
    assert "validate_adaptive_layout_evidence.py" in evidence_block
    assert "[switch]$CaptureAdaptiveLayoutEvidence" in windows
    assert "if ($CaptureAdaptiveLayoutEvidence)" in windows
    assert windows.index("if (-not $SkipSmoke)") < windows.index(
        "if ($CaptureAdaptiveLayoutEvidence)"
    )
    assert 'for scale in "1.0" "1.5"' in macos
    assert "--automation-adaptive-layout-evidence" in macos
    assert "validate_adaptive_layout_evidence.py" in macos
    assert "--capture-adaptive-layout-evidence" in macos
    assert 'if [ "$capture_adaptive_layout_evidence" -eq 1 ]' in macos
    assert "QT_QPA_PLATFORM=" not in macos[
        macos.index("run_adaptive_layout_evidence()") :
        macos.index("if [ \"$skip_smoke\" -eq 0 ]")
    ]


def test_hosted_package_workflow_does_not_require_native_layout_evidence():
    workflow = _text(".github", "workflows", "package-verification.yml")
    target = _text(".github", "workflows", "package-target.yml")

    assert "artifact_name: RCMetaStudio-windows-x64" in workflow
    assert "artifact_name: RCMetaStudio-macos-x64" in workflow
    assert "Upload adaptive-layout evidence" not in target
    assert "evidence_path" not in target
    assert "adaptive-layout-evidence" not in workflow
    assert target.count("if-no-files-found: error") >= 1


def test_native_evidence_runner_covers_the_release_review_contract():
    runner = _text("src", "rc_metastudio", "adaptive_layout_evidence.py")

    for archetype in ("workspace", "workflow", "transactional", "transient"):
        assert f'"{archetype}"' in runner
    for field in (
        "platform_plugin",
        "logical_dpi",
        "device_pixel_ratio",
        "actual_frame_geometry",
        "actual_client_geometry",
        "requested_client_size",
        "window_chrome",
        "font",
        "icon_available",
        "table",
        "splitter",
        "intrinsic_artifact",
        "remembered_geometry",
        "runtime_resize",
        "human_review",
    ):
        assert f'"{field}"' in runner
    assert "offscreen" in runner
    assert "minimal" in runner
    assert "QScreen.grabWindow" in runner
    assert '"capture_region": "native-frame"' in runner
    assert "available_screen_geometry" in runner
    assert "client_paint_probe_pixel_size" in runner
    assert "isExposed" in runner
    assert "frame_matches" in runner
    assert "pixel-diff" in runner


def _load_validator():
    validator_path = ROOT / "scripts" / "validate_adaptive_layout_evidence.py"
    spec = importlib.util.spec_from_file_location("evidence_validator", validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    return validator


def test_native_evidence_validator_matches_qt_half_up_pixel_rounding():
    validator = _load_validator()

    assert validator._physical_pixel_extent(515, 1.5) == 773


def _write_validator_fixture(tmp_path, validator):
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()

    def write_nonblank_png(path, size):
        image = QtGui.QImage(size[0], size[1], QtGui.QImage.Format_ARGB32)
        image.fill(QtGui.QColor("white"))
        painter = QtGui.QPainter(image)
        painter.fillRect(
            size[0] // 2,
            size[1] // 2,
            size[0] - (size[0] // 2),
            size[1] - (size[1] // 2),
            QtGui.QColor("#2457a6"),
        )
        painter.end()
        assert image.save(str(path), "PNG")

    content_sizes = {
        "new-dataset-workflow-constrained-owner": [640, 480],
        "about-legal-constrained-owner": [500, 300],
        "analysis-progress-constrained-owner": [420, 140],
    }
    surfaces = []
    for index, name in enumerate(validator.EXPECTED_SCENARIOS):
        archetype, exact_size, owner = validator.EXPECTED_SCENARIO_CONTRACTS[name]
        client_size = list(exact_size or content_sizes[name])
        frame_size = [client_size[0] + 16, client_size[1] + 39]
        frame_x, frame_y = 20 + index, 20 + index
        relative = "screenshots/%s.png" % name
        path = tmp_path / relative
        write_nonblank_png(path, frame_size)
        surfaces.append(
            {
                "name": name,
                "archetype": archetype,
                "screenshot": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "requested_client_size": client_size,
                "owning_workspace_client_size": owner,
                "actual_client_geometry": {
                    "x": frame_x + 8,
                    "y": frame_y + 31,
                    "width": client_size[0],
                    "height": client_size[1],
                },
                "actual_frame_geometry": {
                    "x": frame_x,
                    "y": frame_y,
                    "width": frame_size[0],
                    "height": frame_size[1],
                },
                "available_screen_geometry": {
                    "x": 0,
                    "y": 0,
                    "width": 1600,
                    "height": 1000,
                },
                "device_pixel_ratio": 1.0,
                "capture_pixel_size": frame_size,
                "client_paint_probe_pixel_size": client_size,
                "client_paint_probe_device_pixel_ratio": 1.0,
                "capture_region": "native-frame",
                "capture_method": "QScreen.grabWindow(desktop); physical frame crop",
            }
        )
    artifact = tmp_path / "intrinsic-ratio-evidence.png"
    write_nonblank_png(artifact, [640, 360])
    manifest = {
        "schema_version": 2,
        "platform_plugin": "windows",
        "scale_factor_environment": "1.0",
        "machine": platform.machine(),
        "surfaces": surfaces,
        "unavailable_scenarios": [],
        "intrinsic_artifact": {
            "path": artifact.name,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "pixel_size": [640, 360],
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "HUMAN_REVIEW.md").write_text("review me\n", encoding="utf-8")
    return manifest


def test_native_evidence_validator_is_exact_and_checks_png_integrity(tmp_path):
    validator = _load_validator()
    manifest = _write_validator_fixture(tmp_path, validator)

    validator.validate_evidence(tmp_path, "windows", "1.0")
    extra = tmp_path / "unexpected.txt"
    extra.write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="file membership"):
        validator.validate_evidence(tmp_path, "windows", "1.0")
    extra.unlink()
    manifest["surfaces"][0]["sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validator.validate_evidence(tmp_path, "windows", "1.0")


def test_validator_accepts_only_proven_unavailable_full_usability_at_150(tmp_path):
    validator = _load_validator()
    manifest = _write_validator_fixture(tmp_path, validator)
    unavailable_names = {
        "main-workspace-full-usability",
        "results-workspace-full-usability",
    }
    unavailable = []
    retained_surfaces = []
    for surface in manifest["surfaces"]:
        if surface["name"] not in unavailable_names:
            retained_surfaces.append(surface)
            continue
        path = tmp_path / surface["screenshot"]
        path.unlink()
        unavailable.append(
            {
                "name": surface["name"],
                "status": "capability-unavailable",
                "reason": "required native frame exceeds available screen geometry",
                "requested_client_size": [1024, 640],
                "required_frame_size": [1040, 679],
                "available_screen_geometry": {
                    "x": 0,
                    "y": 0,
                    "width": 1280,
                    "height": 647,
                },
                "frame_margins": {"left": 8, "top": 31, "right": 8, "bottom": 8},
            }
        )
    manifest["surfaces"] = retained_surfaces
    manifest["unavailable_scenarios"] = unavailable
    manifest["scale_factor_environment"] = "1.5"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    validator.validate_evidence(tmp_path, "windows", "1.5")

    manifest["scale_factor_environment"] = "1.0"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="allowed only at scale 1.5"):
        validator.validate_evidence(tmp_path, "windows", "1.0")

    manifest["scale_factor_environment"] = "1.5"
    manifest["unavailable_scenarios"][0]["available_screen_geometry"]["height"] = 900
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="even though its native frame fits"):
        validator.validate_evidence(tmp_path, "windows", "1.5")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("wrong-request", "exact client viewport"),
        ("wrong-actual", "exact client viewport"),
        ("wrong-owner", "owning Workspace contract"),
        ("off-screen", "outside its recorded available screen"),
        ("wrong-archetype", "wrong archetype"),
        ("tiny-workspace", "exact client viewport"),
        ("client-only-capture", "not a native-frame capture"),
    ],
)
def test_native_evidence_validator_rejects_semantic_contract_mutations(
    tmp_path, mutation, message
):
    validator = _load_validator()
    manifest = _write_validator_fixture(tmp_path, validator)
    workspace = manifest["surfaces"][0]
    content = manifest["surfaces"][4]
    if mutation == "wrong-request":
        workspace["requested_client_size"] = [801, 600]
    elif mutation == "wrong-actual":
        workspace["actual_client_geometry"]["width"] = 799
    elif mutation == "wrong-owner":
        content["owning_workspace_client_size"] = [1024, 640]
    elif mutation == "off-screen":
        workspace["actual_frame_geometry"]["x"] = 1590
        workspace["actual_client_geometry"]["x"] = 1598
    elif mutation == "wrong-archetype":
        workspace["archetype"] = "workflow"
    elif mutation == "tiny-workspace":
        workspace["requested_client_size"] = [10, 10]
        workspace["actual_client_geometry"].update(width=10, height=10)
    elif mutation == "client-only-capture":
        workspace["capture_region"] = "client"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validator.validate_evidence(tmp_path, "windows", "1.0")


def test_launch_exposes_native_evidence_as_an_explicit_automation_mode():
    launch = _text("src", "rc_metastudio", "launch.py")

    assert '"--automation-adaptive-layout-evidence"' in launch
    assert "start_adaptive_layout_evidence" in launch
    assert "RCMS_ADAPTIVE_LAYOUT_EVIDENCE_LOG" in launch
