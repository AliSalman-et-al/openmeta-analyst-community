"""Exercise Results, SVG, plot actions, and Network View on native Qt6."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
import sys
from typing import Any, cast

from rc_metastudio.qt_geometry import logical_extent_to_physical_pixels


SCALE_FACTORS = (1.0, 1.5)
NUMERIC_TOLERANCE = 0.01
MAX_CAPTURE_ATTEMPTS = 5


def _scale_slug(scale: float) -> str:
    return str(scale).replace(".", "_")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_path(root: Path, scale: float) -> Path:
    return root / ("scale-%s.json" % _scale_slug(scale))


def _strict_int(
    value: object,
    name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise ValueError("native Results evidence %s must be an integer" % name)
    result = value
    if minimum is not None and result < minimum:
        raise ValueError("native Results evidence %s is below its minimum" % name)
    if maximum is not None and result > maximum:
        raise ValueError("native Results evidence %s exceeds its maximum" % name)
    return result


def _strict_number(
    value: object,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if type(value) not in (int, float):
        raise ValueError("native Results evidence %s must be a number" % name)
    result = float(cast(int | float, value))
    if not math.isfinite(result):
        raise ValueError("native Results evidence %s must be finite" % name)
    if minimum is not None and result < minimum:
        raise ValueError("native Results evidence %s is below its minimum" % name)
    if maximum is not None and result > maximum:
        raise ValueError("native Results evidence %s exceeds its maximum" % name)
    return result


def _require_close(actual: float, expected: float, name: str) -> None:
    """Require recorded Qt DPR values to agree within 0.01 device pixels."""
    if abs(actual - expected) > NUMERIC_TOLERANCE + 1e-12:
        raise ValueError("native Results evidence %s does not match" % name)


def _require_single_dpr_band(values: list[float]) -> None:
    if max(values) - min(values) > NUMERIC_TOLERANCE + 1e-12:
        raise ValueError("native Results evidence device pixel ratios drifted apart")


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError("native Results evidence JSON contains nonstandard %s" % value)


def _canonical_member(root: Path, value: object, suffix: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("native Results evidence path is not canonical")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or "." in relative.parts
        or ".." in relative.parts
        or any(":" in part for part in relative.parts)
        or str(relative) != value
    ):
        raise ValueError("native Results evidence path is not canonical")
    if relative.suffix.lower() != suffix:
        raise ValueError(
            "native Results evidence member must be a %s file" % suffix.upper()
        )
    resolved = (root / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("native Results evidence path escapes its root")
    if not resolved.is_file():
        raise ValueError("native Results evidence member is missing")
    return resolved


def _rect(value: object, name: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
        raise ValueError("native Results evidence has malformed %s" % name)
    record = cast(dict[str, Any], value)
    return {
        "x": _strict_int(record["x"], "%s x" % name),
        "y": _strict_int(record["y"], "%s y" % name),
        "width": _strict_int(record["width"], "%s width" % name, minimum=1),
        "height": _strict_int(record["height"], "%s height" % name, minimum=1),
    }


def _pixel_size(value: object) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("native Results evidence pixel size is malformed")
    return [
        _strict_int(value[0], "pixel width", minimum=1),
        _strict_int(value[1], "pixel height", minimum=1),
    ]


def _image_has_variation(image: Any) -> bool:
    converted = image.convertToFormat(image.Format.Format_ARGB32)
    if converted.isNull() or converted.width() < 1 or converted.height() < 1:
        return False
    first = converted.pixel(0, 0)
    for y in range(0, converted.height(), max(1, converted.height() // 48)):
        for x in range(0, converted.width(), max(1, converted.width() // 48)):
            if converted.pixel(x, y) != first:
                return True
    return False


def _validate_png_capture(
    root: Path, capture: object, expected_dpr: float
) -> tuple[float, float]:
    from PyQt6 import QtGui

    if not isinstance(capture, dict):
        raise ValueError("native Results evidence capture is malformed")
    capture = cast(dict[str, Any], capture)
    path = _canonical_member(root, capture.get("path"), ".png")
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("native Results evidence is not a readable PNG")
    reader = QtGui.QImageReader(str(path), b"png")
    if not reader.canRead() or reader.format().data().lower() != b"png":
        raise ValueError("native Results evidence is not a readable PNG")
    image = reader.read()
    if image.isNull():
        raise ValueError("native Results evidence is not a readable PNG")
    size_bytes = _strict_int(capture.get("size_bytes"), "capture byte size", minimum=1)
    if size_bytes != len(payload):
        raise ValueError("native Results evidence byte size does not match")
    if capture.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError("native Results evidence hash does not match")
    actual_size = [image.width(), image.height()]
    recorded_size = _pixel_size(capture.get("pixel_size"))
    if recorded_size != actual_size:
        raise ValueError("native Results evidence pixel size does not match")
    dpr = _strict_number(
        capture.get("device_pixel_ratio"), "capture device pixel ratio", minimum=0.01
    )
    _require_close(dpr, expected_dpr, "capture device pixel ratio")
    image_dpr = _strict_number(
        capture.get("image_device_pixel_ratio"),
        "internal image device pixel ratio",
        minimum=0.01,
    )
    _require_close(image_dpr, expected_dpr, "internal image device pixel ratio")
    logical = _rect(capture.get("logical_frame"), "logical frame")
    screen = _rect(capture.get("screen_geometry"), "screen geometry")
    physical = _rect(capture.get("physical_crop"), "physical frame")
    if not (
        screen["x"] <= logical["x"]
        and screen["y"] <= logical["y"]
        and logical["x"] + logical["width"] <= screen["x"] + screen["width"]
        and logical["y"] + logical["height"] <= screen["y"] + screen["height"]
    ):
        raise ValueError("native Results evidence logical frame is outside its screen")
    expected_physical = {
        "x": logical_extent_to_physical_pixels(logical["x"] - screen["x"], dpr),
        "y": logical_extent_to_physical_pixels(logical["y"] - screen["y"], dpr),
        "width": logical_extent_to_physical_pixels(logical["width"], dpr),
        "height": logical_extent_to_physical_pixels(logical["height"], dpr),
    }
    physical_screen_size = [
        logical_extent_to_physical_pixels(screen["width"], dpr),
        logical_extent_to_physical_pixels(screen["height"], dpr),
    ]
    if (
        physical["x"] < 0
        or physical["y"] < 0
        or physical["x"] + physical["width"] > physical_screen_size[0]
        or physical["y"] + physical["height"] > physical_screen_size[1]
    ):
        raise ValueError("native Results evidence physical frame is outside its screen")
    if physical != expected_physical or recorded_size != [
        expected_physical["width"],
        expected_physical["height"],
    ]:
        raise ValueError("native Results evidence physical frame does not match")
    _strict_int(
        capture.get("attempts"),
        "capture attempts",
        minimum=1,
        maximum=MAX_CAPTURE_ATTEMPTS,
    )
    if (
        capture.get("capture_method")
        != "QScreen.grabWindow(desktop); physical frame crop"
    ):
        raise ValueError("native Results evidence capture method is invalid")
    if capture.get("varied_pixels") is not True or not _image_has_variation(image):
        raise ValueError("native Results evidence capture is blank or single-colour")
    return dpr, image_dpr


def validate_evidence(root: Path) -> list[dict[str, object]]:
    """Validate relocated native Results evidence without trusting local paths."""
    records = []
    for scale in SCALE_FACTORS:
        record_path = _record_path(root, scale)
        record = json.loads(
            record_path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_json_constant,
        )
        expected_dpr = scale
        scale_factor = _strict_number(
            record.get("scale_factor"), "scale factor", minimum=0.01
        )
        _require_close(scale_factor, expected_dpr, "scale factor")
        if record.get("qpa") != "windows":
            raise ValueError("native Results evidence was not captured with qwindows")
        device_pixel_ratio = _strict_number(
            record.get("device_pixel_ratio"),
            "top-level device pixel ratio",
            minimum=0.01,
        )
        _require_close(device_pixel_ratio, expected_dpr, "top-level device pixel ratio")
        if record.get("navigation") != [
            "Meta-Analysis Summary",
            "Forest Plot",
            "References",
        ]:
            raise ValueError("native Results evidence has the wrong navigation")
        if record.get("result_text") != {
            "references": "Maintained native Qt6 Results evidence.",
            "summary": "Random-effects model\nEstimate  Lower bound  Upper bound",
        }:
            raise ValueError("native Results evidence has the wrong result text")
        if record.get("plot_capability") != {
            "composition": "single",
            "editable": True,
            "plot_kind": "forest",
            "regenerator": "forest",
            "styleable": True,
        }:
            raise ValueError("native Results evidence has the wrong plot descriptor")
        network = record.get("network")
        if not isinstance(network, dict):
            raise ValueError("native Results evidence has malformed Network View state")
        item_count = _strict_int(
            network.get("item_count"), "network item count", minimum=0
        )
        if {
            "follow_up": network.get("follow_up"),
            "item_count": item_count,
            "outcome": network.get("outcome"),
        } != {
            "follow_up": "12 months",
            "item_count": 1,
            "outcome": "Mortality",
        }:
            raise ValueError("native Results evidence has the wrong Network View state")
        ratio = _strict_number(record.get("plot_ratio"), "plot ratio", minimum=0.01)
        _require_close(ratio, 2.0, "plot ratio")
        captures = record.get("captures")
        if not isinstance(captures, dict) or set(captures) != {"results", "network"}:
            raise ValueError("native Results evidence capture set is incomplete")
        dpr_values = [scale_factor, device_pixel_ratio]
        for capture in captures.values():
            capture_dpr, image_dpr = _validate_png_capture(root, capture, expected_dpr)
            dpr_values.extend((capture_dpr, image_dpr))
        _require_single_dpr_band(dpr_values)
        artifact = _canonical_member(root, record.get("plot_artifact"), ".svg")
        artifact_size = _strict_int(
            record.get("plot_artifact_size"), "Plot Artifact size", minimum=1
        )
        if artifact.stat().st_size != artifact_size:
            raise ValueError("native Results Plot Artifact size does not match")
        if _sha256(artifact) != record.get("plot_artifact_sha256"):
            raise ValueError("native Results Plot Artifact hash does not match")
        artifact_text = artifact.read_text(encoding="utf-8")
        if "Forest Plot 95% confidence interval" not in artifact_text:
            raise ValueError("native Results Plot Artifact lost its readable label")
        if 'stroke="#000000"' not in artifact_text:
            raise ValueError(
                "native Results Plot Artifact lost its confidence interval"
            )
        records.append(record)
    return records


def _capture_window(
    app: Any, window: Any, destination: Path, attempts: int = MAX_CAPTURE_ATTEMPTS
) -> dict[str, object]:
    from PyQt6 import QtCore, QtGui

    last_problem = "window was not exposed"
    for attempt in range(1, attempts + 1):
        screen = window.screen()
        if screen is None:
            last_problem = "window was not attached to a screen"
        elif not window.isVisible() or window.isMinimized():
            last_problem = "window was hidden or minimized"
        else:
            frame = window.frameGeometry()
            screen_geometry = screen.geometry()
            if not screen_geometry.contains(frame):
                last_problem = "window frame did not fit its screen"
            else:
                # Force a synchronous client paint before asking the Windows
                # compositor for the desktop.  qwindows can otherwise block in
                # grabWindow() while a newly shown widget still has a pending
                # paint event.
                paint_probe = window.grab()
                if paint_probe.isNull() or not _image_has_variation(
                    paint_probe.toImage()
                ):
                    last_problem = "window client was not painted"
                    desktop = QtGui.QPixmap()
                else:
                    desktop = screen.grabWindow(0)
                if desktop.isNull():
                    if attempt < attempts:
                        QtCore.QThread.msleep(50)
                        app.processEvents()
                    continue
                dpr = float(desktop.devicePixelRatioF())
                physical = QtCore.QRect(
                    logical_extent_to_physical_pixels(
                        frame.x() - screen_geometry.x(), dpr
                    ),
                    logical_extent_to_physical_pixels(
                        frame.y() - screen_geometry.y(), dpr
                    ),
                    logical_extent_to_physical_pixels(frame.width(), dpr),
                    logical_extent_to_physical_pixels(frame.height(), dpr),
                )
                captured = (
                    desktop.copy(physical) if not desktop.isNull() else QtGui.QPixmap()
                )
                expected_size = [physical.width(), physical.height()]
                actual_size = [captured.width(), captured.height()]
                if captured.isNull() or actual_size != expected_size:
                    last_problem = "desktop crop did not match the physical frame"
                elif not _image_has_variation(captured.toImage()):
                    last_problem = "desktop crop was blank or single-colour"
                else:
                    image_dpr = float(captured.devicePixelRatioF())
                    captured.setDevicePixelRatio(dpr)
                    if not captured.save(str(destination), "PNG"):
                        raise RuntimeError("failed to save native Qt6 frame capture")
                    payload = destination.read_bytes()
                    return {
                        "attempts": attempt,
                        "capture_method": "QScreen.grabWindow(desktop); physical frame crop",
                        "device_pixel_ratio": dpr,
                        "image_device_pixel_ratio": image_dpr,
                        "logical_frame": {
                            "x": frame.x(),
                            "y": frame.y(),
                            "width": frame.width(),
                            "height": frame.height(),
                        },
                        "path": destination.name,
                        "physical_crop": {
                            "x": physical.x(),
                            "y": physical.y(),
                            "width": physical.width(),
                            "height": physical.height(),
                        },
                        "pixel_size": actual_size,
                        "screen_geometry": {
                            "x": screen_geometry.x(),
                            "y": screen_geometry.y(),
                            "width": screen_geometry.width(),
                            "height": screen_geometry.height(),
                        },
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size_bytes": len(payload),
                        "varied_pixels": True,
                    }
        if attempt < attempts:
            QtCore.QThread.msleep(50)
            app.processEvents()
    raise RuntimeError(
        "%s native frame capture failed after %s attempts: %s"
        % (window.objectName() or window.windowTitle(), attempts, last_problem)
    )


def _native_device_pixel_ratio(repo_root: Path) -> float:
    environment = os.environ.copy()
    environment.pop("QT_SCALE_FACTOR", None)
    environment.pop("QT_SCALE_FACTOR_ROUNDING_POLICY", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from PyQt6.QtWidgets import QApplication; "
            "app=QApplication([]); print(app.primaryScreen().devicePixelRatio())",
        ],
        cwd=repo_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return float(completed.stdout.strip().splitlines()[-1])


def _run_scale(scale: float, repo_root: Path, evidence_root: Path) -> None:
    os.environ.setdefault("RCMS_STUB_BACKEND", "1")
    from PyQt6 import QtCore, QtGui, QtWidgets

    from rc_metastudio.qt6_ui import prepare_generated_ui_imports

    prepare_generated_ui_imports()
    from rc_metastudio import r_backend

    r_backend.install_stub_r_bridge()
    from rc_metastudio import app_error_handler, network_view_dialog, results_window
    from rc_metastudio.analysis_results import parse_analysis_result

    evidence_root.mkdir(parents=True, exist_ok=True)
    slug = _scale_slug(scale)
    svg = evidence_root / ("forest-%s.svg" % slug)
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" '
        'viewBox="0 0 800 400"><rect width="800" height="400" fill="white"/>'
        '<line x1="80" y1="210" x2="720" y2="210" stroke="#000000" '
        'stroke-width="4"/><text x="80" y="100" font-size="32">Forest Plot '
        "95% confidence interval</text></svg>",
        encoding="utf-8",
    )
    app = app_error_handler.get_or_create_application([])
    if app.platformName() != "windows":
        raise RuntimeError("native Results smoke requires qwindows")
    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(evidence_root / ("settings-%s" % _scale_slug(scale))),
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    QtCore.QSettings().clear()
    capability = {
        "composition": "single",
        "editable": True,
        "plot_kind": "forest",
        "regenerator": "forest",
        "styleable": True,
    }
    results = results_window.ResultsWindow(
        parse_analysis_result(
            {
                "texts": {
                    "Summary": "Random-effects model\nEstimate  Lower bound  Upper bound",
                    "References": "Maintained native Qt6 Results evidence.",
                },
                "images": {"Forest Plot": str(svg)},
                "display_images": {"Forest Plot": str(svg)},
                "image_params_paths": {"Forest Plot": str(evidence_root / "forest")},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {"Forest Plot": capability},
            }
        )
    )
    network_image = evidence_root / ("network-source-%s.png" % slug)
    source = QtGui.QImage(640, 320, QtGui.QImage.Format.Format_ARGB32)
    source.fill(QtGui.QColor("white"))
    if not source.save(str(network_image), "PNG"):
        raise RuntimeError("failed to create Network View smoke artifact")

    class Model:
        current_outcome = "Mortality"
        dataset = type(
            "Dataset",
            (),
            {
                "get_outcome_names": staticmethod(lambda: ["Mortality"]),
                "get_follow_up_names": staticmethod(lambda: ["12 months"]),
            },
        )()

        def get_current_follow_up_name(self) -> str:
            return "12 months"

        def get_outcome_type(self, _outcome: Any, get_str: bool = False) -> str:
            return "binary"

    setattr(
        network_view_dialog.r_bridge,
        "dataset_to_simple_network",
        lambda **_kwargs: str(network_image),
    )
    network = network_view_dialog.NetworkViewDialog(Model())
    results_image = evidence_root / ("results-%s.png" % slug)
    network_capture = evidence_root / ("network-%s.png" % slug)
    try:
        available = app.primaryScreen().availableGeometry()
        results.setGeometry(
            available.left() + int(available.width() * 0.10),
            available.top() + int(available.height() * 0.10),
            int(available.width() * 0.70),
            int(available.height() * 0.70),
        )
        results.showNormal()
        results.show()
        network.show()
        for _ in range(3):
            app.processEvents()
        if results.isMaximized():
            results.showNormal()
            results.setGeometry(
                available.left() + int(available.width() * 0.10),
                available.top() + int(available.height() * 0.10),
                int(available.width() * 0.70),
                int(available.height() * 0.70),
            )
            for _ in range(3):
                app.processEvents()
        svg_items = [
            item
            for item in results.scene.items()
            if isinstance(item, results_window._svg_item_class())
        ]
        if len(svg_items) != 1 or not svg_items[0].renderer().isValid():
            raise RuntimeError("native Results SVG artifact is not valid")
        plot_rect = svg_items[0].sceneBoundingRect()
        if plot_rect.isEmpty():
            raise RuntimeError("native Results SVG artifact is empty")
        navigation = []
        for index in range(results.nav_tree.topLevelItemCount()):
            item = results.nav_tree.topLevelItem(index)
            if item is None:
                raise RuntimeError("native Results navigation contains a missing item")
            navigation.append(item.text(0))
        if network._network_pixmap_item is None:
            raise RuntimeError("native Network View has no scene item")
        results_capture = _capture_window(app, results, results_image)
        network_capture_record = _capture_window(app, network, network_capture)
        record = {
            "captures": {
                "network": network_capture_record,
                "results": results_capture,
            },
            "device_pixel_ratio": float(results.devicePixelRatioF()),
            "navigation": navigation,
            "network": {
                "follow_up": network.follow_up_cbo_box.currentText(),
                "item_count": len(network.scene.items()),
                "outcome": network.outcome_cbo_box.currentText(),
            },
            "plot_artifact": svg.name,
            "plot_artifact_sha256": _sha256(svg),
            "plot_artifact_size": svg.stat().st_size,
            "plot_capability": capability,
            "plot_ratio": plot_rect.width() / plot_rect.height(),
            "qpa": app.platformName(),
            "result_text": {
                "references": results.references_text,
                "summary": results.texts.get("Summary"),
            },
            "scale_factor": scale,
        }
        _record_path(evidence_root, scale).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    finally:
        network.close()
        results.close()
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    evidence_root = repo_root / "build/qt6-verification/native-results"
    if args.validate_only:
        validate_evidence(evidence_root)
        return 0
    if args.scale is not None:
        _run_scale(args.scale, repo_root, evidence_root)
        return 0
    native_dpr = _native_device_pixel_ratio(repo_root)
    if native_dpr <= 0.0:
        raise RuntimeError("native Qt6 reported an invalid device pixel ratio")
    for scale in SCALE_FACTORS:
        environment = os.environ.copy()
        environment["QT_SCALE_FACTOR"] = str(scale / native_dpr)
        environment["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--scale", str(scale)],
            cwd=repo_root,
            env=environment,
            check=True,
        )
    records = validate_evidence(evidence_root)
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
