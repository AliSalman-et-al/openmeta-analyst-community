# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from rc_metastudio.analysis_results import parse_analysis_result


def test_section_identity_and_order_are_explicit_and_title_independent():
    result = parse_analysis_result(
        {
            "version": 1,
            "texts": {"summary": "headline"},
            "images": {"forest": "forest.png"},
            "image_params_paths": {"forest": "plot-data"},
            "plot_capabilities": {
                "forest": {
                    "plot_kind": "forest",
                    "editable": True,
                    "styleable": True,
                    "composition": "single",
                    "regenerator": "forest",
                }
            },
            "sections": [
                {
                    "id": "headline",
                    "kind": "text",
                    "order": 0,
                    "title": "Summary",
                    "source_key": "summary",
                },
                {
                    "id": "primary-plot",
                    "kind": "image",
                    "order": 1,
                    "title": "Forest Plot",
                    "source_key": "forest",
                },
            ],
        }
    )

    assert [(section.semantic_id, section.order) for section in result.sections] == [
        ("headline", 0),
        ("primary-plot", 1),
    ]
    assert result.sections[0].title == "Summary"


def test_section_identity_survives_display_title_change():
    base = {
        "version": 1,
        "texts": {"summary": "headline"},
        "sections": [
            {
                "id": "headline",
                "kind": "text",
                "order": 0,
                "title": "Summary",
                "source_key": "summary",
            }
        ],
    }
    renamed = {
        "version": 1,
        "texts": {"summary": "headline"},
        "sections": [
            {
                "id": "headline",
                "kind": "text",
                "order": 0,
                "title": "Meta-Analysis Summary",
                "source_key": "summary",
            }
        ],
    }
    assert (
        parse_analysis_result(base).sections[0].semantic_id
        == parse_analysis_result(renamed).sections[0].semantic_id
    )


def test_nonempty_results_require_explicit_versioned_sections():
    import pytest

    with pytest.raises(ValueError, match="result version"):
        parse_analysis_result({"texts": {}, "sections": []})
    with pytest.raises(ValueError, match="sections are required"):
        parse_analysis_result({"version": 1, "texts": {"summary": "headline"}})
    with pytest.raises(ValueError, match="cover every text and image"):
        parse_analysis_result(
            {"version": 1, "texts": {"summary": "headline"}, "sections": []}
        )
