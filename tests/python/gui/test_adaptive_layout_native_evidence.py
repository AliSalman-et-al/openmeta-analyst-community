# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Behavioral coverage for the package-native adaptive-layout evidence runner."""

import json
import importlib.util
import os
from pathlib import Path

import pytest
from rc_metastudio import automation

from test_types import required


ROOT = Path(__file__).resolve().parents[3]


def test_native_evidence_rejects_non_native_and_wrong_platform_plugins():
    from scripts import adaptive_layout_evidence

    with pytest.raises(RuntimeError, match="native Qt platform"):
        adaptive_layout_evidence.validate_native_platform("offscreen", "win32", "AMD64")
    with pytest.raises(RuntimeError, match="expected Qt platform cocoa"):
        adaptive_layout_evidence.validate_native_platform("windows", "darwin", "x86_64")
    with pytest.raises(RuntimeError, match="requires an Apple silicon arm64 host"):
        adaptive_layout_evidence.validate_native_platform("cocoa", "darwin", "x86_64")

    assert (
        adaptive_layout_evidence.validate_native_platform("windows", "win32", "AMD64")
        == "windows"
    )
    assert (
        adaptive_layout_evidence.validate_native_platform("cocoa", "darwin", "arm64")
        == "cocoa"
    )


def test_native_evidence_records_absolute_scale_when_qt_uses_native_multiplier(
    monkeypatch,
):
    from scripts import adaptive_layout_evidence

    monkeypatch.setenv("QT_SCALE_FACTOR", "1.2")
    monkeypatch.setenv("RCMS_ADAPTIVE_LAYOUT_SCALE", "1.5")
    assert adaptive_layout_evidence._requested_scale_factor() == "1.5"

    monkeypatch.delenv("RCMS_ADAPTIVE_LAYOUT_SCALE")
    assert adaptive_layout_evidence._requested_scale_factor() == "1.2"


def test_exact_client_size_repositions_the_outer_frame_inside_the_screen(qapp):
    from scripts import adaptive_layout_evidence

    window = adaptive_layout_evidence.QtWidgets.QMainWindow()
    window.show()
    qapp.processEvents()
    screen = required(window.screen() or qapp.primaryScreen(), "screen")
    available = screen.availableGeometry()
    margins = required(window.windowHandle(), "window handle").frameMargins()
    requested = adaptive_layout_evidence.QtCore.QSize(
        available.width() - margins.left() - margins.right() - 1,
        available.height() - margins.top() - margins.bottom() - 1,
    )
    window.move(available.bottomRight())

    try:
        adaptive_layout_evidence._show_at_exact_client_size(qapp, window, requested)

        assert available.contains(window.frameGeometry())
    finally:
        window.close()
        qapp.processEvents()


def test_exact_client_size_clears_sticky_maximized_state(qapp):
    from scripts import adaptive_layout_evidence

    class StickyMaximizedWindow(adaptive_layout_evidence.QtWidgets.QMainWindow):
        first_show = True

        def show(self):
            super().show()
            if self.first_show:
                self.first_show = False
                self.setWindowState(
                    self.windowState()
                    | adaptive_layout_evidence.QtCore.Qt.WindowState.WindowMaximized
                )

        def showNormal(self):
            # Model a Cocoa first-show callback that reapplies remembered
            # maximized placement while showNormal() is still being processed.
            self.show()

        def resize(self, *args):
            if not self.isMaximized():
                super().resize(*args)

    window = StickyMaximizedWindow()
    window.setWindowState(
        window.windowState()
        | adaptive_layout_evidence.QtCore.Qt.WindowState.WindowMaximized
    )

    try:
        requested = adaptive_layout_evidence.QtCore.QSize(640, 480)
        adaptive_layout_evidence._show_at_exact_client_size(qapp, window, requested)

        assert not window.isMaximized()
        assert window.size() == requested
    finally:
        window.close()
        qapp.processEvents()


def test_native_frame_capture_retries_until_compositor_pixels_are_visible(
    qapp, monkeypatch
):
    from scripts import adaptive_layout_evidence

    blank = adaptive_layout_evidence.QtGui.QPixmap(140, 89)
    blank.fill(adaptive_layout_evidence.QtGui.QColor("white"))
    painted = adaptive_layout_evidence.QtGui.QPixmap(blank.size())
    painted.fill(adaptive_layout_evidence.QtGui.QColor("white"))
    painter = adaptive_layout_evidence.QtGui.QPainter(painted)
    painter.fillRect(20, 20, 100, 40, adaptive_layout_evidence.QtGui.QColor("blue"))
    painter.end()
    grabs = iter((blank, blank, painted))
    calls = []

    def grab(_screen, _window):
        calls.append(True)
        return next(grabs)

    monkeypatch.setattr(adaptive_layout_evidence, "_grab_native_frame", grab)

    result = adaptive_layout_evidence._grab_painted_native_frame(
        qapp, object(), adaptive_layout_evidence.QtWidgets.QWidget()
    )

    assert result.cacheKey() == painted.cacheKey()
    assert len(calls) == 3


