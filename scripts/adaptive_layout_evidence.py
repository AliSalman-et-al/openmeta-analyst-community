# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture human-reviewable native evidence for the adaptive-layout release gate."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from rc_metastudio import adaptive_window
from rc_metastudio.analysis_results import parse_analysis_result


EVIDENCE_SCHEMA_VERSION = 2
CONSTRAINED_WORKSPACE = QtCore.QSize(800, 600)
FULL_USABILITY_WORKSPACE = QtCore.QSize(1024, 640)
NON_NATIVE_PLUGINS = {"offscreen", "minimal", "minimalegl", "vnc"}
EXPECTED_NATIVE_PLUGINS = {"win32": "windows", "darwin": "cocoa"}
EXPECTED_NATIVE_ARCHITECTURES = {
    "win32": {"amd64", "x86_64"},
    "darwin": {"arm64"},
}
EXPECTED_NATIVE_ARCHITECTURE_LABELS = {"win32": "x64", "darwin": "Apple silicon arm64"}


def _normalized_platform_value(value, fallback):
    return str(value or fallback).strip().lower()


def _requested_scale_factor():
    """Return the absolute evidence scale, separate from Qt's multiplier."""
    return os.environ.get(
        "RCMS_ADAPTIVE_LAYOUT_SCALE",
        os.environ.get("QT_SCALE_FACTOR", "native"),
    )


def configure_isolated_evidence_settings(output_dir):
    """Keep package verification from reading or overwriting user geometry."""
    settings_root = Path(output_dir).resolve() / "settings"
    settings_root.mkdir(parents=True, exist_ok=True)
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(settings_root),
    )


def validate_native_platform(platform_plugin=None, system=None, machine=None):
    """Fail closed when a supported-platform run cannot prove native paint."""
    plugin = _normalized_platform_value(
        platform_plugin, QtGui.QGuiApplication.platformName()
    )
    host = _normalized_platform_value(system, sys.platform)
    architecture = _normalized_platform_value(machine, platform.machine())
    expected = EXPECTED_NATIVE_PLUGINS.get(host)
    expected_architectures = EXPECTED_NATIVE_ARCHITECTURES.get(host, ())
    expected_architecture = EXPECTED_NATIVE_ARCHITECTURE_LABELS.get(host, "")
    failures = (
        (
            plugin in NON_NATIVE_PLUGINS,
            "Adaptive-layout package evidence requires a native Qt platform "
            "plugin; got %s." % plugin,
        ),
        (
            expected is None,
            "Adaptive-layout package evidence is release-gated only on Windows "
            "x64 and Apple silicon macOS; got %s." % host,
        ),
        (
            expected is not None and plugin != expected,
            "Adaptive-layout package evidence expected Qt platform %s on %s; "
            "got %s." % (expected, host, plugin),
        ),
        (
            bool(expected_architectures) and architecture not in expected_architectures,
            "Adaptive-layout package evidence requires an %s host; got %s."
            % (expected_architecture, architecture),
        ),
    )
    for failed, message in failures:
        if failed:
            raise RuntimeError(message)
    return plugin


def run_native_adaptive_layout_evidence(app, main_window, sample_path, output_dir):
    """Exercise representative native surfaces and write screenshots + manifest."""
    output = Path(output_dir).resolve()
    screenshots = output / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    plugin = validate_native_platform()

    sample = Path(sample_path).resolve()
    if not main_window.open(str(sample)):
        raise RuntimeError(
            "Could not open adaptive-layout evidence project: %s" % sample
        )
    _flush(app)
    model = main_window.tableView.model()
    if model is None or model.rowCount() < 1:
        raise RuntimeError(
            "Adaptive-layout evidence project opened without table rows."
        )

    from rc_metastudio import about_legal_dialog
    from rc_metastudio import main_wizard
    from rc_metastudio import progress_dialog
    from rc_metastudio import results_window
    from rc_metastudio import settings

    plot_path, results = _create_results_surface(results_window, main_window, output)
    workflow = main_wizard.MainWizard(path="new_dataset", parent=main_window)
    transactional = about_legal_dialog.AboutLegalDialog(parent=main_window)
    transient = progress_dialog.AnalysisProgressDialog(parent=main_window)
    transient.setWindowTitle("Adaptive layout verification")
    transient.progress_bar.setRange(0, 100)
    transient.progress_bar.setValue(45)
    transient.progress_bar.setFormat("45%")
    surfaces = [
        ("main-workspace", "workspace", main_window),
        ("results-workspace", "workspace", results),
        ("new-dataset-workflow", "workflow", workflow),
        ("about-legal", "transactional", transactional),
        ("analysis-progress", "transient", transient),
    ]

    try:
        records, unavailable_scenarios = _capture_workspace_scenarios(
            app, main_window, surfaces[:2], screenshots
        )
        records.extend(
            _capture_owned_surfaces(app, main_window, surfaces[2:], screenshots)
        )

        runtime_resize = _exercise_runtime_resize(app, main_window)
        remembered_geometry = _exercise_remembered_geometry(main_window, settings)
        splitter = _exercise_results_splitter(app, results)
        intrinsic_artifact = _intrinsic_artifact_record(results, plot_path)
        table_record = _table_record(main_window, model)
    finally:
        for _name, _archetype, window in reversed(surfaces[1:]):
            window.close()
        main_window.close()
        _flush(app)

    shutil.rmtree(output / "settings", ignore_errors=True)

    manifest = _evidence_manifest(
        app,
        plugin,
        table_record,
        splitter,
        intrinsic_artifact,
        remembered_geometry,
        runtime_resize,
        records,
        unavailable_scenarios,
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "HUMAN_REVIEW.md").write_text(
        _human_review_template(manifest), encoding="utf-8"
    )
    return manifest


