from pathlib import Path

import pytest

from rc_metastudio.publication_bias import (
    AsymmetryTestSpec,
    EligibilityReport,
    FunnelKind,
    FunnelPlotSpec,
    FunnelStyle,
    LabelPolicy,
    PooledDisplayModel,
    PooledDisplaySpec,
    SensitivitySpec,
    SmallStudyEffectsRequest,
    TestMethod,
    TrimAndFillEstimator,
    TrimAndFillModel,
)

ROOT = Path(__file__).resolve().parents[3]


def test_request_freezes_typed_test_ids_and_serializes_wire_names():
    request = SmallStudyEffectsRequest.create(
        data_type="binary", metric="OR", selected_tests=(TestMethod.HARBORD,)
    )
    assert request.to_mapping()["tests"] == ["harbord"]
    assert "options" not in request.to_mapping()
    with pytest.raises(ValueError, match="unsupported small-study effects test"):
        SmallStudyEffectsRequest.create(
            data_type="binary", metric="OR", selected_tests=("not-a-test",)
        )


def test_eligibility_parser_requires_the_dotted_rcmetar_schema():
    report = EligibilityReport.from_mapping(
        {
            "data.type": "binary",
            "metric": "OR",
            "usable.studies": 4,
            "raw.data.available": True,
            "precision.range": [0.1, 0.4],
            "package.versions": {"meta": "8.5-0"},
            "warnings": [],
            "methods": [
                {
                    "method": "harbord",
                    "available": True,
                    "reason": "",
                    "required.inputs": ["two-arm counts"],
                    "usable.studies": 4,
                    "warnings": [],
                    "role": "primary",
                }
            ],
        }
    )
    assert report.usable_studies == 4
    assert report.primary_method is not None
    assert report.primary_method.role == "primary"
    assert report.primary_method.available
    assert report.package_versions == (("meta", "8.5-0"),)


def test_eligibility_parser_rejects_incomplete_wire_entries():
    with pytest.raises(ValueError, match="eligibility method is missing fields"):
        EligibilityReport.from_mapping(
            {
                "data.type": "continuous",
                "metric": "MD",
                "usable.studies": 4,
                "raw.data.available": False,
                "precision.range": [0.1, 0.4],
                "package.versions": {"meta": "8.5-0"},
                "warnings": [],
                "methods": [{"method": "classical-egger"}],
            }
        )


def test_eligibility_parser_normalizes_scalarized_single_method_mapping():
    report = EligibilityReport.from_mapping(
        {
            "data.type": "diagnostic",
            "metric": "DOR",
            "usable.studies": 4,
            "raw.data.available": True,
            "precision.range": [0.1, 0.4],
            "package.versions": {"meta": "8.5-0"},
            "warnings": "one warning",
            "methods": {
                "method": "deeks",
                "available": True,
                "reason": "",
                "usable.studies": 4,
                "required.inputs": [],
                "warnings": "one method warning",
                "role": "primary",
            },
        }
    )
    assert len(report.methods) == 1
    assert report.methods[0].method == "deeks"
    assert report.warnings == ("one warning",)
    assert report.methods[0].warnings == ("one method warning",)


def test_request_has_explicit_frozen_plot_test_sensitivity_and_pool_specs():
    request = SmallStudyEffectsRequest(
        data_type="continuous",
        metric="MD",
        plot_specs=(FunnelPlotSpec(FunnelKind.ORDINARY),),
        test_specs=(AsymmetryTestSpec(TestMethod.CLASSICAL_EGGER),),
        sensitivity_specs=(SensitivitySpec(),),
        pooled_display=PooledDisplaySpec(PooledDisplayModel.COMMON),
    )
    assert request.to_mapping()["funnels"] == ["ordinary"]
    assert request.to_mapping()["tests"] == ["classical-egger"]
    assert request.to_mapping()["pooled.display.model"] == "common"
    with pytest.raises(AttributeError):
        request.__setattr__("metric", "SMD")


