import re
from collections.abc import Mapping
from collections import namedtuple


REFERENCE_SECTION_TITLE = "References"
WEIGHTS_SECTION_TITLE = "Weights"

DisplaySection = namedtuple("DisplaySection", ["kind", "key", "display_title", "value"])


DIAGNOSTIC_SECTION_GROUPS = (
    ("sens", "spec", "reitsma"),
    ("likelihood", "nlr", "plr"),
)

SECTION_TITLE_REPLACEMENTS = {
    "Leave-one-out Forest plot": "Leave-One-Out Forest Plot",
    "SROC": "Summary ROC Plot",
    "Warning": "Interpretation",
    "Data and eligibility": "Analysis Summary",
    "Tests": "Small-Study Effects Tests",
    "Pooled comparison": "Pooled Estimates",
    "Trim-and-fill left": "Trim-and-Fill: Left Estimate",
    "Trim-and-fill right": "Trim-and-Fill: Right Estimate",
    "Trim-and-fill model": "Trim-and-Fill Model",
    "Extrapolation": "Infinite-Precision Estimate",
    "Failures": "Procedure Warnings",
    "Method details": "Method Details",
    "Methods not applicable": "Methods Not Applicable",
}

METRIC_TITLE_REPLACEMENTS = (
    ("NLR", "Negative Likelihood Ratio"),
    ("PLR", "Positive Likelihood Ratio"),
    ("DOR", "Diagnostic Odds Ratio"),
    ("Sens", "Sensitivity"),
    ("Spec", "Specificity"),
)


def format_references(references):
    if references is None:
        return ""
    if isinstance(references, Mapping):
        references = references.values()
    elif isinstance(references, str):
        references = [references]
    else:
        try:
            references = list(references)
        except TypeError:
            references = [references]
    references = [_reference_text(reference) for reference in references]
    ordered_references = dedupe_references_preserving_order(references)
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


def _reference_text(reference):
    if reference is None:
        return ""
    if not isinstance(reference, str):
        try:
            values = list(reference)
        except TypeError:
            values = None
        if values is not None:
            if not values:
                return ""
            if len(values) == 1:
                return _reference_text(values[0])
            return "; ".join(_reference_text(value) for value in values)
    text = str(reference).replace("\r\n", "\n").strip()
    text = re.sub(r"^\[\d+\]\s+", "", text)
    return text.strip('"')


def order_text_sections(items, include_references=False):
    filtered = [
        (title, value)
        for title, value in items
        if include_references or title != REFERENCE_SECTION_TITLE
    ]
    # Most workflows deliberately emit a meaningful narrative order.  Only
    # the legacy multi-metric diagnostic result has a narrow ordering contract;
    # arbitrary/new result sections must remain in producer order.
    if _looks_like_diagnostic_sections(filtered):
        return _group_items(filtered, *DIAGNOSTIC_SECTION_GROUPS)
    return filtered


def order_image_sections(items, explicit_order=None):
    item_dict = dict(items)
    if explicit_order is not None:
        return [
            (title, item_dict[title]) for title in explicit_order if title in item_dict
        ]
    items = list(items)
    if _looks_like_diagnostic_sections(items):
        return _group_items(items, *DIAGNOSTIC_SECTION_GROUPS)
    return items


def order_display_sections(texts, images, explicit_image_order=None):
    context = _section_context(texts, images)
    text_sections = [
        DisplaySection("text", title, section_display_title(title, context, "text"), value)
        for title, value in order_text_sections(texts)
    ]
    image_sections = [
        DisplaySection("image", title, section_display_title(title, context, "image"), value)
        for title, value in order_image_sections(
            images, explicit_order=explicit_image_order
        )
    ]

    if _is_small_study_effects_result(context):
        return _order_small_study_effects_sections(text_sections, image_sections)
    if _is_reitsma_meta_regression_result(context):
        return _order_reitsma_meta_regression_sections(text_sections, image_sections)
    if _is_reitsma_result(context):
        return _order_reitsma_sections(text_sections, image_sections)
    if _is_standard_meta_analysis_result(context):
        return _order_standard_meta_analysis_sections(text_sections, image_sections)
    return text_sections + image_sections