def _create_results_surface(results_window, main_window, output):
    plot_path = _create_intrinsic_ratio_artifact(output)
    result = parse_analysis_result(
        {
            "version": 1,
            "texts": {
                "Summary": (
                    "Native adaptive-layout package evidence\n\n"
                    "Required Content remains readable while the Results navigation "
                    "and content panes are resized independently."
                )
            },
            "images": {"Aspect-Ratio Plot": str(plot_path)},
            "display_images": {"Aspect-Ratio Plot": str(plot_path)},
            "plot_capabilities": {
                "Aspect-Ratio Plot": {
                    "plot_kind": "other",
                    "editable": False,
                    "styleable": False,
                    "regenerator": "none",
                    "composition": "single",
                }
            },
            "sections": [
                {
                    "id": "adaptive.summary",
                    "kind": "text",
                    "order": 0,
                    "title": "Summary",
                    "source_key": "Summary",
                },
                {
                    "id": "adaptive.aspect-ratio-plot",
                    "kind": "image",
                    "order": 1,
                    "title": "Aspect-Ratio Plot",
                    "source_key": "Aspect-Ratio Plot",
                },
            ],
        }
    )
    return plot_path, results_window.ResultsWindow(result, parent=main_window)


def _capture_workspace_scenarios(app, main_window, surfaces, screenshots):
    records = []
    unavailable_scenarios = []
    viewports = (
        ("constrained", CONSTRAINED_WORKSPACE),
        ("full-usability", FULL_USABILITY_WORKSPACE),
    )
    for viewport_name, viewport in viewports:
        for surface_name, _archetype, window in surfaces:
            scenario_name = "%s-%s" % (surface_name, viewport_name)
            unavailable = _exact_client_size_unavailability(
                app, window, viewport, scenario_name
            )
            if unavailable is not None:
                if viewport != FULL_USABILITY_WORKSPACE:
                    raise RuntimeError(
                        "%s is required even on a constrained native screen."
                        % scenario_name
                    )
                unavailable_scenarios.append(unavailable)
                continue
            _show_at_exact_client_size(app, window, viewport)
            if window is main_window:
                _exercise_main_workspace(main_window)
            records.append(
                _capture_surface(
                    app, window, screenshots, scenario_name, "workspace", viewport
                )
            )
    return records, unavailable_scenarios


def _capture_owned_surfaces(app, main_window, surfaces, screenshots):
    _show_at_exact_client_size(app, main_window, CONSTRAINED_WORKSPACE)
    records = []
    for surface_name, archetype, window in surfaces:
        _show_content_driven_surface(app, window, archetype)
        records.append(
            _capture_surface(
                app,
                window,
                screenshots,
                "%s-constrained-owner" % surface_name,
                archetype,
                window.size(),
                owning_workspace_client_size=CONSTRAINED_WORKSPACE,
            )
        )
        window.hide()
        _flush(app)
    return records


def _table_record(main_window, model):
    return {
        "rows": model.rowCount(),
        "columns": model.columnCount(),
        "column_widths": [
            main_window.tableView.columnWidth(index)
            for index in range(model.columnCount())
        ],
    }


