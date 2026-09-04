import os
from pathlib import Path
from test_types import key_click, key_clicks, required

import pytest
from PyQt6 import QtCore, QtGui, QtSvg, QtTest, QtWidgets
from rc_metastudio.analysis_results import parse_analysis_result
from rc_metastudio.plot_text import normalize_plot_text_value

pytestmark = pytest.mark.qsettings


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("RCMS_QT6_BUILD_ROOT", str(ROOT / "build" / "qt6-verification"))
from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()
from rc_metastudio import plot_editor_dialog, results_window


def _empty_results(summary="Summary text"):
    return _analysis_result({"texts": {"Summary": summary}})


def _analysis_result(payload):
    """Build the complete result contract used by ResultsWindow fixtures."""
    payload = dict(payload)
    payload.setdefault("version", 1)
    text_titles = list(payload.get("texts", {}))
    image_titles = list(payload.get("images", {}))
    payload.setdefault(
        "sections",
        [
            {
                "id": f"fixture.text.{index}",
                "kind": "text",
                "order": index,
                "title": title,
                "source_key": title,
            }
            for index, title in enumerate(text_titles)
        ]
        + [
            {
                "id": f"fixture.image.{index}",
                "kind": "image",
                "order": len(text_titles) + index,
                "title": title,
                "source_key": title,
            }
            for index, title in enumerate(image_titles)
        ],
    )
    return parse_analysis_result(payload)


def _plot_capability(
    plot_kind="forest", editable=True, styleable=True, regenerator="forest"
):
    return {
        "plot_kind": plot_kind,
        "editable": editable,
        "styleable": styleable,
        "regenerator": regenerator,
        "composition": "single",
    }


def _use_isolated_settings(tmp_path):
    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    store = QtCore.QSettings()
    store.clear()
    store.sync()


def _dispose(widget, qapp):
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize(
    "placeholder",
    ["", "[default]", "[Default]", "<default>", "(default)", "default"],
)
def test_untouched_plot_default_placeholder_is_unset(placeholder):
    assert normalize_plot_text_value(placeholder) is None


def test_edited_plot_default_placeholder_remains_user_text():
    assert normalize_plot_text_value("[default]", was_edited=True) == "[default]"


def test_qtsvg_renders_materialized_default_black_plot_stroke():
    svg = b"""<svg xmlns='http://www.w3.org/2000/svg' width='100' height='40' viewBox='0 0 100 40'>
    <g class='svglite'><line x1='10' y1='20' x2='90' y2='20' stroke='#000000' fill='none'
    stroke-linecap='round' stroke-linejoin='round' stroke-miterlimit='10.00'/></g></svg>"""
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg))
    assert renderer.isValid()

    image = QtGui.QImage(100, 40, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.white)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()

    assert (
        sum(
            image.pixelColor(x, 20) != QtGui.QColor(QtCore.Qt.GlobalColor.white)
            for x in range(100)
        )
        >= 75
    )


def test_plot_graphics_items_paint_an_opaque_white_canvas(qapp, tmp_path):
    from rc_metastudio import results_window

    svg_path = tmp_path / "svglite-shaped-transparent.svg"
    svg_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1127.12pt" '
        'height="360.00pt" viewBox="0 0 1127.12 360.00">'
        '<g class="svglite"><line x1="20" y1="20" x2="1100" y2="20" '
        'stroke="#000000"/></g></svg>',
        encoding="utf-8",
    )

    svg_item = results_window._svg_item_class()(str(svg_path))
    raster_source = QtGui.QPixmap(100, 40)
    raster_source.fill(QtCore.Qt.GlobalColor.transparent)
    raster_item = results_window.ResponsivePixmapItem(raster_source)
    raster_item.setPixmap(raster_source)

    for item in (svg_item, raster_item):
        bounds = item.boundingRect()
        rendered = QtGui.QImage(
            max(1, int(bounds.width())),
            max(1, int(bounds.height())),
            QtGui.QImage.Format.Format_ARGB32,
        )
        rendered.fill(QtGui.QColor("#2b2b2b"))
        painter = QtGui.QPainter(rendered)
        item.paint(painter, QtWidgets.QStyleOptionGraphicsItem())
        painter.end()

        assert rendered.pixelColor(rendered.width() - 1, rendered.height() - 1) == (
            QtGui.QColor(QtCore.Qt.GlobalColor.white)
        )