def test_native_frame_capture_targets_window_frame_not_desktop(
    qapp, monkeypatch
):
    from scripts import adaptive_layout_evidence

    painted = adaptive_layout_evidence.QtGui.QPixmap(140, 89)
    painted.fill(adaptive_layout_evidence.QtGui.QColor("white"))
    painter = adaptive_layout_evidence.QtGui.QPainter(painted)
    painter.fillRect(20, 20, 100, 40, adaptive_layout_evidence.QtGui.QColor("blue"))
    painter.end()

    class Handle:
        def frameMargins(self):
            return adaptive_layout_evidence.QtCore.QMargins(5, 7, 9, 11)

    class Window:
        def windowHandle(self):
            return Handle()

        def winId(self):
            return 42

        def frameGeometry(self):
            return adaptive_layout_evidence.QtCore.QRect(100, 200, 140, 89)

    class Screen:
        def __init__(self):
            self.arguments = None

        def grabWindow(self, *arguments):
            self.arguments = arguments
            return painted

    screen = Screen()
    result = adaptive_layout_evidence._grab_native_frame(screen, Window())

    assert result.cacheKey() == painted.cacheKey()
    assert screen.arguments == (42, -5, -7, 140, 89)


def test_native_frame_capture_fails_closed_on_persistent_blank_frame(
    qapp, monkeypatch
):
    from scripts import adaptive_layout_evidence

    blank = adaptive_layout_evidence.QtGui.QPixmap(140, 89)
    blank.fill(adaptive_layout_evidence.QtGui.QColor("black"))
    calls = []

    class Window:
        def update(self):
            pass

        def repaint(self):
            pass

        def objectName(self):
            return "MainWindow"

        def windowTitle(self):
            return "Main Window"

    def grab(_screen, _window):
        calls.append(True)
        return blank

    monkeypatch.setattr(adaptive_layout_evidence, "_grab_native_frame", grab)

    with pytest.raises(RuntimeError, match="remained blank after 3"):
        adaptive_layout_evidence._grab_painted_native_frame(
            qapp, object(), Window(), attempts=3
        )

    assert len(calls) == 3


def test_native_frame_requests_a_fresh_client_paint_before_each_native_grab(
    qapp, monkeypatch
):
    from scripts import adaptive_layout_evidence

    blank = adaptive_layout_evidence.QtGui.QPixmap(140, 89)
    blank.fill(adaptive_layout_evidence.QtGui.QColor("white"))
    painted = adaptive_layout_evidence.QtGui.QPixmap(blank.size())
    painted.fill(adaptive_layout_evidence.QtGui.QColor("white"))
    painter = adaptive_layout_evidence.QtGui.QPainter(painted)
    painter.fillRect(20, 20, 100, 40, adaptive_layout_evidence.QtGui.QColor("blue"))
    painter.end()

    class Window:
        def __init__(self):
            self.ready = False
            self.events = []

        def update(self):
            self.events.append("update")

        def repaint(self):
            self.events.append("repaint")
            self.ready = True

        def objectName(self):
            return "MainWindow"

        def windowTitle(self):
            return "Main Window"

    window = Window()

    def grab(_screen, _window):
        window.events.append("grab")
        return painted if window.ready else blank

    monkeypatch.setattr(adaptive_layout_evidence, "_grab_native_frame", grab)

    result = adaptive_layout_evidence._grab_painted_native_frame(qapp, object(), window)

    assert result.cacheKey() == painted.cacheKey()
    assert window.events == ["update", "repaint", "grab"]