def _evidence_manifest(
    app,
    plugin,
    table,
    splitter,
    intrinsic_artifact,
    remembered_geometry,
    runtime_resize,
    surfaces,
    unavailable_scenarios,
):
    screen = app.primaryScreen()
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "qt": QtCore.QT_VERSION_STR,
        "pyqt": QtCore.PYQT_VERSION_STR,
        "platform_plugin": plugin,
        "scale_factor_environment": _requested_scale_factor(),
        "screen": _screen_record(screen),
        "logical_dpi": round(screen.logicalDotsPerInch(), 2),
        "device_pixel_ratio": round(screen.devicePixelRatio(), 2),
        "font": _font_record(app.font()),
        "icon_available": not app.windowIcon().isNull(),
        "table": table,
        "splitter": splitter,
        "intrinsic_artifact": intrinsic_artifact,
        "remembered_geometry": remembered_geometry,
        "runtime_resize": runtime_resize,
        "surfaces": surfaces,
        "unavailable_scenarios": unavailable_scenarios,
        "human_review": {
            "status": "required",
            "method": "manual screenshot review; no pixel-diff gate",
            "checklist": [
                "professional reflow and appropriate spacing",
                "readable Required Content",
                "reachable primary actions",
                "undistorted visual artifacts",
                "native fonts, icons, paint, and window chrome",
            ],
        },
    }


def _show_at_exact_client_size(app, window, requested):
    available, margins = _normalize_window_for_exact_size(app, window)
    required_width = requested.width() + margins.left() + margins.right()
    required_height = requested.height() + margins.top() + margins.bottom()
    if available.width() < required_width or available.height() < required_height:
        raise RuntimeError(
            "Native display cannot reach required %sx%s client viewport for %s; "
            "available frame area is %sx%s."
            % (
                requested.width(),
                requested.height(),
                window.objectName() or window.windowTitle(),
                available.width(),
                available.height(),
            )
        )
    # layout-audit: allow=verification-layout-fixture; reason=native package evidence exercises agreed logical viewports
    window.resize(requested)
    _flush(app)
    frame = window.frameGeometry()
    if not available.contains(frame):
        target_frame = QtCore.QRect(frame)
        target_frame.moveTopLeft(available.topLeft())
        # layout-audit: allow=verification-layout-fixture; reason=native evidence positions an exact viewport fully within the owning display
        window.move(target_frame.topLeft())
        _flush(app)
    if window.size() != requested:
        raise RuntimeError(
            "%s requested %sx%s client viewport but reached %sx%s."
            % (
                window.objectName() or window.windowTitle(),
                requested.width(),
                requested.height(),
                window.width(),
                window.height(),
            )
        )
    _assert_screen_reachable(window)


def _normalize_window_for_exact_size(app, window):
    screen = window.screen() or app.primaryScreen()
    available = screen.availableGeometry()
    window.setWindowState(
        window.windowState()
        & ~QtCore.Qt.WindowState.WindowMaximized
        & ~QtCore.Qt.WindowState.WindowFullScreen
    )
    window.showNormal()
    window.show()
    _flush(app)
    # Workspace first-show placement can reapply a remembered/default maximized
    # state after the initial normalization, particularly through Cocoa.  The
    # evidence viewport owns geometry here, so normalize once more after those
    # callbacks have run before requesting the exact client size.
    window.setWindowState(
        window.windowState()
        & ~QtCore.Qt.WindowState.WindowMaximized
        & ~QtCore.Qt.WindowState.WindowFullScreen
    )
    window.showNormal()
    _flush(app)
    margins = window.windowHandle().frameMargins()
    return available, margins


def _exact_client_size_unavailability(app, window, requested, scenario_name):
    available, margins = _normalize_window_for_exact_size(app, window)
    required = QtCore.QSize(
        requested.width() + margins.left() + margins.right(),
        requested.height() + margins.top() + margins.bottom(),
    )
    if (
        available.width() >= required.width()
        and available.height() >= required.height()
    ):
        return None
    return {
        "name": scenario_name,
        "status": "capability-unavailable",
        "reason": "required native frame exceeds available screen geometry",
        "requested_client_size": [requested.width(), requested.height()],
        "required_frame_size": [required.width(), required.height()],
        "available_screen_geometry": _rect_record(available),
        "frame_margins": {
            "left": margins.left(),
            "top": margins.top(),
            "right": margins.right(),
            "bottom": margins.bottom(),
        },
    }


