import qt_text


ENTITY_LABELS = {
    "study": "Study",
    "group": "Group",
    "outcome": "Outcome",
    "follow-up": "Follow-up",
    "covariate": "Covariate",
}


def normalize_name(value):
    return qt_text.to_native_text(value).strip()


def required_message(entity):
    return "%s names cannot be empty." % ENTITY_LABELS[entity]


def duplicate_message(entity, name):
    article = "An" if entity[0].lower() in "aeiou" else "A"
    return "%s %s named %s already exists. Please pick another name." % (
        article,
        entity,
        name,
    )


def validate_required_name(entity, value):
    name = normalize_name(value)
    if name == "":
        raise ValueError(required_message(entity))
    return name


def validate_unique_name(entity, value, existing_names):
    name = validate_required_name(entity, value)
    if name in existing_names:
        raise ValueError(duplicate_message(entity, name))
    return name