@pytest.mark.parametrize("plot_format", ("svg", "png"))
def test_results_plot_preview_is_opaque_white_on_dark_theme(
    qapp, tmp_path, plot_format
):
    _use_isolated_settings(tmp_path)
    plot_path = tmp_path / ("transparent-plot." + plot_format)
    if plot_format == "svg":
        plot_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40" '
            'viewBox="0 0 100 40"><line x1="10" y1="20" x2="90" y2="20" '
            'stroke="black"/></svg>',
            encoding="utf-8",
        )
    else:
        source = QtGui.QImage(100, 40, QtGui.QImage.Format.Format_ARGB32)
        source.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(source)
        painter.setPen(QtGui.QColor(QtCore.Qt.GlobalColor.black))
        painter.drawLine(10, 20, 90, 20)
        painter.end()
        assert source.save(str(plot_path), "PNG")

    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {},
                "images": {"Plot": str(plot_path)},
                "plot_capabilities": {
                    "Plot": _plot_capability(
                        plot_kind="other",
                        editable=False,
                        styleable=False,
                        regenerator="none",
                    )
                },
            }
        )
    )
    try:
        plot_item = (
            window._svg_plot_items[0]
            if plot_format == "svg"
            else window._raster_plot_items[0]
        )
        preview = QtGui.QImage(100, 40, QtGui.QImage.Format.Format_ARGB32)
        preview.fill(QtGui.QColor("#2b2b2b"))
        painter = QtGui.QPainter(preview)
        if plot_format == "svg":
            plot_item.renderer().render(painter, QtCore.QRectF(0, 0, 100, 40))
        else:
            painter.drawPixmap(QtCore.QRect(0, 0, 100, 40), plot_item.pixmap())
        painter.end()

        white = QtGui.QColor(QtCore.Qt.GlobalColor.white)
        white_pixels = sum(
            preview.pixelColor(x, y) == white
            for y in range(preview.height())
            for x in range(preview.width())
        )
        assert white_pixels >= 3500, white_pixels
        assert all(
            preview.pixelColor(x, y) == white
            for x, y in ((0, 0), (99, 0), (0, 39), (99, 39))
        )
    finally:
        _dispose(window, qapp)


def test_results_workspace_defaults_maximized_and_restores_screen_safe_state(
    qapp, tmp_path
):
    from rc_metastudio import adaptive_window
    from rc_metastudio import results_window
    from rc_metastudio import settings

    _use_isolated_settings(tmp_path)
    fresh = results_window.ResultsWindow(_empty_results())
    try:
        state = adaptive_window.adaptive_window_state(fresh)
        assert state.policy.archetype is adaptive_window.WindowArchetype.WORKSPACE
        assert state.role is adaptive_window.WindowRole.RESULTS
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
        total_size = sum(sizes)
        assert total_size > 0
        if total_size == 0:
            pytest.fail("results splitter has no allocated space")
        assert sizes[0] / total_size == pytest.approx(0.25, abs=0.03)
    finally:
        _dispose(restored, qapp)


def test_results_splitter_proportions_persist_independently_of_outer_geometry(
    qapp, tmp_path
):
    from rc_metastudio import results_window
    from rc_metastudio import settings

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
        viewport = required(window.graphics_view.viewport(), "graphics viewport")
        assert text_item.textWidth() <= viewport.width()
        assert window.scene.width() <= viewport.width() + 2
    finally:
        _dispose(window, qapp)


