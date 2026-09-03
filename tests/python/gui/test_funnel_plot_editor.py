from pathlib import Path

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QDialog, QDialogButtonBox

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()

from rc_metastudio import funnel_plot_editor_dialog, results_window
from rc_metastudio.funnel_plot_editor_dialog import FunnelPlotEditorDialog


def _params(kind):
    return {
        "funnel.kind": kind,
        "metric": "OR",
        "trim.and.fill.estimator": "L0",
        "trim.and.fill.side": "left",
        "deeks.ess": [12.0, 20.0],
        "funnel.point.size": 1.0,
        "funnel.label.policy": "none",
    }


def test_funnel_editor_preserves_statistical_params_and_updates_presentation(qapp):
    dialog = FunnelPlotEditorDialog(
        _params("ordinary"), "ordinary.png", plot_type="funnel"
    )
    try:
        dialog.point_size_spin.setValue(2.0)
        dialog.point_color_edit.setText("#123456")
        dialog.label_policy_combo.setCurrentText("All")
        dialog.reference_visible_check.setChecked(False)
        params = dialog.plot_params()
        assert params["trim.and.fill.estimator"] == "L0"
        assert params["trim.and.fill.side"] == "left"
        assert params["deeks.ess"] == [12.0, 20.0]
        assert params["funnel.kind"] == "ordinary"
        assert params["funnel.point.size"] == 2.0
        assert params["funnel.point.color"] == "#123456"
        assert params["funnel.label.policy"] == "all"
        assert params["funnel.reference.visible"] is False
    finally:
        dialog.close()


def test_funnel_editor_supports_visual_presets_symbols_and_color_picker(
    qapp, monkeypatch
):
    dialog = FunnelPlotEditorDialog(
        _params("ordinary"), "ordinary.png", plot_type="funnel"
    )
    monkeypatch.setattr(
        funnel_plot_editor_dialog.QColorDialog,
        "getColor",
        lambda *args, **kwargs: QColor("#AABBCC"),
    )
    try:
        dialog.style_combo.setCurrentText("BMJ")
        assert dialog.point_color_edit.text() == "#6B58A6"
        assert dialog.reference_color_edit.text() == "#6B58A6"
        assert dialog.region_color_edit.text() == "#E8E2F4"
        assert dialog.point_symbol_combo.currentText() == "Diamond"
        dialog.background_color_button.click()

        params = dialog.plot_params()
        assert params["funnel.style"] == "bmj"
        assert params["funnel.point.symbol"] == 18
        assert params["funnel.background.color"] == "#AABBCC"
        assert "background-color" in dialog.background_color_button.styleSheet()
    finally:
        dialog.close()


def test_funnel_editor_disables_inapplicable_controls_by_kind(qapp):
    contour = FunnelPlotEditorDialog(
        _params("contour"), "contour.png", plot_type="contour_funnel"
    )
    deeks = FunnelPlotEditorDialog(
        _params("deeks"), "deeks.png", plot_type="deeks_funnel"
    )
    trimfill = FunnelPlotEditorDialog(
        _params("trimfill"), "trimfill.png", plot_type="trimfill_funnel"
    )
    try:
        assert contour.contour_levels_edit.isEnabled()
        assert not contour.sampling_region_check.isEnabled()
        assert (
            deeks.label_policy_combo.findText("Outside pseudo-confidence region") == -1
        )
        assert not deeks.sampling_confidence_spin.isEnabled()
        assert deeks.regression_visible_check.isEnabled()
        assert trimfill.kind_label.text() == "Funnel kind: trimfill"
        assert "estimator" in trimfill.rerun_note.text()
    finally:
        for dialog in (contour, deeks, trimfill):
            dialog.close()


def test_funnel_editor_rejects_kind_descriptor_mismatch(qapp):
    try:
        FunnelPlotEditorDialog(_params("trimfill"), "ordinary.png", plot_type="funnel")
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("mismatched funnel descriptor was accepted")


def test_funnel_editor_reads_persisted_second_plot_settings_by_index(qapp):
    params = _params("contour")
    params.update(
        {
            "funnel.index": 2,
            "funnel.point.size": [1.0, 2.0],
            "funnel.label.policy": ["none", "all"],
            "funnel.xlab": ["first", "second"],
            "funnel.ylab": ["one", "two"],
        }
    )
    dialog = FunnelPlotEditorDialog(params, "contour.png", plot_type="contour_funnel")
    try:
        assert dialog.point_size_spin.value() == 2.0
        assert dialog.label_policy_combo.currentText() == "All"
        assert dialog.x_label_edit.text() == "second"
        assert dialog.y_label_edit.text() == "two"
    finally:
        dialog.close()


def test_funnel_editor_prefers_persisted_output_path_on_reopen(qapp, tmp_path):
    persisted = tmp_path / "edited-funnel.png"
    dialog = FunnelPlotEditorDialog(
        {**_params("ordinary"), "funnel.outpath": str(persisted)},
        str(tmp_path / "original-funnel.png"),
        plot_type="funnel",
    )
    try:
        assert dialog.path_edit.text() == str(persisted)
    finally:
        dialog.close()