def test_dialog_keeps_test_selection_inside_authoritative_eligibility():
    request = SmallStudyEffectsRequest.create(
        data_type="continuous",
        metric="MD",
        selected_tests=(TestMethod.CLASSICAL_EGGER, TestMethod.MIXED_EFFECTS_EGGER),
    )
    assert request.to_mapping()["tests"] == ["classical-egger", "mixed-effects-egger"]
    ui = (ROOT / "src/rc_metastudio/forms/publication_bias_dialog.ui").read_text(
        encoding="utf-8"
    )
    assert 'name="automatic_test_label"' in ui
    assert 'name="classical_egger_check"' not in ui
    assert 'name="primary_method_combo"' not in ui
    source = (ROOT / "src/rc_metastudio/publication_bias_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "item.available" in source


def test_contour_plot_spec_serializes_presentation_controls_without_options_bag():
    request = SmallStudyEffectsRequest.create(
        data_type="continuous",
        metric="MD",
        selected_funnels=(FunnelKind.ORDINARY, FunnelKind.CONTOUR),
        label_policy=LabelPolicy.ALL,
        sampling_confidence_level=90,
        include_tau2=True,
        point_size=1.5,
        reference_line_visible=False,
        pooled_overlay_visible=False,
    )
    wire = request.to_mapping()
    assert wire["funnels"] == ["ordinary", "contour"]
    assert wire["funnel.label.policy"] == ["all", "all"]
    assert wire["funnel.sampling.conf.level"] == [90.0, 90.0]
    assert wire["funnel.sampling.region.visible"] == [True, True]
    assert "funnel.show.sampling.region" not in wire
    assert wire["funnel.include.tau2"] == [True, True]
    assert wire["funnel.point.size"] == [1.5, 1.5]
    assert wire["funnel.reference.visible"] == [False, False]
    assert wire["funnel.pooled.overlay.visible"] == [False, False]
    assert wire["funnel.style"] == ["default", "default"]
    assert wire["funnel.point.symbol"] == [19, 19]
    assert "options" not in wire


@pytest.mark.parametrize(
    ("style", "symbol", "color"),
    [
        (FunnelStyle.DEFAULT, 19, "#2F5597"),
        (FunnelStyle.REVMAN, 15, "#111111"),
        (FunnelStyle.BMJ, 18, "#6B58A6"),
    ],
)
def test_funnel_style_variants_serialize_the_shared_visual_preset(
    style, symbol, color
):
    wire = SmallStudyEffectsRequest.create(
        data_type="continuous", metric="MD", style=style
    ).to_mapping()
    assert wire["funnel.style"] == [style.value]
    assert wire["funnel.point.symbol"] == [symbol]
    assert wire["funnel.point.color"] == [color]


def test_contour_levels_are_only_valid_for_contour_specs():
    with pytest.raises(ValueError, match="contour levels apply only"):
        FunnelPlotSpec(FunnelKind.ORDINARY, contour_levels=(90.0,))


def test_create_applies_custom_contour_levels_only_to_contour_specs():
    request = SmallStudyEffectsRequest.create(
        data_type="continuous",
        metric="MD",
        selected_funnels=(FunnelKind.ORDINARY, FunnelKind.CONTOUR),
        contour_levels=(85.0, 95.0),
    )
    assert request.plot_specs[0].contour_levels == ()
    assert request.plot_specs[1].contour_levels == (85.0, 95.0)
    assert request.to_mapping()["funnel.contour.levels"] == ["", "85,95"]


def test_publication_bias_action_is_exposed_for_the_release():
    source = (ROOT / "src/rc_metastudio/main_window.py").read_text(encoding="utf-8")
    assert "self.action_publication_bias.setVisible(False)" not in source
    assert "self.action_publication_bias.setEnabled(enable)" in source


def test_publication_bias_icons_are_funnel_plot_glyphs_without_warning_symbols():
    for relative_path, center in (
        ("src/rc_metastudio/images/icons/analyses/publication-bias.svg", "M24 7v35"),
        ("src/rc_metastudio/images/icons/analyses/compact/publication-bias.svg", "M10 3v15"),
    ):
        svg = (ROOT / relative_path).read_text(encoding="utf-8")
        assert center in svg
        assert "stroke-dasharray" in svg
        assert svg.count("<circle") >= 4
        assert "!" not in svg
        assert "#edf2fb" not in svg
        assert "<rect" not in svg


def test_canonical_dialog_matches_method_and_plots_tabs():
    ui = (ROOT / "src/rc_metastudio/forms/publication_bias_dialog.ui").read_text(
        encoding="utf-8"
    )
    assert ui.count('class="QScrollArea"') == 2
    assert "Method &amp; Parameters" in ui
    assert ">Method<" in ui
    assert ">Plots<" in ui
    assert ">Options<" not in ui
    assert ui.index(">Method<") < ui.index(">Plots<")
    assert 'name="progress_bar"' in ui
    assert "QDialogButtonBox::Cancel|QDialogButtonBox::Ok" in ui


def test_dialog_uses_application_modal_progress_and_failure_safe_execution():
    source = (ROOT / "src/rc_metastudio/publication_bias_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "Qt.WindowModality.ApplicationModal" in source
    assert "self.setModal(True)" in source
    assert "self.progress_bar.setRange(0, 0)" in source
    assert "self.failure_label.setText(str(error))" in source


def test_trimfill_request_serializes_estimator_model_side_and_extrapolation():
    request = SmallStudyEffectsRequest.create(
        data_type="continuous",
        metric="MD",
        trim_and_fill=True,
        trim_and_fill_estimator=TrimAndFillEstimator.R0,
        trim_and_fill_side="right",
        trim_and_fill_model=TrimAndFillModel.COMMON,
        extrapolation=True,
    )
    wire = request.to_mapping()
    assert wire["trim.and.fill"] is True
    assert wire["trim.and.fill.estimator"] == "R0"
    assert wire["trim.and.fill.side"] == "right"
    assert wire["trim.and.fill.model"] == "common"
    assert wire["extrapolation"] is True
    ui = (ROOT / "src/rc_metastudio/forms/publication_bias_dialog.ui").read_text(
        encoding="utf-8"
    )
    for control in (
        "trim_fill_estimator_combo",
        "trim_fill_side_combo",
        "trim_fill_model_combo",
        "extrapolation_check",
    ):
        assert f'name="{control}"' in ui


def test_diagnostic_request_is_read_only_dor_and_deeks_only():
    request = SmallStudyEffectsRequest.create(
        data_type="diagnostic", metric="DOR", selected_funnels=(FunnelKind.ORDINARY,)
    )
    wire = request.to_mapping()
    assert wire["metric"] == "DOR"
    assert wire["funnels"] == ["deeks"]
    with pytest.raises(ValueError, match="read-only DOR"):
        SmallStudyEffectsRequest.create(data_type="diagnostic", metric="Sens")
    source = (ROOT / "src/rc_metastudio/publication_bias_dialog.py").read_text(
        encoding="utf-8"
    )
    assert 'metric = "DOR" if data_type == "diagnostic"' in source
    assert "self.ordinary_funnel_check.setEnabled(not deeks)" in source
