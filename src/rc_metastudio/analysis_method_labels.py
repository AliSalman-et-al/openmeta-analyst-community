import re


_KNOWN_METHOD_LABELS = {
    "binary.fixed.inv.var": "Binary Fixed-Effect Inverse Variance",
    "binary.fixed.mh": "Binary Fixed-Effect Mantel-Haenszel",
    "binary.fixed.peto": "Binary Fixed-Effect Peto",
    "binary.random": "Binary Random-Effects",
    "continuous.fixed": "Continuous Fixed-Effect Inverse Variance",
    "continuous.random": "Continuous Random-Effects",
    "diagnostic.fixed.inv.var": "Diagnostic Fixed-Effect Inverse Variance",
    "diagnostic.fixed.mh": "Diagnostic Fixed-Effect Mantel-Haenszel",
    "diagnostic.fixed.peto": "Diagnostic Fixed-Effect Peto",
    "diagnostic.random": "Diagnostic Random-Effects",
    "diagnostic.reitsma": "Reitsma bivariate model",
    "meta.regression": "Meta-Regression",
}

_RAW_METHOD_KEY_RE = re.compile(r"^[a-z]+(?:\.[a-z0-9]+)+$")
_TOKEN_LABELS = {
    "binary": "Binary",
    "continuous": "Continuous",
    "diagnostic": "Diagnostic",
    "fixed": "Fixed-Effect",
    "random": "Random-Effects",
    "inv": "Inverse",
    "var": "Variance",
    "mh": "Mantel-Haenszel",
    "peto": "Peto",
    "ml": "Maximum Likelihood",
    "meta": "Meta",
    "regression": "Regression",
}

_CANONICAL_LABEL_REPLACEMENTS = (("Mantel Haenszel", "Mantel-Haenszel"),)

_KNOWN_PARAMETER_VALUE_LABELS = {
    # Keep estimator choices compact in constrained dialogs.  The raw codes
    # remain the backend values and are standard statistical abbreviations.
    ("estimator", "REML"): "REML",
    ("estimator", "ML"): "ML",
    ("rm.method", "HE"): "Hedges",
    ("rm.method", "DL"): "DerSimonian-Laird",
    ("rm.method", "SJ"): "Sidik-Jonkman",
    ("rm.method", "ML"): "Maximum Likelihood",
    ("rm.method", "REML"): "Restricted Maximum Likelihood",
    ("rm.method", "EB"): "Empirical Bayes",
    ("rm.method", "HS"): "Hunter-Schmidt",
    ("rm.method", "HSk"): "Hunter-Schmidt with small-sample correction",
    ("rm.method", "PM"): "Paule-Mandel",
    ("rm.method", "PMM"): "Median-unbiased Paule-Mandel",
    ("inference.method", "z"): "Normal approximation",
    ("inference.method", "t"): "Student's t-distribution",
    ("inference.method", "knha"): "Knapp-Hartung",
    ("inference.method", "adhoc"): "Modified Knapp-Hartung",
    ("to", "only0"): "Only zero-event studies",
    ("to", "all"): "All studies",
    ("to", "if0all"): "All studies if any study has zero events",
    ("to", "none"): "No studies",
    ("correction.policy", "Studies with any zero cell"): "Studies with any zero cell",
    ("correction.policy", "All studies if any zero exists"): "All studies if any zero exists",
    ("correction.policy", "None"): "None",
}

_KNOWN_PARAMETER_LABELS = {
    "rm.method": "Random-Effects Method",
    "estimator": "Estimator",
    "inference.method": "Inference Method",
    "to": "Correction Factor Target",
    "correction.policy": "Correction Policy",
    "conf.level": "Confidence Level",
    "digits": "Decimal Places",
    "adjust": "Correction Factor",
}

_DIAGNOSTIC_METRIC_GROUP_LABELS = {
    "sens_spec": "Sensitivity and Specificity",
    "lr_dor": "Likelihood Ratios and Diagnostic Odds Ratio",
}


def method_display_label(method_key_or_label):
    text = str(method_key_or_label)
    if text in _KNOWN_METHOD_LABELS:
        return _KNOWN_METHOD_LABELS[text]
    if not _RAW_METHOD_KEY_RE.match(text):
        return _canonicalize_label(text)
    return _canonicalize_label(
        " ".join(_TOKEN_LABELS.get(token, token.title()) for token in text.split("."))
    )


def _canonicalize_label(label):
    text = str(label)
    for old, new in _CANONICAL_LABEL_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def normalize_available_method_labels(methods_by_label):
    normalized = {}
    for label, method_key in methods_by_label.items():
        normalized[method_display_label(label)] = method_key
    return normalized


def parameter_value_display_label(param_name, value, param_metadata=None):
    text = str(value)
    if param_metadata is not None:
        value_names = param_metadata.get("%s.names" % param_name)
        if value_names is not None and text in value_names:
            return str(value_names[text])
    return _KNOWN_PARAMETER_VALUE_LABELS.get((str(param_name), text), text)


def parameter_display_label(param_name, param_metadata=None):
    text = str(param_name)
    if param_metadata is not None:
        pretty_name = param_metadata.get("pretty.name")
        if pretty_name:
            pretty_name = str(pretty_name)
            if pretty_name != text:
                return _canonicalize_label(pretty_name)
    if text in _KNOWN_PARAMETER_LABELS:
        return _KNOWN_PARAMETER_LABELS[text]
    return _label_from_key(text)


def parameter_description(param_name, param_metadata=None):
    if param_metadata is not None:
        description = param_metadata.get("description")
        if description and str(description) != "None provided":
            return str(description)
    return "No description provided."


def diagnostic_metric_group_display_label(group_key):
    return _DIAGNOSTIC_METRIC_GROUP_LABELS.get(str(group_key), str(group_key))


def _label_from_key(key):
    key = str(key)
    if "." in key:
        return " ".join(_label_from_token(token) for token in key.split("."))
    if "_" in key:
        return " ".join(_label_from_token(token) for token in key.split("_"))
    return _label_from_token(key)


def _label_from_token(token):
    if token.lower() in _TOKEN_LABELS:
        return _TOKEN_LABELS[token.lower()]
    return token[:1].upper() + token[1:]