def test_funnel_editor_apply_then_ok_does_not_regenerate_twice(qapp):
    dialog = FunnelPlotEditorDialog(
        _params("ordinary"), "ordinary.png", plot_type="funnel"
    )
    applied = []
    dialog.applied.connect(
        lambda: (applied.append(True), dialog.mark_commit_succeeded())
    )
    try:
        apply_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Apply)
        ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert apply_button is not None
        assert ok_button is not None
        apply_button.click()
        assert len(applied) == 1
        ok_button.click()
        assert len(applied) == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()


def test_funnel_editor_ok_commits_new_change_and_closes(qapp):
    dialog = FunnelPlotEditorDialog(
        _params("ordinary"), "ordinary.png", plot_type="funnel"
    )
    applied = []
    dialog.applied.connect(
        lambda: (applied.append(True), dialog.mark_commit_succeeded())
    )
    try:
        dialog.point_size_spin.setValue(2.0)
        ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.click()
        assert len(applied) == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()


def test_funnel_editor_ok_commits_combo_only_change(qapp):
    dialog = FunnelPlotEditorDialog(
        _params("ordinary"), "ordinary.png", plot_type="funnel"
    )
    applied = []
    dialog.applied.connect(
        lambda: (applied.append(dialog.plot_params()), dialog.mark_commit_succeeded())
    )
    try:
        dialog.label_policy_combo.setCurrentText("All")
        ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.click()
        assert len(applied) == 1
        assert applied[0]["funnel.label.policy"] == "all"
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()


def test_funnel_editor_failed_commit_stays_dirty_and_open(qapp):
    dialog = FunnelPlotEditorDialog(
        _params("ordinary"), "ordinary.png", plot_type="funnel"
    )
    dialog.applied.connect(dialog.mark_commit_failed)
    try:
        dialog.point_size_spin.setValue(2.0)
        ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.click()
        assert dialog._dirty
        assert dialog.result() == 0
    finally:
        dialog.close()


def test_funnel_editor_failed_second_apply_preserves_last_good_artifacts(
    qapp, monkeypatch, tmp_path
):
    base = tmp_path / "funnel"
    params_path = Path(str(base) + ".params")
    params_path.write_text("initial", encoding="utf-8")
    Path(str(base) + ".data").write_text("data", encoding="utf-8")
    Path(str(base) + ".res").write_text("res", encoding="utf-8")
    image_path = tmp_path / "funnel.png"
    image_path.write_bytes(b"old image")
    artifact = results_window.PlotArtifact(
        "Ordinary Funnel Plot",
        str(image_path),
        {"plot_kind": "funnel", "regenerator": "funnel"},
        params_path=str(base),
    )
    window = results_window.ResultsWindow.__new__(results_window.ResultsWindow)
    window._refresh_plot_item = lambda *args: None
    regenerate_count = [0]

    def write_params(params, **kwargs):
        Path(kwargs["outpath"]).write_text(
            repr(sorted(params.items())), encoding="utf-8"
        )

    def regenerate(_params_path, output_path=None):
        regenerate_count[0] += 1
        if regenerate_count[0] == 1:
            assert output_path is not None
            Path(output_path).write_bytes(b"first good image")
            return output_path
        raise RuntimeError("render failed")

    monkeypatch.setattr(
        results_window.r_bridge, "update_plot_params", write_params, raising=False
    )
    monkeypatch.setattr(
        results_window.r_bridge,
        "regenerate_small_study_effects_funnel",
        regenerate,
        raising=False,
    )
    dialog = FunnelPlotEditorDialog(
        {"funnel.kind": "ordinary", "funnel.point.size": 1.0},
        str(image_path),
        plot_type="funnel",
    )
    try:
        dialog.point_size_spin.setValue(2.0)
        window._apply_funnel_plot_edits(dialog, artifact, None)
        committed_params = params_path.read_bytes()
        committed_image = image_path.read_bytes()
        dialog.point_size_spin.setValue(3.0)
        with pytest.raises(RuntimeError, match="render failed"):
            window._apply_funnel_plot_edits(dialog, artifact, None)
        assert params_path.read_bytes() == committed_params
        assert image_path.read_bytes() == committed_image
        assert dialog._dirty
        assert dialog.result() == 0
    finally:
        dialog.close()


def test_funnel_editor_rejects_svgz_output_path(qapp):
    artifact = results_window.PlotArtifact(
        "Ordinary Funnel Plot",
        "funnel.png",
        {"plot_kind": "funnel", "regenerator": "funnel"},
        params_path="funnel",
    )
    window = results_window.ResultsWindow.__new__(results_window.ResultsWindow)

    class Dialog:
        def plot_params(self):
            return {"funnel.outpath": "edited-funnel.svgz"}

    with pytest.raises(ValueError, match="SVGZ output is not supported"):
        window._apply_funnel_plot_edits(Dialog(), artifact, None)
