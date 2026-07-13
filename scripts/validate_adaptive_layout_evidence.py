# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed validation for packaged adaptive-layout evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PyQt5 import QtGui


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


def _fail(message):
    raise ValueError("Invalid adaptive-layout evidence: %s" % message)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_nonblank_png(path, expected_size=None):
    image = QtGui.QImage(str(path))
    if image.isNull():
        _fail("%s is not a readable PNG" % path.name)
    actual = [image.width(), image.height()]
    if expected_size is not None and actual != list(expected_size):
        _fail("%s has pixel size %s, expected %s" % (path.name, actual, expected_size))
    converted = image.convertToFormat(QtGui.QImage.Format_ARGB32)
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


def _rect(record, field):
    value = record.get(field)
    if not isinstance(value, dict):
        _fail("%s has no %s record" % (record.get("name"), field))
    try:
        rect = tuple(int(value[key]) for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError):
        _fail("%s has malformed %s" % (record.get("name"), field))
    if rect[2] < 1 or rect[3] < 1:
        _fail("%s has empty %s" % (record.get("name"), field))
    return rect


def _contains(outer, inner):
    return (
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[0] + inner[2] <= outer[0] + outer[2]
        and inner[1] + inner[3] <= outer[1] + outer[3]
    )


def _validate_scenario_semantics(record):
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
    if record.get("capture_method") != "QScreen.grabWindow(desktop, frameGeometry)":
        _fail("%s has an unexpected capture method" % name)
    probe = record.get("client_paint_probe_pixel_size")
    if not isinstance(probe, list) or len(probe) != 2 or min(probe) < 1:
        _fail("%s has no valid client paint probe" % name)
    probe_dpr = float(record.get("client_paint_probe_device_pixel_ratio", 0))
    expected_probe = [round(client[2] * probe_dpr), round(client[3] * probe_dpr)]
    if probe_dpr <= 0 or probe != expected_probe:
        _fail("%s client paint probe geometry/DPR is inconsistent" % name)
    return frame


def validate_evidence(root, expected_platform, expected_scale):
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail("manifest.json is missing or unreadable: %s" % exc)

    if manifest.get("schema_version") != 1:
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
    scenarios = tuple(record.get("name") for record in surfaces)
    if scenarios != EXPECTED_SCENARIOS:
        _fail("scenario membership/order is %r, expected %r" % (scenarios, EXPECTED_SCENARIOS))

    expected_files = {"manifest.json", "HUMAN_REVIEW.md", "intrinsic-ratio-evidence.png"}
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
            round(frame[2] * dpr),
            round(frame[3] * dpr),
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
            % (sorted(expected_files - actual_files), sorted(actual_files - expected_files))
        )
    checklist = root / "HUMAN_REVIEW.md"
    if not checklist.read_text(encoding="utf-8").strip():
        _fail("HUMAN_REVIEW.md is empty")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--platform-plugin", required=True, choices=("windows", "cocoa"))
    parser.add_argument("--scale-factor", required=True)
    args = parser.parse_args(argv)
    validate_evidence(args.root, args.platform_plugin, args.scale_factor)
    print("Validated adaptive-layout evidence: %s" % Path(args.root).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