def test_results_resize_burst_runs_one_expensive_reflow_per_event_loop_turn(
    qapp, monkeypatch, tmp_path
):
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
    from rc_metastudio import results_window

    class LayoutRequestProbe(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.layout_requests = 0

        # The Qt runtime dispatches this override correctly; the bundled
        # stubs expose an incompatible descriptor signature.
        def event(self, event: QtCore.QEvent) -> bool:  # ty: ignore[invalid-method-override]
            if event.type() == QtCore.QEvent.Type.LayoutRequest:
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
    _use_isolated_settings(tmp_path)
    plot_path = tmp_path / "plot.png"
    image = results_window.QImage(600, 300, results_window.QImage.Format.Format_RGB32)
    image.fill(results_window.Qt.GlobalColor.white)
    assert image.save(str(plot_path), "PNG")
    window = results_window.ResultsWindow(
        _analysis_result(
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
    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    try:
        window.showNormal()
        window.resize(560, 420)
        window.show()
        qapp.processEvents()

        source = results_window.QPixmap(1200, 600)
        source.fill(results_window.Qt.GlobalColor.white)
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
    from rc_metastudio import adaptive_window

    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog({}, "forest.png")
    try:
        dialog.show()
        qapp.processEvents()
        state = adaptive_window.adaptive_window_state(dialog)
        assert state.policy.archetype is adaptive_window.WindowArchetype.TRANSACTIONAL
        assert state.role is adaptive_window.WindowRole.TRANSACTIONAL
        assert isinstance(dialog.content_scroll, QtWidgets.QScrollArea)
        assert dialog.content_scroll.widgetResizable()
        assert not dialog.content_scroll.isAncestorOf(dialog.buttonBox)
        available = required(dialog.screen(), "dialog screen").availableGeometry()
        assert dialog.frameGeometry().width() <= int(available.width() * 0.9) + 1
        assert dialog.frameGeometry().height() <= int(available.height() * 0.9) + 1
        assert dialog.buttonBox.isVisible()
        assert required(
            dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Apply),
            "apply button",
        ).isVisible()
        assert required(
            dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok),
            "ok button",
        ).isVisible()
    finally:
        _dispose(dialog, qapp)


def test_sroc_plot_editor_keeps_dynamic_controls_inside_scrollable_content(
    qapp, tmp_path
):
    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog({}, "sroc.svg", plot_type="sroc")
    try:
        high_font = QtGui.QFont(dialog.font())
        high_font.setPointSize(18)
        dialog.setFont(high_font)
        dialog.resize(600, 450)
        dialog.show()
        qapp.processEvents()
        sroc_options = dialog.findChild(QtWidgets.QWidget, "sroc_options")
        assert sroc_options is not None
        assert dialog.content_scroll.isAncestorOf(sroc_options)
        assert dialog.content_layout.indexOf(sroc_options) >= 0
        content_viewport = required(
            dialog.content_scroll.viewport(), "content viewport"
        )
        content_scrollbar = required(
            dialog.content_scroll.verticalScrollBar(), "content scrollbar"
        )
        assert content_viewport.height() > 0
        assert content_scrollbar.maximum() > 0
        assert dialog.content_scroll.isAncestorOf(dialog.buttonBox) is False
    finally:
        _dispose(dialog, qapp)


def test_reitsma_coefficient_editor_hides_inapplicable_forest_controls(qapp):
    from rc_metastudio import plot_editor_dialog

    dialog = plot_editor_dialog.EditPlotDialog(
        {
            "reitsma.coefficient.scale": "Sensitivity",
            "reitsma.moderator.coding": {"quality": {"reference": "A"}},
            "fp_xlabel": "Odds ratio",
            "fp_plot_lb": "0.5",
            "fp_plot_ub": "3",
            "fp_xticks": "0.5, 1, 2, 3",
        },
        "coefficients.svg",
    )
    try:
        assert not dialog.groupBox.isVisible()
        assert not dialog.default_panel.isVisible()
        params = dialog.plot_params()
        assert params["reitsma.coefficient.scale"] == "Sensitivity"
        assert params["reitsma.moderator.coding"]["quality"]["reference"] == "A"
        assert params["fp_xlabel"] == "Odds ratio"
    finally:
        dialog.close()
        qapp.processEvents()


@pytest.mark.parametrize(
    "plot_type, parameter_name",
    [("forest", "fp_xlabel"), ("regression", "bp_xlabel"), ("sroc", "fp_xlabel")],
)
def test_plot_editor_omits_unedited_default_axis_label_sentinel(
    qapp, tmp_path, plot_type, parameter_name
):
    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog(
        {parameter_name: "[default]"}, "plot.svg", plot_type=plot_type
    )
    try:
        assert dialog.x_lbl_le.text() == ""
        assert dialog.plot_params()[parameter_name] is None
        dialog.x_lbl_le.setFocus()
        key_clicks(dialog.x_lbl_le, "Specific axis label")
        assert dialog.plot_params()[parameter_name] == "Specific axis label"
    finally:
        _dispose(dialog, qapp)


def test_sroc_plot_editor_uses_acronym_safe_browse_title(qapp, tmp_path, monkeypatch):
    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog({}, "sroc.svg", plot_type="sroc")
    titles = []

    monkeypatch.setattr(
        plot_editor_dialog.QFileDialog,
        "getSaveFileName",
        lambda _parent, title, *_args: titles.append(title) or ("", ""),
    )
    try:
        dialog.save_btn.click()
        assert titles == ["Save SROC Plot Image"]
    finally:
        _dispose(dialog, qapp)


def test_results_window_presents_summary_references_and_vector_plot_artifacts(
    qapp, tmp_path
):
    _use_isolated_settings(tmp_path)
    svg_path = tmp_path / "forest.display.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="801.5" height="400.75" '
        'viewBox="0 0 801.5 400.75"><rect width="801.5" height="400.75" '
        'fill="white"/><text x="24" y="48">Forest Plot</text></svg>',
        encoding="utf-8",
    )
    window = results_window.ResultsWindow(
        _analysis_result(
            {
                "texts": {
                    "Summary": "Random-effects model\nEstimate  Lower bound  Upper bound",
                    "References": "A maintained analysis reference.",
                },
                "images": {"Forest Plot": str(svg_path)},
                "display_images": {"Forest Plot": str(svg_path)},
                "image_params_paths": {"Forest Plot": str(tmp_path / "forest")},
                "image_order": ["Forest Plot"],
                "plot_capabilities": {"Forest Plot": _plot_capability()},
            }
        )
    )
    try:
        window.show()
        qapp.processEvents()
        nav_titles = [
            required(window.nav_tree.topLevelItem(index), "navigation item").text(0)
            for index in range(window.nav_tree.topLevelItemCount())
        ]
        assert nav_titles == ["Summary", "References", "Forest Plot"]
        svg_items = [
            item
            for item in window.scene.items()
            if isinstance(item, results_window._svg_item_class())
        ]
        assert len(svg_items) == 1
        assert svg_items[0].renderer().isValid()
        assert svg_items[0].sceneBoundingRect().width() > 0.0
        assert all(
            isinstance(position, QtCore.QPointF)
            for position in window.items_to_coords.values()
        )
        assert window.graphics_view.scene() is window.scene
    finally:
        _dispose(window, qapp)


