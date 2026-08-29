"""Fail-closed contract tests for native Qt6 Results evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from PyQt6 import QtCore, QtGui


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "native_results_smoke", ROOT / "scripts/native_results_smoke.py"
)
assert SPEC is not None and SPEC.loader is not None
native_results_smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native_results_smoke)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_png(path: Path, width: int, height: int, *, blank: bool = False) -> None:
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("white"))
    if not blank:
        painter = QtGui.QPainter(image)
        painter.fillRect(
            width // 4, height // 4, width // 2, height // 2, QtGui.QColor("navy")
        )
        painter.end()
    assert image.save(str(path), "PNG")


def _valid_bundle(root: Path) -> None:
    capability = {
        "composition": "single",
        "editable": True,
        "plot_kind": "forest",
        "regenerator": "forest",
        "styleable": True,
    }
    for scale in native_results_smoke.SCALE_FACTORS:
        slug = str(scale).replace(".", "_")
        artifact = root / f"forest-{slug}.svg"
        artifact.write_text(
            '<svg><line stroke="#000000"/><text>Forest Plot 95% confidence interval</text></svg>',
            encoding="utf-8",
        )
        captures = {}
        for name in ("results", "network"):
            path = root / f"{name}-{slug}.png"
            width = native_results_smoke.logical_extent_to_physical_pixels(100.0, scale)
            height = native_results_smoke.logical_extent_to_physical_pixels(80.0, scale)
            _write_png(path, width, height)
            captures[name] = {
                "attempts": 1,
                "capture_method": "QScreen.grabWindow(desktop); physical frame crop",
                "device_pixel_ratio": scale,
                "image_device_pixel_ratio": scale,
                "logical_frame": {"x": 10, "y": 20, "width": 100, "height": 80},
                "path": path.name,
                "physical_crop": {
                    "x": native_results_smoke.logical_extent_to_physical_pixels(
                        10.0, scale
                    ),
                    "y": native_results_smoke.logical_extent_to_physical_pixels(
                        20.0, scale
                    ),
                    "width": width,
                    "height": height,
                },
                "pixel_size": [width, height],
                "screen_geometry": {"x": 0, "y": 0, "width": 1600, "height": 1000},
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "varied_pixels": True,
            }
        record = {
            "captures": captures,
            "device_pixel_ratio": scale,
            "navigation": ["Meta-Analysis Summary", "Forest Plot", "References"],
            "network": {
                "follow_up": "12 months",
                "item_count": 1,
                "outcome": "Mortality",
            },
            "plot_artifact": artifact.name,
            "plot_artifact_sha256": _sha256(artifact),
            "plot_artifact_size": artifact.stat().st_size,
            "plot_capability": capability,
            "plot_ratio": 2.0,
            "qpa": "windows",
            "result_text": {
                "references": "Maintained native Qt6 Results evidence.",
                "summary": "Random-effects model\nEstimate  Lower bound  Upper bound",
            },
            "scale_factor": scale,
        }
        native_results_smoke._record_path(root, scale).write_text(
            json.dumps(record), encoding="utf-8"
        )


def _record(root: Path, scale: float = 1.0) -> tuple[Path, dict]:
    path = native_results_smoke._record_path(root, scale)
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_native_results_evidence_accepts_exact_nonblank_png_bundle(tmp_path):
    _valid_bundle(tmp_path)

    records = native_results_smoke.validate_evidence(tmp_path)

    assert [record["scale_factor"] for record in records] == [1.0, 1.5]


def test_native_results_evidence_rejects_invalid_numeric_types_ranges_and_mismatches(
    tmp_path,
):
    cases = (
        ("bool-scale", ("scale_factor",), True),
        ("string-scale", ("scale_factor",), "1.0"),
        ("null-scale", ("scale_factor",), None),
        ("mismatched-scale", ("scale_factor",), 1.1),
        ("zero-top-dpr", ("device_pixel_ratio",), 0),
        ("mismatched-top-dpr", ("device_pixel_ratio",), 1.1),
        ("mismatched-capture-dpr", ("captures", "results", "device_pixel_ratio"), 1.1),
        (
            "mismatched-image-dpr",
            ("captures", "results", "image_device_pixel_ratio"),
            1.1,
        ),
        ("bool-attempts", ("captures", "results", "attempts"), True),
        ("float-attempts", ("captures", "results", "attempts"), 1.0),
        ("zero-attempts", ("captures", "results", "attempts"), 0),
        ("excess-attempts", ("captures", "results", "attempts"), 6),
        ("string-ratio", ("plot_ratio",), "2.0"),
        ("float-artifact-size", ("plot_artifact_size",), 1.0),
        ("bool-item-count", ("network", "item_count"), True),
        ("bool-pixel-width", ("captures", "results", "pixel_size", 0), True),
        ("float-pixel-width", ("captures", "results", "pixel_size", 0), 100.0),
        ("negative-pixel-width", ("captures", "results", "pixel_size", 0), -1),
        ("float-logical-x", ("captures", "results", "logical_frame", "x"), 10.0),
        ("zero-logical-width", ("captures", "results", "logical_frame", "width"), 0),
        ("outside-logical-x", ("captures", "results", "logical_frame", "x"), -1),
        ("negative-physical-x", ("captures", "results", "physical_crop", "x"), -1),
        ("outside-physical-x", ("captures", "results", "physical_crop", "x"), 2000),
        ("zero-screen-width", ("captures", "results", "screen_geometry", "width"), 0),
        ("null-byte-size", ("captures", "results", "size_bytes"), None),
    )
    for label, keys, value in cases:
        root = tmp_path / label
        root.mkdir()
        _valid_bundle(root)
        path, record = _record(root)
        target = record
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
        path.write_text(json.dumps(record), encoding="utf-8")
        with pytest.raises(ValueError):
            native_results_smoke.validate_evidence(root)


def test_native_results_evidence_json_rejects_nan_and_infinity_constants(tmp_path):
    for token in ("NaN", "Infinity", "-Infinity"):
        root = tmp_path / token.replace("-", "negative-")
        root.mkdir()
        _valid_bundle(root)
        path, record = _record(root)
        text = json.dumps(record).replace(
            '"scale_factor": 1.0', f'"scale_factor": {token}'
        )
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="nonstandard"):
            native_results_smoke.validate_evidence(root)


def test_native_results_evidence_rejects_chained_dpr_drift_reproduction(tmp_path):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    record["scale_factor"] = 1.009
    record["device_pixel_ratio"] = 1.018
    record["captures"]["results"]["device_pixel_ratio"] = 0.991
    record["captures"]["results"]["image_device_pixel_ratio"] = 0.982
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="pixel ratio|drifted apart"):
        native_results_smoke.validate_evidence(tmp_path)
    with pytest.raises(ValueError, match="drifted apart"):
        native_results_smoke._require_single_dpr_band([1.009, 1.018, 0.991, 0.982])


def test_native_results_evidence_accepts_values_on_single_tolerance_boundary(tmp_path):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    record["scale_factor"] = 1.01
    record["device_pixel_ratio"] = 1.01
    path.write_text(json.dumps(record), encoding="utf-8")

    native_results_smoke.validate_evidence(tmp_path)


def test_native_results_evidence_uses_exact_capture_dpr_for_physical_geometry(
    tmp_path,
):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    record["scale_factor"] = 1.009
    record["device_pixel_ratio"] = 1.009
    capture = record["captures"]["results"]
    capture["device_pixel_ratio"] = 1.009
    capture["image_device_pixel_ratio"] = 1.009
    width = native_results_smoke.logical_extent_to_physical_pixels(100, 1.009)
    height = native_results_smoke.logical_extent_to_physical_pixels(80, 1.009)
    image = tmp_path / capture["path"]
    _write_png(image, width, height)
    capture["pixel_size"] = [width, height]
    capture["physical_crop"] = {
        "x": native_results_smoke.logical_extent_to_physical_pixels(10, 1.009),
        "y": native_results_smoke.logical_extent_to_physical_pixels(20, 1.009),
        "width": width,
        "height": height,
    }
    capture["size_bytes"] = image.stat().st_size
    capture["sha256"] = _sha256(image)
    path.write_text(json.dumps(record), encoding="utf-8")

    native_results_smoke.validate_evidence(tmp_path)

    capture["physical_crop"]["width"] = 100
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="physical frame"):
        native_results_smoke.validate_evidence(tmp_path)


@pytest.mark.parametrize(
    "bad_path", ["../results.png", "./results.png", "/results.png", "results.jpg"]
)
def test_native_results_evidence_rejects_noncanonical_or_non_png_paths(
    tmp_path, bad_path
):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    record["captures"]["results"]["path"] = bad_path
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical|PNG"):
        native_results_smoke.validate_evidence(tmp_path)


def test_native_results_evidence_rejects_corrupted_png_even_with_matching_bytes(
    tmp_path,
):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    image = tmp_path / record["captures"]["results"]["path"]
    image.write_bytes(b"not a png")
    record["captures"]["results"]["size_bytes"] = image.stat().st_size
    record["captures"]["results"]["sha256"] = _sha256(image)
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="readable PNG"):
        native_results_smoke.validate_evidence(tmp_path)


def test_native_results_evidence_rejects_blank_capture_with_matching_metadata(tmp_path):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    capture = record["captures"]["results"]
    image = tmp_path / capture["path"]
    _write_png(image, *capture["pixel_size"], blank=True)
    capture["size_bytes"] = image.stat().st_size
    capture["sha256"] = _sha256(image)
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="blank|single-colour"):
        native_results_smoke.validate_evidence(tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("pixel_size", [99, 80], "pixel size"),
        ("device_pixel_ratio", 1.25, "pixel ratio"),
        ("sha256", "0" * 64, "hash"),
        (
            "physical_crop",
            {"x": 10, "y": 20, "width": 99, "height": 80},
            "physical frame",
        ),
    ),
)
def test_native_results_evidence_rejects_dimension_dpr_hash_and_frame_tampering(
    tmp_path, field, value, message
):
    _valid_bundle(tmp_path)
    path, record = _record(tmp_path)
    record["captures"]["results"][field] = value
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        native_results_smoke.validate_evidence(tmp_path)


def test_native_results_capture_retries_blank_desktop_until_frame_is_painted(
    qapp, tmp_path
):
    blank = QtGui.QPixmap(120, 100)
    blank.fill(QtGui.QColor("white"))
    painted = QtGui.QPixmap(blank.size())
    painted.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(painted)
    painter.fillRect(20, 20, 30, 20, QtGui.QColor("navy"))
    painter.end()

    class Screen:
        grabs = iter((blank, painted))

        def geometry(self):
            return QtCore.QRect(0, 0, 120, 100)

        def grabWindow(self, _window_id):
            return next(self.grabs)

    class Window:
        def grab(self):
            return painted

        def screen(self):
            return Screen()

        def isVisible(self):
            return True

        def isMinimized(self):
            return False

        def frameGeometry(self):
            return QtCore.QRect(10, 10, 60, 50)

        def objectName(self):
            return "ResultsWindow"

        def windowTitle(self):
            return "Results"

    metadata = native_results_smoke._capture_window(
        qapp, Window(), tmp_path / "capture.png", attempts=3
    )

    assert metadata["attempts"] == 2
    assert metadata["pixel_size"] == [60, 50]
    assert metadata["varied_pixels"] is True


@pytest.mark.parametrize("failure", ["minimized", "mismatched", "blank"])
def test_native_results_capture_fails_closed_after_bounded_attempts(
    qapp, tmp_path, failure
):
    desktop = QtGui.QPixmap(120, 100)
    desktop.fill(QtGui.QColor("white"))
    client = QtGui.QPixmap(desktop.size())
    client.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(client)
    painter.fillRect(10, 10, 20, 20, QtGui.QColor("navy"))
    painter.end()

    class Screen:
        def geometry(self):
            return QtCore.QRect(0, 0, 120, 100)

        def grabWindow(self, _window_id):
            return desktop

    class Window:
        def grab(self):
            return client

        def screen(self):
            return Screen()

        def isVisible(self):
            return True

        def isMinimized(self):
            return failure == "minimized"

        def frameGeometry(self):
            if failure == "mismatched":
                return QtCore.QRect(110, 90, 60, 50)
            return QtCore.QRect(10, 10, 60, 50)

        def objectName(self):
            return "ResultsWindow"

        def windowTitle(self):
            return "Results"

    with pytest.raises(RuntimeError, match="after 2 attempts"):
        native_results_smoke._capture_window(
            qapp, Window(), tmp_path / "capture.png", attempts=2
        )
