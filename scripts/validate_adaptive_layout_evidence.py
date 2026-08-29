# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed validation for packaged adaptive-layout evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, NoReturn

from PyQt6 import QtGui


EXPECTED_SCENARIOS = (
    "main-workspace-constrained",
    "results-workspace-constrained",
    "main-workspace-full-usability",
    "results-workspace-full-usability",
    "new-dataset-workflow-constrained-owner",
    "about-legal-constrained-owner",
    "analysis-progress-constrained-owner",
)
EXPECTED_SCENARIO_CONTRACTS = {
    "main-workspace-constrained": ("workspace", [800, 600], None),
    "results-workspace-constrained": ("workspace", [800, 600], None),
    "main-workspace-full-usability": ("workspace", [1024, 640], None),
    "results-workspace-full-usability": ("workspace", [1024, 640], None),
    "new-dataset-workflow-constrained-owner": ("workflow", None, [800, 600]),
    "about-legal-constrained-owner": ("transactional", None, [800, 600]),
    "analysis-progress-constrained-owner": ("transient", None, [800, 600]),
}
CAPABILITY_QUALIFIED_SCENARIOS = {
    "main-workspace-full-usability",
    "results-workspace-full-usability",
}


def _fail(message: str) -> NoReturn:
    raise ValueError("Invalid adaptive-layout evidence: %s" % message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _physical_pixel_extent(logical_extent: float, device_pixel_ratio: float) -> int:
    """Match Qt's half-up conversion from positive logical to physical pixels."""
    return int((logical_extent * device_pixel_ratio) + 0.5)


def _read_nonblank_png(path: Path, expected_size: Any = None) -> list[int]:
    image = QtGui.QImage(str(path))
    if image.isNull():
        _fail("%s is not a readable PNG" % path.name)
    actual = [image.width(), image.height()]
    if expected_size is not None and actual != list(expected_size):
        _fail("%s has pixel size %s, expected %s" % (path.name, actual, expected_size))
    converted = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    first = converted.pixel(0, 0)
    varied = False
    for y in range(0, converted.height(), max(1, converted.height() // 32)):
        for x in range(0, converted.width(), max(1, converted.width() // 32)):
            if converted.pixel(x, y) != first:
                varied = True
                break
        if varied:
            break
    if not varied:
        _fail("%s is blank or single-colour" % path.name)
    return actual


def _rect(record: dict[str, Any], field: str) -> tuple[int, int, int, int]:
    value = record.get(field)
    if not isinstance(value, dict):
        _fail("%s has no %s record" % (record.get("name"), field))
    try:
        rect = tuple(int(value[key]) for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError):
        _fail("%s has malformed %s" % (record.get("name"), field))
    if rect[2] < 1 or rect[3] < 1:
        _fail("%s has empty %s" % (record.get("name"), field))
    return (rect[0], rect[1], rect[2], rect[3])


def _contains(
    outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]
) -> bool:
    return (
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[0] + inner[2] <= outer[0] + outer[2]
        and inner[1] + inner[3] <= outer[1] + outer[3]
    )


def _validate_scenario_semantics(record: dict[str, Any]) -> tuple[int, int, int, int]:
    name = record["name"]
    archetype, exact_client_size, owner_size = EXPECTED_SCENARIO_CONTRACTS[name]
    if record.get("archetype") != archetype:
        _fail("%s has wrong archetype" % name)
    if record.get("owning_workspace_client_size") != owner_size:
        _fail("%s has wrong owning Workspace contract" % name)
    requested = record.get("requested_client_size")
    client = _rect(record, "actual_client_geometry")
    frame = _rect(record, "actual_frame_geometry")
    available = _rect(record, "available_screen_geometry")
    actual_client_size = [client[2], client[3]]
    if exact_client_size is not None:
        if requested != exact_client_size or actual_client_size != exact_client_size:
            _fail("%s did not request and reach its exact client viewport" % name)
    elif requested != actual_client_size:
        _fail("%s content-driven requested and actual client sizes differ" % name)
    if not _contains(frame, client):
        _fail("%s frame does not contain its client geometry" % name)
    if not _contains(available, frame):
        _fail("%s frame is outside its recorded available screen" % name)
    if record.get("capture_region") != "native-frame":
        _fail("%s is not a native-frame capture" % name)
    if (
        record.get("capture_method")
        != "QScreen.grabWindow(desktop); physical frame crop"
    ):
        _fail("%s has an unexpected capture method" % name)
    probe = record.get("client_paint_probe_pixel_size")
    if not isinstance(probe, list) or len(probe) != 2 or min(probe) < 1:
        _fail("%s has no valid client paint probe" % name)
    probe_dpr = float(record.get("client_paint_probe_device_pixel_ratio", 0))
    expected_probe = [round(client[2] * probe_dpr), round(client[3] * probe_dpr)]
    if probe_dpr <= 0 or probe != expected_probe:
        _fail("%s client paint probe geometry/DPR is inconsistent" % name)
    return frame


def _validate_unavailable_scenario(record: dict[str, Any], expected_scale: str) -> None:
    name = record.get("name")
    if name not in CAPABILITY_QUALIFIED_SCENARIOS:
        _fail("%s cannot be capability-unavailable" % name)
    if str(expected_scale) != "1.5":
        _fail("capability-unavailable scenarios are allowed only at scale 1.5")
    if record.get("status") != "capability-unavailable":
        _fail("%s has an invalid unavailable status" % name)
    if (
        record.get("reason")
        != "required native frame exceeds available screen geometry"
    ):
        _fail("%s has an invalid unavailable reason" % name)
    expected_client = EXPECTED_SCENARIO_CONTRACTS[name][1]
    if expected_client is None:
        _fail("%s has no exact client contract" % name)
    if record.get("requested_client_size") != expected_client:
        _fail("%s has the wrong unavailable client request" % name)
    margins = record.get("frame_margins")
    if not isinstance(margins, dict):
        _fail("%s has no native frame margins" % name)
    try:
        margin_values = [
            int(margins[key]) for key in ("left", "top", "right", "bottom")
        ]
    except (KeyError, TypeError, ValueError):
        _fail("%s has malformed native frame margins" % name)
    if min(margin_values) < 0:
        _fail("%s has negative native frame margins" % name)
    required = [
        expected_client[0] + margin_values[0] + margin_values[2],
        expected_client[1] + margin_values[1] + margin_values[3],
    ]
    if record.get("required_frame_size") != required:
        _fail("%s has inconsistent required frame geometry" % name)
    available = _rect(record, "available_screen_geometry")
    if required[0] <= available[2] and required[1] <= available[3]:
        _fail("%s was marked unavailable even though its native frame fits" % name)


def validate_evidence(
    root: Path, expected_platform: str, expected_scale: str
) -> dict[str, Any]:
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail("manifest.json is missing or unreadable: %s" % exc)

    if manifest.get("schema_version") != 2:
        _fail("unexpected manifest schema version")
    if manifest.get("platform_plugin") != expected_platform:
        _fail("platform plugin does not match the package target")
    if str(manifest.get("scale_factor_environment")) != str(expected_scale):
        _fail("scale factor does not match the requested package run")
    if str(expected_scale) not in {"1.0", "1.5"}:
        _fail("unexpected release scale")
    if str(manifest.get("machine", "")).lower() not in {"amd64", "x86_64"}:
        _fail("evidence was not generated on x64")

    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list):
        _fail("surfaces must be a list")
    unavailable = manifest.get("unavailable_scenarios")
    if not isinstance(unavailable, list):
        _fail("unavailable_scenarios must be a list")
    surface_names = tuple(record.get("name") for record in surfaces)
    unavailable_names = tuple(record.get("name") for record in unavailable)
    observed_names = surface_names + unavailable_names
    if len(observed_names) != len(set(observed_names)) or set(observed_names) != set(
        EXPECTED_SCENARIOS
    ):
        _fail(
            "scenario membership is %r plus unavailable %r, expected %r"
            % (surface_names, unavailable_names, EXPECTED_SCENARIOS)
        )
    expected_surface_order = tuple(
        name for name in EXPECTED_SCENARIOS if name in surface_names
    )
    if surface_names != expected_surface_order:
        _fail(
            "available scenario order is %r, expected %r"
            % (surface_names, expected_surface_order)
        )
    for record in unavailable:
        _validate_unavailable_scenario(record, expected_scale)

    expected_files = {
        "manifest.json",
        "HUMAN_REVIEW.md",
        "intrinsic-ratio-evidence.png",
    }
    for record in surfaces:
        frame = _validate_scenario_semantics(record)
        relative = record.get("screenshot")
        expected_relative = "screenshots/%s.png" % record["name"]
        if relative != expected_relative:
            _fail("scenario %s has unexpected screenshot path" % record["name"])
        expected_files.add(relative)
        path = root / relative
        if not path.is_file():
            _fail("missing screenshot %s" % relative)
        if _sha256(path) != record.get("sha256"):
            _fail("SHA-256 mismatch for %s" % relative)
        dpr = float(record.get("device_pixel_ratio", 0))
        if dpr <= 0:
            _fail("invalid device pixel ratio for %s" % relative)
        expected_pixels = [
            _physical_pixel_extent(frame[2], dpr),
            _physical_pixel_extent(frame[3], dpr),
        ]
        if expected_pixels != record.get("capture_pixel_size"):
            _fail("capture geometry/DPR metadata is inconsistent for %s" % relative)
        _read_nonblank_png(path, expected_pixels)

    artifact = manifest.get("intrinsic_artifact", {})
    artifact_relative = artifact.get("path")
    if artifact_relative != "intrinsic-ratio-evidence.png":
        _fail("unexpected intrinsic artifact path")
    artifact_path = root / artifact_relative
    if _sha256(artifact_path) != artifact.get("sha256"):
        _fail("SHA-256 mismatch for intrinsic artifact")
    _read_nonblank_png(artifact_path, artifact.get("pixel_size"))

    actual_files = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    if actual_files != expected_files:
        _fail(
            "artifact file membership differs; missing=%r extra=%r"
            % (
                sorted(expected_files - actual_files),
                sorted(actual_files - expected_files),
            )
        )
    checklist = root / "HUMAN_REVIEW.md"
    if not checklist.read_text(encoding="utf-8").strip():
        _fail("HUMAN_REVIEW.md is empty")
    return manifest


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument(
        "--platform-plugin", required=True, choices=("windows", "cocoa")
    )
    parser.add_argument("--scale-factor", required=True)
    args = parser.parse_args(argv)
    validate_evidence(args.root, args.platform_plugin, args.scale_factor)
    print("Validated adaptive-layout evidence: %s" % Path(args.root).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