@pytest.mark.parametrize(
    ("title", "plot_kind", "regenerator"),
    (
        ("Forest Plot", "forest", "forest"),
        ("Cumulative Forest Plot", "cumulative_forest", "forest"),
        ("Leave-one-out Forest Plot", "leave_one_out_forest", "forest"),
        ("Subgroup Forest Plot", "subgroup_forest", "forest"),
        ("Diagnostic Forest Plot", "forest", "forest"),
        ("Meta-Regression Bubble Plot", "regression", "regression"),
    ),
)
def test_regenerable_plot_families_expose_native_edit_and_export_actions(
    qapp, tmp_path, monkeypatch, title, plot_kind, regenerator
):
    from rc_metastudio import results_window

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    captured = []

    class Event:
        def screenPos(self):
            return QtCore.QPoint(20, 30)

        def accept(self):
            pass

    monkeypatch.setattr(
        results_window.app_error_handler,
        "popup_context_menu",
        lambda menu, *_args, **_kwargs: captured.append(
            [action.text() for action in menu.actions()]
        ),
    )
    artifact = results_window.PlotArtifact(
        title,
        str(tmp_path / "plot.svg"),
        _plot_capability(plot_kind=plot_kind, regenerator=regenerator),
        params_path=str(tmp_path / "plot-params"),
    )
    try:
        window._make_context_menu(artifact, None)(Event())
        assert captured == [
            [
                "Edit Plot",
                "Save PDF Image As",
                "Save PNG Image As",
                "Save TIFF Image As",
                "Save SVG Image As",
            ]
        ]
    finally:
        _dispose(window, qapp)


@pytest.mark.parametrize("extension", ["pdf", "png", "tiff", "svg"])
def test_results_window_regenerates_each_supported_export_format(
    qapp, tmp_path, monkeypatch, extension
):
    from rc_metastudio import results_window

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    calls = []
    artifact = results_window.PlotArtifact(
        "Forest Plot",
        str(tmp_path / "forest.svg"),
        _plot_capability(),
        params_path=str(tmp_path / "forest-params"),
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "load_in_r",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_forest_plot",
        lambda path: calls.append(("generate", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "export"), ""),
    )
    try:
        window.save_image_as(artifact, format=extension)
        assert calls == [
            ("load", f"{artifact.params_path}.plotdata"),
            ("generate", str(tmp_path / f"export.{extension}")),
        ]
    finally:
        _dispose(window, qapp)