def test_evidence_runner_captures_all_archetypes_and_runtime_contracts(
    qapp, monkeypatch, tmp_path
):
    from scripts import adaptive_layout_evidence

    sample = ROOT / "sample_projects" / "amino.rcms"
    output = tmp_path / "native-evidence"
    os.chdir(ROOT)
    adaptive_layout_evidence.configure_isolated_evidence_settings(output)
    monkeypatch.setattr(
        adaptive_layout_evidence,
        "validate_native_platform",
        lambda: "test-native-plugin",
    )
    monkeypatch.setenv("QT_SCALE_FACTOR", "1.0")
    # The offscreen pytest display is only 800x600 including synthetic frame
    # margins. Native package lanes retain and prove the release sizes.
    monkeypatch.setattr(
        adaptive_layout_evidence,
        "CONSTRAINED_WORKSPACE",
        qapp.primaryScreen().availableSize()
        - adaptive_layout_evidence.QtCore.QSize(80, 80),
    )
    monkeypatch.setattr(
        adaptive_layout_evidence,
        "FULL_USABILITY_WORKSPACE",
        qapp.primaryScreen().availableSize()
        - adaptive_layout_evidence.QtCore.QSize(40, 40),
    )

    def grab_test_frame(_screen, window):
        pixmap = adaptive_layout_evidence.QtGui.QPixmap(window.frameGeometry().size())
        pixmap.fill(adaptive_layout_evidence.QtGui.QColor("white"))
        painter = adaptive_layout_evidence.QtGui.QPainter(pixmap)
        painter.fillRect(
            pixmap.width() // 2,
            pixmap.height() // 2,
            pixmap.width() // 2,
            pixmap.height() // 2,
            adaptive_layout_evidence.QtGui.QColor("#2457a6"),
        )
        painter.end()
        return pixmap

    monkeypatch.setattr(adaptive_layout_evidence, "_grab_native_frame", grab_test_frame)

    try:
        app, main = automation.start_automation()
        manifest = adaptive_layout_evidence.run_native_adaptive_layout_evidence(
            app, main, sample, output
        )
    finally:
        os.chdir(ROOT)

    assert {surface["archetype"] for surface in manifest["surfaces"]} == {
        "workspace",
        "workflow",
        "transactional",
        "transient",
    }
    assert [surface["name"] for surface in manifest["surfaces"]] == [
        "main-workspace-constrained",
        "results-workspace-constrained",
        "main-workspace-full-usability",
        "results-workspace-full-usability",
        "new-dataset-workflow-constrained-owner",
        "about-legal-constrained-owner",
        "analysis-progress-constrained-owner",
    ]
    assert manifest["table"]["rows"] > 0
    assert manifest["splitter"]["both_panes_reachable"] is True
    assert manifest["intrinsic_artifact"]["preserved"] is True
    assert manifest["remembered_geometry"]["round_trip"] is True
    assert manifest["remembered_geometry"]["frame_matches"] is True
    assert manifest["remembered_geometry"]["state_matches"] is True
    assert manifest["runtime_resize"]["table_reachable"] is True
    assert manifest["human_review"]["status"] == "required"
    assert len(list((output / "screenshots").glob("*.png"))) == 7
    assert (
        json.loads((output / "manifest.json").read_text(encoding="utf-8"))[
            "platform_plugin"
        ]
        == "test-native-plugin"
    )
    assert "pixel-diff" in (output / "HUMAN_REVIEW.md").read_text(encoding="utf-8")
    validator_path = ROOT / "scripts" / "validate_adaptive_layout_evidence.py"
    spec = importlib.util.spec_from_file_location(
        "evidence_validator_gui", validator_path
    )
    assert spec is not None
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)
    constrained_size = adaptive_layout_evidence.CONSTRAINED_WORKSPACE
    constrained = [constrained_size.width(), constrained_size.height()]
    full_size = adaptive_layout_evidence.FULL_USABILITY_WORKSPACE
    full_usability = [full_size.width(), full_size.height()]
    for name in (
        "main-workspace-constrained",
        "results-workspace-constrained",
    ):
        validator.EXPECTED_SCENARIO_CONTRACTS[name] = (
            "workspace",
            constrained,
            None,
        )
    for name in (
        "main-workspace-full-usability",
        "results-workspace-full-usability",
    ):
        validator.EXPECTED_SCENARIO_CONTRACTS[name] = (
            "workspace",
            full_usability,
            None,
        )
    for name, archetype in (
        ("new-dataset-workflow-constrained-owner", "workflow"),
        ("about-legal-constrained-owner", "transactional"),
        ("analysis-progress-constrained-owner", "transient"),
    ):
        validator.EXPECTED_SCENARIO_CONTRACTS[name] = (
            archetype,
            None,
            constrained,
        )
    validator.validate_evidence(
        output,
        "test-native-plugin",
        manifest["scale_factor_environment"],
    )