def section_display_title(title, context=None, kind=None):
    if context is None:
        context = {"text_titles": [], "image_titles": []}

    if title == "Summary":
        if "Regression Plot" in context["image_titles"]:
            return "Meta-Regression Summary"
        return "Meta-Analysis Summary"
    if kind == "image" and title in ("Trim-and-fill left", "Trim-and-fill right"):
        side = "Left" if title.endswith("left") else "Right"
        return "Trim-and-Fill: %s Plot" % side
    if title in SECTION_TITLE_REPLACEMENTS:
        return SECTION_TITLE_REPLACEMENTS[title]
    return _normalize_metric_title(title)


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


def _is_small_study_effects_result(context):
    return "Warning" in context["text_titles"] and (
        "Data and eligibility" in context["text_titles"]
        or any("Funnel Plot" in title for title in context["image_titles"])
    )


def _is_reitsma_result(context):
    titles = set(context["text_titles"])
    # AUC is an optional derived quantity: mada can fail to provide it for a
    # valid fit (for example when the SROC geometry is undefined).  The
    # result still has the Reitsma contract when its clinical headline and at
    # least one of the model's supporting outputs are present.
    return "Clinical interpretation" in titles and bool(
        titles
        & {
            "Summary operating point",
            "Sampling-based summary ratios",
            "Marginal prediction",
            "Between-study heterogeneity",
            "Diagnostic I-squared",
            "Model information",
        }
    )


def _is_reitsma_meta_regression_result(context):
    titles = set(context["text_titles"])
    return "Overall ML likelihood-ratio test" in titles and (
        "Sensitivity coefficients" in titles or "Specificity coefficients" in titles
    )


def _take_sections(sections, keys):
    by_key = {section.key: section for section in sections}
    selected = []
    for key in keys:
        section = by_key.pop(key, None)
        if section is not None:
            selected.append(section)
    return selected, by_key


def _order_reitsma_sections(text_sections, image_sections):
    result = []
    primary, remaining = _take_sections(
        text_sections,
        ("Clinical interpretation", "Summary operating point", "SROC AUC"),
    )
    result.extend(primary)
    sroc, remaining_images = _take_sections(image_sections, ("SROC", "Summary ROC"))
    result.extend(sroc)
    support, remaining = _take_sections(
        list(remaining.values()),
        (
            "Sampling-based summary ratios",
            "Marginal prediction",
            "Between-study heterogeneity",
            "Diagnostic I-squared",
        ),
    )
    result.extend(support)
    model, remaining = _take_sections(
        list(remaining.values()), ("Model information",)
    )
    result.extend(remaining.values())
    result.extend(model)
    result.extend(remaining_images.values())
    return result


def _order_reitsma_meta_regression_sections(text_sections, image_sections):
    result = []
    primary, remaining = _take_sections(text_sections, ("Clinical interpretation",))
    result.extend(primary)
    tests, remaining = _take_sections(
        list(remaining.values()),
        ("Overall ML likelihood-ratio test", "Moderator block tests"),
    )
    result.extend(tests)
    for table_key, plot_prefix in (
        ("Sensitivity coefficients", "Sensitivity Moderator Coefficients"),
        ("Specificity coefficients", "Specificity Moderator Coefficients"),
    ):
        table, remaining = _take_sections(list(remaining.values()), (table_key,))
        result.extend(table)
        plots = [
            section
            for section in image_sections
            if section.key == plot_prefix
        ]
        result.extend(plots)
        image_sections = [section for section in image_sections if section not in plots]
    details, remaining = _take_sections(
        list(remaining.values()),
        ("Residual diagnostic I-squared", "Moderator coding", "Model information"),
    )
    result.extend(details)
    result.extend(remaining.values())
    result.extend(image_sections)
    return result


def _order_small_study_effects_sections(text_sections, image_sections):
    ordered_keys = (
        "Warning",
        "Data and eligibility",
        "Tests",
        "Pooled comparison",
        "Trim-and-fill",
        "Trim-and-fill left",
        "Trim-and-fill right",
        "Trim-and-fill model",
        "Extrapolation",
        REFERENCE_SECTION_TITLE,
        "Failures",
    )
    by_text = {section.key: section for section in text_sections}
    result = []
    for key in ordered_keys[:2]:
        section = by_text.pop(key, None)
        if section is not None:
            result.append(section)
    result.extend(image_sections)
    for key in ordered_keys[2:]:
        section = by_text.pop(key, None)
        if section is not None:
            result.append(section)
    result.extend(by_text.values())
    return result


