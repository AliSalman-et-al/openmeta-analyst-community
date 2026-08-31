from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QWidget

from rc_metastudio.qt6_ui import prepare_generated_ui_imports

prepare_generated_ui_imports()

from rc_metastudio import publication_bias_dialog


class _Model:
    def __init__(self, data_type, metric, confidence_level=95.0):
        self._data_type = data_type
        self.current_effect = metric
        self._confidence_level = confidence_level
        self.dataset: object | None = None

    def get_current_outcome_type(self):
        return self._data_type

    def get_confidence_level(self):
        return self._confidence_level


class _Owner(QWidget):
    analysis: Callable[[object], None]


def _method(method, available, role="none", reason=""):
    return {
        "method": method,
        "available": available,
        "reason": reason,
        "usable.studies": 10,
        "required.inputs": [],
        "warnings": [],
        "role": role,
    }


def _report(data_type, metric, methods, raw_data_available=True, warnings=None):
    return {
        "data.type": data_type,
        "metric": metric,
        "usable.studies": 10,
        "raw.data.available": raw_data_available,
        "precision.range": [0.1, 0.4],
        "package.versions": {"meta": "8.5-0", "metafor": "5.0-1"},
        "warnings": [] if warnings is None else warnings,
        "methods": methods,
    }


def test_dialog_matches_standard_method_and_plots_structure(qapp, monkeypatch):
    report = _report("continuous", "MD", [_method("classical-egger", True, "primary")])
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("continuous", "MD"))
    try:
        assert dialog.windowTitle() == "Method & Parameters"
        assert dialog.tabs.count() == 2
        assert [dialog.tabs.tabText(i) for i in range(2)] == ["Method", "Plots"]
        assert dialog.findChild(type(dialog.plots_scroll), "methods_scroll") is not None
        assert not hasattr(dialog, "primary_method_combo")
        assert not hasattr(dialog, "classical_egger_check")
        assert dialog.button_box.button(QDialogButtonBox.StandardButton.Ok) is not None
        assert dialog.methods_scroll_content.isAncestorOf(dialog.plot_selection_group)
        assert dialog.methods_scroll_content.isAncestorOf(dialog.include_tau2_check)
        assert dialog.plots_scroll_content.isAncestorOf(dialog.presentation_group)
        assert not dialog.plots_scroll_content.isAncestorOf(dialog.contour_levels_edit)
        assert dialog.sampling_confidence_combo.currentText() == "95"
        assert dialog.style_combo.currentText() == "Default (metafor)"
        dialog.style_combo.setCurrentText("RevMan")
        assert dialog._request().to_mapping()["funnel.style"] == ["revman"]
        assert dialog._request().to_mapping()["funnel.point.symbol"] == [15]
        assert dialog.trim_fill_group.isHidden()
        dialog.trim_fill_check.setChecked(True)
        assert not dialog.trim_fill_group.isHidden()
    finally:
        dialog.close()


def test_dialog_reports_authoritative_automatic_tests_without_selection_controls(
    qapp, monkeypatch
):
    report = _report(
        "binary",
        "OR",
        [
            _method("harbord", True, "primary"),
            _method("rucker-as-re", True, "sensitivity"),
            _method("peters", True, "sensitivity"),
        ],
    )
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("binary", "OR"))
    try:
        assert dialog.automatic_test_label.text() == (
            "Primary: Harbord\nAdditional: Rücker AS+RE, Peters"
        )
        assert dialog._request().to_mapping()["tests"] == [
            "harbord",
            "rucker-as-re",
            "peters",
        ]
    finally:
        dialog.close()


def test_diagnostic_request_does_not_select_unavailable_deeks(qapp, monkeypatch):
    report = _report(
        "diagnostic",
        "DOR",
        [_method("deeks", False, reason="Complete TP/FN/FP/TN counts are required.")],
        raw_data_available=False,
    )
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("diagnostic", "DOR"))
    try:
        assert dialog._request().to_mapping()["tests"] == []
        assert dialog._request().to_mapping()["funnels"] == ["deeks"]
        assert dialog.sensitivity_group.isHidden()
    finally:
        dialog.close()