@pytest.mark.parametrize("extension", ["pdf", "png", "tiff", "svg"])
def test_results_window_exports_sroc_with_format_specific_default_name(
    qapp, tmp_path, monkeypatch, extension
):
    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    calls = []
    defaults = []
    artifact = results_window.PlotArtifact(
        "SROC",
        str(tmp_path / "sroc.svg"),
        _plot_capability(plot_kind="sroc", regenerator="sroc"),
        params_path=str(tmp_path / "sroc-params"),
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "load_in_r",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "generate_sroc_plot",
        lambda path: calls.append(("generate", path)),
        raising=False,
    )

    def choose_path(_parent, _title, default_path, *_args):
        defaults.append(default_path)
        return str(tmp_path / "export"), ""

    monkeypatch.setattr(results_window.QFileDialog, "getSaveFileName", choose_path)
    try:
        window.save_image_as(artifact, format=extension)
        assert defaults == [f"sroc.{extension}"]
        assert calls == [
            ("load", f"{artifact.params_path}.plotdata"),
            ("generate", str(tmp_path / f"export.{extension}")),
        ]
    finally:
        _dispose(window, qapp)


def test_results_window_rejects_svgz_for_funnel_export_before_r(
    monkeypatch, qapp, tmp_path
):
    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    artifact = results_window.PlotArtifact(
        "Contour Funnel Plot",
        str(tmp_path / "funnel.png"),
        _plot_capability(plot_kind="contour_funnel", regenerator="funnel"),
        params_path=str(tmp_path / "funnel-params"),
    )
    calls = []
    monkeypatch.setattr(
        results_window.r_bridge,
        "load_vars_for_plot",
        lambda path: calls.append(("load", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "regenerate_small_study_effects_funnel",
        lambda path: calls.append(("generate", path)),
        raising=False,
    )
    monkeypatch.setattr(
        results_window.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "funnel.svgz"), ""),
    )
    try:
        with pytest.raises(ValueError, match="SVGZ export is not supported"):
            window.save_image_as(artifact, format="svg")
        assert calls == []
    finally:
        _dispose(window, qapp)


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 1.75])
def test_results_plot_geometry_preserves_fractional_logical_coordinates(
    qapp, tmp_path, scale
):
    from rc_metastudio import results_window

    _use_isolated_settings(tmp_path)
    window = results_window.ResultsWindow(_empty_results())
    try:
        window._viewport_width_override = 1003.0 * scale
        width, height = window._fit_size_to_viewport(801.5, 400.75, max_scale=4.0)
        assert isinstance(width, float)
        assert isinstance(height, float)
        assert width / height == pytest.approx(2.0)
        window.x_coord = 5.25
        window.y_coord = 9.75
        assert window.position() == QtCore.QPointF(5.25, 9.75)
    finally:
        _dispose(window, qapp)


def test_plot_editor_apply_signal_fires_exactly_once(qapp, tmp_path):

    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog({}, "forest.png")
    try:
        applied = QtTest.QSignalSpy(dialog.applied)
        button = dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        )
        assert button is not None
        button.click()
        qapp.processEvents()
        assert len(applied) == 1
    finally:
        _dispose(dialog, qapp)


@pytest.mark.parametrize(
    ("plot_type", "field_name", "parameter_name"),
    (
        ("forest", "x_lbl_le", "fp_xlabel"),
        ("regression", "x_lbl_le", "bp_xlabel"),
    ),
)
@pytest.mark.parametrize("dismissal", ["cancel", "escape", "close"])
def test_generated_plot_editor_dismissal_never_commits_or_regenerates(
    qapp, tmp_path, plot_type, field_name, parameter_name, dismissal
):

    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog(
        {parameter_name: "Committed label"},
        "plot.svg",
        plot_type=plot_type,
    )
    committed = []
    regenerations = []
    dialog.applied.connect(lambda: committed.append(dialog.plot_params()))
    dialog.applied.connect(lambda: regenerations.append(plot_type))
    try:
        dialog.show()
        qapp.processEvents()
        getattr(dialog, field_name).setText("Uncommitted draft")
        if dismissal == "cancel":
            cancel = dialog.buttonBox.button(
                QtWidgets.QDialogButtonBox.StandardButton.Cancel
            )
            assert cancel is not None
            cancel.click()
        elif dismissal == "escape":
            key_click(dialog, QtCore.Qt.Key.Key_Escape)
        else:
            dialog.close()
        qapp.processEvents()
        assert committed == []
        assert regenerations == []
    finally:
        _dispose(dialog, qapp)