def _order_standard_meta_analysis_sections(text_sections, image_sections):
    summary = _matching_sections(
        text_sections, lambda section: section.key == "Summary"
    )
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


def _matching_sections(sections, predicate):
    return [section for section in sections if predicate(section)]


def _is_primary_plot_title(title):
    return title in ("Forest Plot", "Regression Plot", "ROC Plot")


def _normalize_metric_title(title):
    display_title = str(title).replace("Forest plot", "Forest Plot")
    display_title = _normalize_identifier_label(display_title)
    for abbreviation, label in METRIC_TITLE_REPLACEMENTS:
        display_title = re.sub(
            r"\b%s\b" % re.escape(abbreviation),
            label,
            display_title,
        )
    return display_title


def _looks_like_diagnostic_sections(items):
    titles = [str(title).lower() for title, _value in items]
    has_accuracy = any(
        title.startswith(("sens", "spec", "reitsma")) for title in titles
    )
    has_ratios = any(
        title.startswith(("nlr", "plr", "negative likelihood", "positive likelihood", "likelihood"))
        for title in titles
    )
    return has_accuracy and has_ratios


def _normalize_identifier_label(value):
    """Make R identifiers readable while retaining statistical notation."""
    text = str(value).replace("I\ufffd", "I²").replace("\ufffd", "-")
    replacements = {
        "posLR": "Positive Likelihood Ratio",
        "negLR": "Negative Likelihood Ratio",
        "invnegLR": "Inverse Negative Likelihood Ratio",
        "pos.lr": "Positive Likelihood Ratio",
        "neg.lr": "Negative Likelihood Ratio",
        "inv.neg.lr": "Inverse Negative Likelihood Ratio",
        # Keep this ASCII-safe because some embedded-R locales decode an
        # en-dash in dimnames as U+FFFD before it reaches the Qt document.
        "Zhou.Dendukuri": "Zhou-Dendukuri",
        "Holling.Unadjusted": "Holling (unadjusted)",
        "Holling.Adjusted": "Holling (adjusted)",
        "I.squared": "I²",
        "I_squared": "I²",
        "I2": "I²",
        "tau.squared": "τ²",
        "tau_squared": "τ²",
        "tau2": "τ²",
    }
    for raw_label, display_label in sorted(
        replacements.items(), key=lambda item: len(item[0]), reverse=True
    ):
        text = text.replace(raw_label, display_label)
    if text in replacements:
        return replacements[text]
    text = re.sub(r"\bPr\s*\(>\|[^)]+\)", "p-value", text)
    text = re.sub(r"\b(?:p[._-]?value|pval)\b", "p-value", text, flags=re.I)
    text = re.sub(r"\b(?:z[._-]?value|zval)\b", "z-value", text, flags=re.I)
    text = re.sub(r"\b(?:I[._-]?squared|I2)\b", "I²", text, flags=re.I)
    text = re.sub(r"\b(?:tau[._-]?squared|tau2)\b", "τ²", text, flags=re.I)
    text = re.sub(r"(?<![A-Za-z])([A-Z]{2,})(?=[A-Z][a-z]|\b)", r"\1 ", text)
    text = text.replace("_", " ").replace(".", " ")
    text = re.sub(r"\s+", " ", text).strip()
    words = []
    for word in text.split(" "):
        lower = word.lower()
        if lower in {"nlr", "plr", "dor"}:
            words.append({"nlr": "Negative Likelihood Ratio", "plr": "Positive Likelihood Ratio", "dor": "Diagnostic Odds Ratio"}[lower])
        elif lower == "sens":
            words.append("Sensitivity")
        elif lower == "spec":
            words.append("Specificity")
        else:
            words.append(word)
    return " ".join(words)


def normalize_identifier_label(value):
    """Public label helper for result values crossing the R boundary."""
    return _normalize_identifier_label(value)


def _group_items(items, *groups):
    def _get_group_id(key):
        normalized_key = key.strip().lower()
        for group_id, group in enumerate(groups):
            for group_member in group:
                if normalized_key.startswith(group_member.lower()):
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
