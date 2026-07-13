import os
import sys

import pytest
from PyQt5 import QtCore, QtWidgets


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RCMS_STUB_BACKEND", "1")
sys.path.insert(0, os.path.abspath("src/rc_metastudio"))
sys.path.insert(0, os.path.abspath("src/rc_metastudio/forms"))


def _empty_results(summary="Summary text"):
    return {"texts": {"Summary": summary}}


def _use_isolated_settings(tmp_path):
    QtCore.QSettings.setPath(
        QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(tmp_path)
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    store = QtCore.QSettings()
    store.clear()
    store.sync()


def _dispose(widget, qapp):
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


def test_results_workspace_defaults_maximized_and_restores_screen_safe_state(
    qapp, tmp_path
):
    import results_window
    import settings

    _use_isolated_settings(tmp_path)
    fresh = results_window.ResultsWindow(_empty_results())
    try:
        assert fresh.property("RCMS_window_archetype") == "workspace"
        assert fresh.property("RCMS_window_role") == "results"
        assert fresh.isMaximized()

        fresh.showNormal()
        fresh.setGeometry(90, 70, 620, 410)
        fresh.results_nav_splitter.setSizes([180, 540])
    finally:
        _dispose(fresh, qapp)

    restored = results_window.ResultsWindow(_empty_results())
    try:
        assert not restored.isMaximized()
        restored.show()
        qapp.processEvents()
        placement = settings.load_results_window_state(
            available_geometries=[QtCore.QRect(0, 0, 800, 600)]
        )
        assert QtCore.QRect(0, 0, 800, 600).contains(placement["frame_geometry"])
        sizes = restored.results_nav_splitter.sizes()
        assert sizes[0] / sum(sizes) == pytest.approx(0.25, abs=0.03)
    finally:
        _dispose(restored, qapp)


def test_results_splitter_proportions_persist_independently_of_outer_geometry(
    qapp, tmp_path
):
    import results_window
    import settings

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    try:
        window.showNormal()
        window.resize(900, 500)
        window.results_nav_splitter.setSizes([315, 585])
        settings.save_results_window_state(window)

        stored = settings.load_results_window_state(
            available_geometries=[QtCore.QRect(0, 0, 640, 480)]
        )
        assert stored["splitter_proportions"] == pytest.approx([0.35, 0.65], abs=0.002)
        assert stored["frame_geometry"].width() <= 640
        assert stored["frame_geometry"].height() <= 480
    finally:
        _dispose(window, qapp)


def test_results_long_text_reflows_inside_constrained_viewport_without_window_growth(
    qapp, tmp_path
):
    import results_window

    _use_isolated_settings(tmp_path)
    long_summary = " ".join(["Long analysis summary"] * 120)
    window = results_window.ResultsWindow(_empty_results(long_summary))
    try:
        window.showNormal()
        window.resize(560, 420)
        window.show()
        qapp.processEvents()
        before = QtCore.QRect(window.geometry())

        window.results_nav_splitter.setSizes([280, 280])
        for _ in range(8):
            window._schedule_viewport_refit()
        qapp.processEvents()

        text_item = next(
            item
            for item in window.scene.items()
            if isinstance(item, results_window.SelectableResultsTextItem)
        )
        assert window.geometry() == before
        assert text_item.textWidth() > 0
        assert text_item.textWidth() <= window.graphics_view.viewport().width()
        assert window.scene.width() <= window.graphics_view.viewport().width() + 2
    finally:
        _dispose(window, qapp)


def test_results_resize_burst_runs_one_expensive_reflow_per_event_loop_turn(
    qapp, monkeypatch, tmp_path
):
    import results_window

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    calls = []
    monkeypatch.setattr(window, "_refit_viewport_items", lambda: calls.append("reflow"))
    try:
        window.show()
        qapp.processEvents()
        calls.clear()
        for _ in range(20):
            window.resize(window.width() + 1, window.height())
            window._schedule_viewport_refit()
        assert calls == []
        qapp.processEvents()
        assert calls == ["reflow"]
    finally:
        _dispose(window, qapp)


def test_results_first_show_runs_one_scheduled_expensive_reflow(
    qapp, monkeypatch, tmp_path
):
    import results_window

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    calls = []
    monkeypatch.setattr(window, "_refit_viewport_items", lambda: calls.append("reflow"))
    try:
        window.show()
        assert calls == []
        qapp.processEvents()
        assert calls == ["reflow"]
    finally:
        _dispose(window, qapp)


def test_results_refit_does_not_dispatch_unrelated_layout_requests(
    qapp, monkeypatch, tmp_path
):
    import results_window

    class LayoutRequestProbe(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.layout_requests = 0

        def event(self, event):
            if event.type() == QtCore.QEvent.LayoutRequest:
                self.layout_requests += 1
            return super().event(event)

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    probe = LayoutRequestProbe()
    probe_layout = QtWidgets.QVBoxLayout(probe)
    calls = []
    monkeypatch.setattr(window, "_refit_viewport_items", lambda: calls.append("reflow"))
    try:
        window.show()
        probe.show()
        qapp.processEvents()
        calls.clear()
        probe.layout_requests = 0

        probe_layout.addWidget(QtWidgets.QLabel("pending unrelated layout", probe))
        window._viewport_refit_pending = True
        window._run_scheduled_viewport_refit()

        assert calls == ["reflow"]
        assert probe.layout_requests == 0
        qapp.processEvents()
        assert probe.layout_requests == 1
    finally:
        probe.close()
        probe.deleteLater()
        _dispose(window, qapp)


def test_results_regeneration_burst_runs_one_scheduled_expensive_reflow(
    qapp, monkeypatch, tmp_path
):
    import results_window

    _use_isolated_settings(tmp_path)
    plot_path = tmp_path / "plot.png"
    image = results_window.QImage(600, 300, results_window.QImage.Format_RGB32)
    image.fill(results_window.Qt.white)
    assert image.save(str(plot_path), "PNG")
    window = results_window.ResultsWindow(
        {
            "texts": {},
            "images": {"Plot": str(plot_path)},
            "plot_capabilities": {
                "Plot": {
                    "plot_kind": "other",
                    "editable": False,
                    "styleable": False,
                    "regenerator": "none",
                    "composition": "single",
                }
            },
        }
    )
    try:
        window.show()
        qapp.processEvents()
        item = next(
            item
            for item in window._raster_plot_items
            if isinstance(item, results_window.ResponsivePixmapItem)
        )
        artifact = window.create_plot_artifact("Plot", str(plot_path))
        calls = []
        monkeypatch.setattr(
            window, "_refit_viewport_items", lambda: calls.append("reflow")
        )

        window._refresh_plot_item(item, artifact, str(plot_path))
        window._refresh_plot_item(item, artifact, str(plot_path))
        assert calls == []
        qapp.processEvents()
        assert calls == ["reflow"]
    finally:
        _dispose(window, qapp)


def test_dpr_raster_uses_device_independent_dimensions_for_viewport_fit(qapp, tmp_path):
    import results_window

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    try:
        window.showNormal()
        window.resize(560, 420)
        window.show()
        qapp.processEvents()

        source = results_window.QPixmap(1200, 600)
        source.fill(results_window.Qt.white)
        source.setDevicePixelRatio(2.0)
        item = results_window.ResponsivePixmapItem(source)
        item.setPixmap(source)
        window.scene.addItem(item)
        window._raster_plot_items.append(item)

        window._refit_raster_plot_items()

        intended_width = min(600.0, float(window._plot_viewport_width()))
        displayed = item.sceneBoundingRect()
        assert item.source_pixmap.width() == 1200
        assert item.source_pixmap.devicePixelRatioF() == pytest.approx(2.0)
        assert displayed.width() == pytest.approx(intended_width, abs=1.0)
        assert displayed.width() / displayed.height() == pytest.approx(2.0)
    finally:
        _dispose(window, qapp)


def test_plot_editor_is_screen_bounded_transactional_dialog_with_fixed_actions(
    qapp, tmp_path
):
    import results_window

    _use_isolated_settings(tmp_path)
    dialog = results_window.EditPlotDialog({}, "forest.png")
    try:
        dialog.show()
        qapp.processEvents()
        assert dialog.property("RCMS_window_archetype") == "transactional"
        assert dialog.property("RCMS_window_role") == "transactional"
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        available = dialog.screen().availableGeometry()
        assert dialog.frameGeometry().width() <= int(available.width() * 0.9) + 1
        assert dialog.frameGeometry().height() <= int(available.height() * 0.9) + 1
        assert dialog.buttonBox.isVisible()
        assert dialog.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).isVisible()
        assert dialog.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).isVisible()
    finally:
        _dispose(dialog, qapp)