@pytest.mark.parametrize(
    ("plot_type", "parameter_name"),
    (("forest", "fp_xlabel"), ("regression", "bp_xlabel")),
)
def test_generated_plot_editor_apply_then_cancel_preserves_only_committed_draft(
    qapp, tmp_path, plot_type, parameter_name
):

    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog(
        {parameter_name: "Original"}, "plot.svg", plot_type=plot_type
    )
    committed = []
    dialog.applied.connect(lambda: committed.append(dialog.plot_params()))
    try:
        dialog.show()
        qapp.processEvents()
        dialog.x_lbl_le.setText("Applied label")
        apply_button = dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        )
        cancel_button = dialog.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        assert apply_button is not None and cancel_button is not None
        apply_button.click()
        dialog.x_lbl_le.setText("Cancelled later draft")
        cancel_button.click()
        qapp.processEvents()
        assert [entry[parameter_name] for entry in committed] == ["Applied label"]
    finally:
        _dispose(dialog, qapp)


@pytest.mark.parametrize("plot_type", ["forest", "regression"])
def test_generated_plot_editor_ok_commits_once_and_accepts(qapp, tmp_path, plot_type):

    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog({}, "plot.svg", plot_type=plot_type)
    applied = QtTest.QSignalSpy(dialog.applied)
    accepted = QtTest.QSignalSpy(dialog.accepted)
    try:
        ok = dialog.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        qapp.processEvents()
        assert len(applied) == 1
        assert len(accepted) == 1
    finally:
        _dispose(dialog, qapp)


def test_plot_color_chooser_is_named_described_and_keyboard_focusable(qapp, tmp_path):

    _use_isolated_settings(tmp_path)
    dialog = plot_editor_dialog.EditPlotDialog({}, "plot.svg")
    try:
        dialog.show()
        dialog.color_btn.setFocus()
        qapp.processEvents()
        assert dialog.color_btn.accessibleName() == "Choose plot accent color"
        assert "color picker" in dialog.color_btn.accessibleDescription().lower()
        assert dialog.color_btn.toolTip() == "Choose the plot accent color"
        assert dialog.color_btn.hasFocus()
        assert dialog.color_btn.focusPolicy() == QtCore.Qt.FocusPolicy.StrongFocus
    finally:
        _dispose(dialog, qapp)


def test_plot_editor_keeps_scratch_plot_path_internal(qapp, tmp_path):
    _use_isolated_settings(tmp_path)
    for plot_type, prefix in (("forest", "fp"), ("regression", "bp")):
        initial = str(tmp_path / f"{plot_type}-initial.svg")
        dialog = plot_editor_dialog.EditPlotDialog(
            {f"{prefix}_outpath": initial}, "", plot_type=plot_type
        )
        try:
            assert dialog.image_path.text() == initial
            assert dialog.label_3.isHidden()
            assert dialog.image_path.isHidden()
            assert dialog.save_btn.isHidden()
            assert dialog.plot_params()[f"{prefix}_outpath"] == initial
        finally:
            _dispose(dialog, qapp)


def test_plot_editor_path_remains_available_to_internal_plot_parameters(qapp, tmp_path):
    _use_isolated_settings(tmp_path)
    initial = str(tmp_path / "forest-initial.svg")
    dialog = plot_editor_dialog.EditPlotDialog({"fp_outpath": initial}, "")
    try:
        assert dialog.plot_params()["fp_outpath"] == initial
    finally:
        _dispose(dialog, qapp)


@pytest.mark.parametrize(
    ("logical_extent", "device_pixel_ratio", "expected"),
    (
        (0.0, 1.0, 0),
        (0.5, 1.0, 1),
        (2.5, 1.0, 3),
        (515.0, 1.0, 515),
        (515.0, 1.25, 644),
        (515.0, 1.5, 773),
        (515.0, 1.75, 901),
    ),
)
def test_logical_extent_boundary_uses_qt_consistent_half_up_rounding(
    logical_extent, device_pixel_ratio, expected
):
    from rc_metastudio.qt_geometry import logical_extent_to_physical_pixels

    assert (
        logical_extent_to_physical_pixels(logical_extent, device_pixel_ratio)
        == expected
    )


@pytest.mark.parametrize(
    ("logical_extent", "device_pixel_ratio"),
    ((-1.0, 1.0), (1.0, 0.0), (1.0, -1.0), (float("nan"), 1.0), (1.0, float("inf"))),
)
def test_logical_extent_boundary_rejects_invalid_values(
    logical_extent, device_pixel_ratio
):
    from rc_metastudio.qt_geometry import logical_extent_to_physical_pixels

    with pytest.raises(ValueError):
        logical_extent_to_physical_pixels(logical_extent, device_pixel_ratio)