def _show_content_driven_surface(app, window, archetype):
    if isinstance(window, QtWidgets.QWizard):
        window.restart()
    # layout-audit: allow=verification-layout-fixture; reason=native evidence records each content-driven archetype at its layout-derived preferred size
    window.adjustSize()
    window.show()
    window.raise_()
    window.activateWindow()
    _flush(app)
    _assert_screen_reachable(window)
    _assert_multiline_tool_button_content(window)


def _capture_surface(
    app,
    window,
    screenshots,
    name,
    archetype,
    requested_client_size,
    owning_workspace_client_size=None,
):
    window.raise_()
    window.activateWindow()
    window.repaint()
    _flush(app)
    actual_archetype = adaptive_window.adaptive_window_state(
        window
    ).policy.archetype.value
    if actual_archetype != archetype:
        raise RuntimeError(
            "%s declared %s, expected %s." % (name, actual_archetype, archetype)
        )
    screen = window.screen() or app.primaryScreen()
    if not window.isVisible() or window.isMinimized():
        raise RuntimeError("%s is not visibly painted for native capture." % name)
    handle = window.windowHandle()
    if handle is None or not handle.isExposed():
        raise RuntimeError("%s has no exposed native window for capture." % name)
    paint_probe = window.grab()
    if paint_probe.isNull() or paint_probe.width() < 1 or paint_probe.height() < 1:
        raise RuntimeError("%s did not produce a painted client image." % name)
    pixmap = _grab_painted_native_frame(app, screen, window)
    if pixmap.isNull() or pixmap.width() < 1 or pixmap.height() < 1:
        raise RuntimeError("QScreen.grabWindow could not capture %s." % name)
    filename = "%s.png" % name
    path = screenshots / filename
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError("Could not save native screenshot: %s" % path)
    payload = path.read_bytes()
    return {
        "name": name,
        "archetype": archetype,
        "requested_client_size": [
            requested_client_size.width(),
            requested_client_size.height(),
        ],
        "owning_workspace_client_size": (
            [
                owning_workspace_client_size.width(),
                owning_workspace_client_size.height(),
            ]
            if owning_workspace_client_size is not None
            else None
        ),
        "actual_frame_geometry": _rect_record(window.frameGeometry()),
        "actual_client_geometry": _rect_record(window.geometry()),
        "available_screen_geometry": _rect_record(screen.availableGeometry()),
        "window_chrome": _window_chrome_record(window),
        "screen": screen.name(),
        "device_pixel_ratio": round(pixmap.devicePixelRatio(), 2),
        "capture_pixel_size": [pixmap.width(), pixmap.height()],
        "client_paint_probe_pixel_size": [paint_probe.width(), paint_probe.height()],
        "client_paint_probe_device_pixel_ratio": round(
            paint_probe.devicePixelRatio(), 2
        ),
        "font": _font_record(window.font()),
        "screenshot": str(path.relative_to(screenshots.parent)).replace("\\", "/"),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "capture_region": "native-frame",
        "capture_method": "QScreen.grabWindow(window); native frame capture",
    }


def _grab_native_frame(screen, window):
    frame = window.frameGeometry()
    margins = window.windowHandle().frameMargins()
    captured = screen.grabWindow(
        window.winId(),
        -margins.left(),
        -margins.top(),
        frame.width(),
        frame.height(),
    )
    return captured


def _grab_painted_native_frame(app, screen, window, attempts=5):
    """Wait for the compositor to expose real frame pixels before accepting a grab."""
    pixmap = QtGui.QPixmap()
    for attempt in range(attempts):
        # qwindows can expose the native window before its first paint has
        # reached the desktop compositor.  Request a synchronous client paint
        # and pump its events before every native grab; otherwise retries can
        # repeatedly sample the same stale blank frame.
        window.update()
        window.repaint()
        _flush(app)
        pixmap = _grab_native_frame(screen, window)
        if not pixmap.isNull() and _pixmap_has_pixel_variation(pixmap):
            return pixmap
        if attempt + 1 < attempts:
            QtCore.QThread.msleep(50)
    raise RuntimeError(
        "%s native frame remained blank after %s compositor capture attempts."
        % (window.objectName() or window.windowTitle(), attempts)
    )