def test_correction_policy_refreshes_authoritative_or_routing(qapp, monkeypatch):
    policies = []

    def preview(_model, request, preview=False):
        policy = request.get("correction.policy")
        policies.append(policy)
        primary = "rucker-as-re" if policy == "All studies" else "harbord"
        return _report(
            "binary",
            "OR",
            [_method(primary, True, "primary")],
        )

    monkeypatch.setattr(publication_bias_dialog.r_bridge, "run_small_study_effects", preview)
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("binary", "OR"))
    try:
        assert dialog.automatic_test_label.text() == "Primary: Harbord"
        dialog.correction_policy_combo.setCurrentText("All studies")
        assert dialog.automatic_test_label.text() == "Primary: Rücker AS+RE"
        assert "All studies" in policies
    finally:
        dialog.close()


def test_context_is_compact_and_distinguishes_included_and_eligible_counts(qapp, monkeypatch):
    report = _report("continuous", "MD", [_method("classical-egger", True, "primary")])
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    model = _Model("continuous", "MD")
    model.dataset = SimpleNamespace(
        studies=[SimpleNamespace(include=True), SimpleNamespace(include=False)]
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(model)
    try:
        assert dialog.context_label.text() == (
            "Continuous  ·  Mean Difference (MD)  ·  1 included  ·  10 eligible"
        )
    finally:
        dialog.close()


def test_singleton_r_warning_is_accepted_at_dialog_boundary(qapp, monkeypatch):
    report = _report(
        "continuous",
        "MD",
        [_method("classical-egger", True, "primary")],
        warnings="Observed precision range",
    )
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("continuous", "MD"))
    try:
        assert dialog.automatic_test_label.text() == "Primary: Classical Egger"
    finally:
        dialog.close()


def test_correction_group_is_hidden_without_raw_count_eligibility(qapp, monkeypatch):
    report = _report("continuous", "MD", [_method("classical-egger", True)], raw_data_available=False)
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("continuous", "MD"))
    try:
        assert not dialog.correction_group.isVisible()
        assert not dialog.correction_policy_combo.isEnabled()
    finally:
        dialog.close()


def test_correction_group_is_hidden_for_one_arm_proportion(qapp, monkeypatch):
    report = _report("binary", "PR", [], raw_data_available=True)
    captured = []

    def preview(_model, request, preview=False):
        captured.append(request)
        return report

    monkeypatch.setattr(publication_bias_dialog.r_bridge, "run_small_study_effects", preview)
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("binary", "PR"))
    try:
        assert not dialog.correction_group.isVisible()
        assert not dialog.correction_policy_combo.isEnabled()
        assert all("correction.policy" not in request for request in captured)
        assert "correction.policy" not in dialog._request().to_mapping()
    finally:
        dialog.close()


def test_failure_is_reported_in_dedicated_label(qapp, monkeypatch):
    report = _report("continuous", "MD", [_method("classical-egger", True)])
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    monkeypatch.setattr(
        publication_bias_dialog,
        "execute_small_study_effects",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("run failed")),
    )
    monkeypatch.setattr(publication_bias_dialog.app_error_handler, "handle_exception", lambda *args, **kwargs: None)
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("continuous", "MD"))
    try:
        dialog.run()
        assert dialog.failure_label.text() == "run failed"
        assert not dialog.failure_label.isHidden()
    finally:
        dialog.close()


def test_successful_run_delivers_results_and_closes_dialog(qapp, monkeypatch):
    report = _report("continuous", "MD", [_method("classical-egger", True)])
    monkeypatch.setattr(
        publication_bias_dialog.r_bridge,
        "run_small_study_effects",
        lambda *args, **kwargs: report,
    )
    delivered = []
    owner = _Owner()
    owner.analysis = delivered.append
    monkeypatch.setattr(
        publication_bias_dialog,
        "execute_small_study_effects",
        lambda *args, **kwargs: {"sections": []},
    )
    dialog = publication_bias_dialog.PublicationBiasDialog(_Model("continuous", "MD"), owner)
    try:
        dialog.run()
        assert delivered == [{"sections": []}]
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()
        owner.close()
