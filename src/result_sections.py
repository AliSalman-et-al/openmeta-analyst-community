import re


OPENMETA_ANALYST_REFERENCE = (
    'OpenMetaAnalyst: Wallace, Byron C., Issa J. Dahabreh, Thomas A. Trikalinos, '
    'Joseph Lau, Paul Trow, and Christopher H. Schmid. "Closing the Gap between '
    'Methodologists and End-Users: R as a Computational Back-End." Journal of '
    'Statistical Software 49 (2012): 5."'
)


REFERENCE_SECTION_TITLE = "References"


DIAGNOSTIC_SECTION_GROUPS = (
    ("sens", "spec", "bivariate"),
    ("likelihood", "nlr", "plr"),
)


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


def pop_references_section(texts):
    texts_without_references = dict(texts)
    references = texts_without_references.pop(REFERENCE_SECTION_TITLE, None)
    return texts_without_references, references


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