def _pixmap_has_pixel_variation(pixmap):
    if pixmap.isNull() or pixmap.width() < 1 or pixmap.height() < 1:
        return False
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    first = image.pixel(0, 0)
    for y in range(0, image.height(), max(1, image.height() // 32)):
        for x in range(0, image.width(), max(1, image.width() // 32)):
            if image.pixel(x, y) != first:
                return True
    return False


def _exercise_main_workspace(window):
    if (
        window.tableView.viewport().width() < 1
        or window.tableView.viewport().height() < 1
    ):
        raise RuntimeError("Main Workspace table viewport is not reachable.")
    application = QtWidgets.QApplication.instance()
    if not isinstance(application, QtWidgets.QApplication):
        raise RuntimeError("Native package evidence requires QApplication")
    if window.windowIcon().isNull() and application.windowIcon().isNull():
        raise RuntimeError("Native package evidence did not load the application icon.")


def _exercise_runtime_resize(app, window):
    before = _rect_record(window.frameGeometry())
    # layout-audit: allow=verification-layout-fixture; reason=native evidence verifies user-owned runtime resizing
    window.resize(800, 600)
    _flush(app)
    after = _rect_record(window.frameGeometry())
    if (
        window.tableView.viewport().width() < 1
        or window.tableView.viewport().height() < 1
    ):
        raise RuntimeError(
            "Main Workspace table became unreachable after runtime resize."
        )
    return {"before": before, "after": after, "table_reachable": True}


def _exercise_remembered_geometry(window, settings_module):
    available = window.screen().availableGeometry()
    saved_frame = settings_module._workspace_normal_frame(window)
    expected_frame = settings_module._screen_safe_geometry(saved_frame, [available])
    expected_state = {
        "maximized": window.isMaximized(),
        "full_screen": window.isFullScreen(),
    }
    settings_module.save_main_window_placement(
        window, window.tableView.column_width_state()
    )
    loaded = settings_module.load_main_window_placement([available])
    if loaded.frame_geometry is None:
        raise RuntimeError("Remembered Workspace geometry did not round-trip.")
    frame_matches = loaded.frame_geometry == expected_frame
    state_matches = (
        loaded.maximized == expected_state["maximized"]
        and loaded.full_screen == expected_state["full_screen"]
    )
    if not frame_matches or not state_matches:
        raise RuntimeError("Remembered Workspace geometry/state changed on round-trip.")
    return {
        "round_trip": True,
        "saved_normalized_frame_geometry": _rect_record(expected_frame),
        "loaded_frame_geometry": _rect_record(loaded.frame_geometry),
        "saved_state": expected_state,
        "loaded_state": {
            "maximized": loaded.maximized,
            "full_screen": loaded.full_screen,
        },
        "frame_matches": frame_matches,
        "state_matches": state_matches,
    }


def _exercise_results_splitter(app, window):
    window.showNormal()
    # layout-audit: allow=verification-layout-fixture; reason=native evidence exercises an Adjustable Pane
    window.resize(1024, 640)
    window.show()
    _flush(app)
    extent = max(2, window.results_nav_splitter.width())
    window.results_nav_splitter.setSizes(
        [max(1, int(extent * 0.35)), max(1, int(extent * 0.65))]
    )
    _flush(app)
    sizes = window.results_nav_splitter.sizes()
    if len(sizes) != 2 or any(size <= 0 for size in sizes):
        raise RuntimeError("Results Adjustable Panes are not independently reachable.")
    return {"sizes": sizes, "both_panes_reachable": True}


def _create_intrinsic_ratio_artifact(output):
    path = output / "intrinsic-ratio-evidence.png"
    image = QtGui.QImage(640, 360, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor("#2457a6"), 8))
        painter.drawRect(20, 20, 600, 320)
        painter.setBrush(QtGui.QColor("#7cb342"))
        painter.drawEllipse(220, 80, 200, 200)
        painter.setPen(QtGui.QColor("#202124"))
        painter.drawText(
            image.rect(),
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignBottom,
            "16:9 intrinsic-ratio artifact",
        )
    finally:
        painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError("Could not create intrinsic-ratio evidence artifact.")
    return path


def _intrinsic_artifact_record(window, artifact_path):
    if len(window._raster_plot_items) != 1:
        raise RuntimeError("Results evidence expected one Intrinsic-Ratio Artifact.")
    item = window._raster_plot_items[0]
    source_width, source_height = _pixmap_logical_size(item.source_pixmap)
    displayed_width = item.boundingRect().width() * item.scale()
    displayed_height = item.boundingRect().height() * item.scale()
    source_ratio = source_width / source_height
    displayed_ratio = displayed_width / displayed_height
    ratio_error = abs(source_ratio - displayed_ratio) / source_ratio
    if ratio_error > 0.01:
        raise RuntimeError("Results evidence distorted its Intrinsic-Ratio Artifact.")
    payload = Path(artifact_path).read_bytes()
    return {
        "path": Path(artifact_path).name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "pixel_size": [640, 360],
        "source_size": [source_width, source_height],
        "displayed_size": [round(displayed_width, 2), round(displayed_height, 2)],
        "source_aspect_ratio": round(source_ratio, 6),
        "displayed_aspect_ratio": round(displayed_ratio, 6),
        "relative_ratio_error": round(ratio_error, 6),
        "preserved": True,
    }


def _pixmap_logical_size(pixmap):
    dpr = max(1.0, pixmap.devicePixelRatioF())
    return pixmap.width() / dpr, pixmap.height() / dpr


def _assert_screen_reachable(window):
    screen = window.screen() or QtWidgets.QApplication.primaryScreen()
    if screen is None or not screen.availableGeometry().contains(
        window.frameGeometry()
    ):
        raise RuntimeError(
            "%s is not reachable on its owning screen." % window.objectName()
        )
    parent = window.parentWidget()
    if parent is not None and parent.screen() is not screen:
        raise RuntimeError("Parented surface opened on a different screen.")


def _assert_multiline_tool_button_content(window):
    for button in window.findChildren(QtWidgets.QToolButton):
        if not button.isVisible() or "\n" not in button.text():
            continue
        line_count = len(button.text().splitlines())
        margin = max(
            0,
            button.style().pixelMetric(
                QtWidgets.QStyle.PixelMetric.PM_ButtonMargin, None, button
            ),
        )
        frame = max(
            0,
            button.style().pixelMetric(
                QtWidgets.QStyle.PixelMetric.PM_DefaultFrameWidth, None, button
            ),
        )
        required_height = (
            button.iconSize().height()
            + (line_count * button.fontMetrics().lineSpacing())
            + (2 * margin)
            + (2 * frame)
        )
        if button.height() < required_height:
            raise RuntimeError(
                "Required Content is clipped in %s: %s < %s."
                % (button.objectName(), button.height(), required_height)
            )


def _flush(app):
    for _index in range(4):
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 100)


def _rect_record(rect):
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def _screen_record(screen):
    return {
        "name": screen.name(),
        "geometry": _rect_record(screen.geometry()),
        "available_geometry": _rect_record(screen.availableGeometry()),
        "physical_dpi": round(screen.physicalDotsPerInch(), 2),
    }


def _window_chrome_record(window):
    frame = window.frameGeometry()
    client = window.geometry()
    horizontal = max(0, frame.width() - window.width())
    vertical = max(0, frame.height() - window.height())
    left = max(0, client.left() - frame.left())
    top = max(0, client.top() - frame.top())
    return {
        "title": window.windowTitle(),
        "window_flags": int(window.windowFlags()),
        "frame_margins": {
            "left": left,
            "top": top,
            "right": max(0, horizontal - left),
            "bottom": max(0, vertical - top),
        },
    }


def _font_record(font):
    return {
        "family": font.family(),
        "point_size": font.pointSizeF(),
        "weight": font.weight(),
        "style": font.style().value,
    }


def _human_review_template(manifest):
    lines = [
        "# Native Adaptive-Layout Human Review\n",
        "This package-generated evidence uses native Qt paint and window capture. ",
        "Review screenshots visually; do not use pixel-diff gating.\n\n",
        "- Platform plugin: `%s`\n" % manifest["platform_plugin"],
        "- Scale: `%s`\n" % manifest["scale_factor_environment"],
        "- Logical DPI: `%s`\n" % manifest["logical_dpi"],
        "- Device pixel ratio: `%s`\n\n" % manifest["device_pixel_ratio"],
    ]
    lines.extend("- [ ] %s\n" % item for item in manifest["human_review"]["checklist"])
    if manifest["unavailable_scenarios"]:
        lines.append("\n## Capability-unavailable native scenarios\n\n")
        lines.extend(
            "- `%s`: %s\n" % (item["name"], item["reason"])
            for item in manifest["unavailable_scenarios"]
        )
    lines.extend(
        [
            "\nReviewer: ____________________\n",
            "\nReview date: ____________________\n",
            "\nVerdict / defects: ____________________\n",
        ]
    )
    return "".join(lines)
