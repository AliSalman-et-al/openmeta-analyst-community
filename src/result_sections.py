import re
from collections import namedtuple


OPENMETA_ANALYST_REFERENCE = (
    'OpenMetaAnalyst: Wallace, Byron C., Issa J. Dahabreh, Thomas A. Trikalinos, '
    'Joseph Lau, Paul Trow, and Christopher H. Schmid. "Closing the Gap between '
    'Methodologists and End-Users: R as a Computational Back-End." Journal of '
    'Statistical Software 49 (2012): 5."'
)


REFERENCE_SECTION_TITLE = "References"
WEIGHTS_SECTION_TITLE = "Weights"

DisplaySection = namedtuple(
    "DisplaySection", ["kind", "key", "display_title", "value"]
)


DIAGNOSTIC_SECTION_GROUPS = (
    ("sens", "spec", "bivariate"),
    ("likelihood", "nlr", "plr"),
)

HSROC_SECTION_TITLES = {
    "Between-study parameters": "HSROC Model Parameters",
    "Within-study parameters": "Study-Level Parameters",
    "Within-study parameters - theta": "Study-Level Threshold Parameters",
    "Within-study parameters - alpha": "Study-Level Accuracy Parameters",
    "Within-study parameters - pi": "Study-Level Prevalence Parameters",
    "Within-study parameters - S1": "Study-Level Sensitivity Parameters",
    "Within-study parameters - C1": "Study-Level Specificity Parameters",
}

SECTION_TITLE_REPLACEMENTS = {
    "NLR and PLR Forest Plot": "Negative and Positive Likelihood Ratio Forest Plot",
    "Density plots": "Density Plots",
    "Trace plots": "Trace Plots",
    "Leave-one-out Forest plot": "Leave-One-Out Forest Plot",
}


def format_references(references):
    ordered_references = dedupe_references_preserving_order(
        list(references) + [OPENMETA_ANALYST_REFERENCE]
    )
    return "".join(
        "%d. %s\n" % (index + 1, reference)
        for index, reference in enumerate(ordered_references)
    )


def dedupe_references_preserving_order(references):
    seen = set()
    deduped = []
    for reference in references:
        normalized = _reference_key(reference)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(str(reference))
    return deduped


def order_text_sections(items, include_references=False):
    ordered = _group_items(
        [
            (title, value)
            for title, value in items
            if include_references or title != REFERENCE_SECTION_TITLE
        ],
        *DIAGNOSTIC_SECTION_GROUPS
    )
    if include_references:
        return ordered
    return ordered


def order_image_sections(items, explicit_order=None):
    item_dict = dict(items)
    if explicit_order is not None:
        return [
            (title, item_dict[title]) for title in explicit_order if title in item_dict
        ]
    return _group_items(list(items), *DIAGNOSTIC_SECTION_GROUPS)


def order_display_sections(texts, images, explicit_image_order=None):
    context = _section_context(texts, images)
    text_sections = [
        DisplaySection("text", title, section_display_title(title, context), value)
        for title, value in order_text_sections(texts)
    ]
    image_sections = [
        DisplaySection("image", title, section_display_title(title, context), value)
        for title, value in order_image_sections(images, explicit_order=explicit_image_order)
    ]

    if _is_hsroc_result(context):
        return _order_hsroc_sections(text_sections, image_sections)
    if _is_standard_meta_analysis_result(context):
        return _order_standard_meta_analysis_sections(text_sections, image_sections)
    return text_sections + image_sections


def section_display_title(title, context=None):
    if context is None:
        context = {"text_titles": [], "image_titles": []}

    if title == "Summary":
        if "Regression Plot" in context["image_titles"]:
            return "Meta-Regression Summary"
        return "Meta-Analysis Summary"
    if title in HSROC_SECTION_TITLES:
        return HSROC_SECTION_TITLES[title]
    if title in SECTION_TITLE_REPLACEMENTS:
        return SECTION_TITLE_REPLACEMENTS[title]
    return title


def pop_references_section(texts):
    texts_without_references = dict(texts)
    references = texts_without_references.pop(REFERENCE_SECTION_TITLE, None)
    return texts_without_references, references


def _section_context(texts, images):
    return {
        "text_titles": [title for title, _value in texts],
        "image_titles": [title for title, _value in images],
    }


def _is_standard_meta_analysis_result(context):
    return (
        "Summary" in context["text_titles"]
        and WEIGHTS_SECTION_TITLE in context["text_titles"]
        and any(_is_primary_plot_title(title) for title in context["image_titles"])
    )


def _is_hsroc_result(context):
    titles = set(context["text_titles"]) | set(context["image_titles"])
    return bool(
        {
            "Clinical Accuracy Summary",
            "Summary ROC",
            "Between-study parameters",
            "HSROC Model Parameters",
        }
        & titles
    )


def _order_standard_meta_analysis_sections(text_sections, image_sections):
    summary = _matching_sections(text_sections, lambda section: section.key == "Summary")
    weights = _matching_sections(
        text_sections, lambda section: section.key == WEIGHTS_SECTION_TITLE
    )
    other_text = [
        section
        for section in text_sections
        if section.key not in ("Summary", WEIGHTS_SECTION_TITLE)
    ]
    primary_images = _matching_sections(
        image_sections, lambda section: _is_primary_plot_title(section.key)
    )
    other_images = [
        section for section in image_sections if not _is_primary_plot_title(section.key)
    ]
    return summary + primary_images + weights + other_text + other_images


def _order_hsroc_sections(text_sections, image_sections):
    combined = text_sections + image_sections
    return sorted(combined, key=lambda section: _hsroc_priority(section))


def _hsroc_priority(section):
    title = section.key
    priority_by_title = {
        "Clinical Accuracy Summary": 0,
        "Summary": 0,
        "Summary ROC": 1,
        "HSROC Model Parameters": 2,
        "Between-study parameters": 2,
        "Within-study parameters": 3,
        "Within-study parameters - theta": 3,
        "Within-study parameters - alpha": 3,
        "Within-study parameters - pi": 3,
        "Within-study parameters - S1": 3,
        "Within-study parameters - C1": 3,
        "Density plots": 4,
        "Trace plots": 5,
    }
    return (priority_by_title.get(title, 6), section.kind, title)


def _matching_sections(sections, predicate):
    return [section for section in sections if predicate(section)]


def _is_primary_plot_title(title):
    return title in ("Forest Plot", "Regression Plot", "ROC Plot")


def _group_items(items, *groups):
    def _get_group_id(key):
        for group_id, group in enumerate(groups):
            for group_member in group:
                if key.lower().find(group_member.lower()) != -1:
                    return group_id
        return None

    grouped_items = []
    for _index in range(len(groups) + 1):
        grouped_items.append([])
    no_group_index = len(groups)

    for key, value in items:
        group_id = _get_group_id(key)
        if group_id is None:
            grouped_items[no_group_index].append((key, value))
        else:
            grouped_items[group_id].append((key, value))

    result = []
    for group in grouped_items:
        result.extend(group)
    return result


def _reference_key(reference):
    return re.sub(r"[^a-z0-9]+", " ", str(reference).lower()).strip()
