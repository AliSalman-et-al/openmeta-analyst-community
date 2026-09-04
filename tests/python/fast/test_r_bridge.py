from rc_metastudio.analysis_results import parse_analysis_result
from rc_metastudio.r_bridge import _text_section_metadata


def test_expanded_summary_sections_keep_metadata_but_point_to_child_values():
    sources = {
        "Clinical interpretation": ("Summary", 0),
        "Model information": ("Summary", 1),
    }
    producer_sections = [
        {
            "id": "diagnostic.reitsma.meta.regression.summary",
            "kind": "text",
            "order": 0,
            "title": "Summary",
            "source_key": "Summary",
        }
    ]

    sections = _text_section_metadata(sources, producer_sections)
    result = parse_analysis_result(
        {
            "version": 1,
            "texts": {
                "Clinical interpretation": "joint model",
                "Model information": "REML",
            },
            "sections": sections,
        }
    )

    assert [(section.semantic_id, section.title, section.source_key) for section in result.sections] == [
        (
            "diagnostic.reitsma.meta.regression.summary",
            "Summary",
            "Clinical interpretation",
        ),
        (
            "diagnostic.reitsma.meta.regression.summary:2",
            "Model information",
            "Model information",
        ),
    ]
