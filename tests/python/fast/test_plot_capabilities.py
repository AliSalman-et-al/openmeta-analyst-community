import pytest

from rc_metastudio.analysis_results import parse_analysis_result
from rc_metastudio import plot_capabilities


def descriptor(**overrides):
    values = {
        "plot_kind": "forest",
        "editable": True,
        "styleable": True,
        "composition": "single",
        "regenerator": "forest",
    }
    values.update(overrides)
    return values


def test_validate_result_requires_one_descriptor_per_plot_artifact():
    with pytest.raises(ValueError, match="missing.*Forest Plot"):
        plot_capabilities.validate_result(
            {"images": {"Forest Plot": "forest.svg"}, "plot_capabilities": {}}
        )


def test_validate_result_rejects_unknown_capability_values():
    with pytest.raises(ValueError, match="plot_kind"):
        plot_capabilities.validate_result(
            {
                "images": {"Forest Plot": "forest.svg"},
                "image_params_paths": {"Forest Plot": "forest-data"},
                "plot_capabilities": {
                    "Forest Plot": descriptor(plot_kind="title_inferred_forest")
                },
            }
        )

    with pytest.raises(ValueError, match="composition"):
        plot_capabilities.validate_result(
            {
                "images": {"Forest Plot": "forest.svg"},
                "plot_capabilities": {
                    "Forest Plot": descriptor(
                        editable=False, composition="side_by_side"
                    )
                },
            }
        )


def test_validate_result_requires_plot_data_for_editable_artifacts():
    with pytest.raises(ValueError, match="missing plot data.*Forest Plot"):
        plot_capabilities.validate_result(
            {
                "images": {"Forest Plot": "forest.svg"},
                "plot_capabilities": {"Forest Plot": descriptor()},
            }
        )


def test_validate_result_returns_normalized_descriptors():
    capabilities = plot_capabilities.validate_result(
        {
            "images": {"Regression Plot": "regression.svg"},
            "image_params_paths": {"Regression Plot": "regression-data"},
            "plot_capabilities": {
                "Regression Plot": descriptor(
                    plot_kind="regression", regenerator="regression"
                )
            },
        }
    )

    assert capabilities["Regression Plot"] == descriptor(
        plot_kind="regression", regenerator="regression"
    )


def test_analysis_result_parser_validates_all_boundary_fields():
    parsed = parse_analysis_result(
        {
            "texts": {"Summary": "ok"},
            "images": {},
            "display_images": {},
            "image_var_names": {},
            "image_params_paths": {},
            "image_order": [],
            "plot_capabilities": {},
        }
    )

    assert parsed["texts"] == {"Summary": "ok"}
    assert parsed["image_order"] == []

    with pytest.raises(ValueError, match="texts keys and values must be text"):
        parse_analysis_result({"texts": {"Summary": 42}})
    with pytest.raises(ValueError, match="image_order must be a list of text"):
        parse_analysis_result({"image_order": ["Forest Plot", 42]})
    with pytest.raises(ValueError, match="Display artifacts have no matching"):
        parse_analysis_result({"display_images": {"Forest Plot": "display.svg"}})


def test_option_groups_are_keyed_by_explicit_plot_kind():
    assert "columns" in plot_capabilities.option_groups("forest")
    assert "columns" not in plot_capabilities.option_groups("cumulative_forest")
    assert "columns" not in plot_capabilities.option_groups("leave_one_out_forest")
    assert "columns" not in plot_capabilities.option_groups("subgroup_forest")
    assert "regression" in plot_capabilities.option_groups("regression")


def test_regenerator_is_resolved_from_a_safe_registry():
    assert plot_capabilities.regenerator_name("forest") == "generate_forest_plot"
    assert plot_capabilities.regenerator_name("regression") == "generate_reg_plot"
    assert plot_capabilities.regenerator_name("none") is None


def test_editable_plot_kind_requires_a_compatible_regenerator():
    with pytest.raises(ValueError, match="does not support plot kind"):
        plot_capabilities.validate_result(
            {
                "images": {"Regression Plot": "regression.svg"},
                "image_params_paths": {"Regression Plot": "regression-data"},
                "plot_capabilities": {
                    "Regression Plot": descriptor(
                        plot_kind="regression", regenerator="forest"
                    )
                },
            }
        )
