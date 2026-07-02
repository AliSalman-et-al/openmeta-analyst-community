def _is_effect_triplet(value):
    if isinstance(value, (str, bytes)):
        return False
    try:
        return len(value) == 3
    except TypeError:
        return False


def effect_triplet(effect_entry, scale_name="calc_scale", metric=None):
    """Return an ``(estimate, lower, upper)`` tuple from a study-effect result.

    Study-effect helpers normally return each scale as a three-value vector.
    Some backend paths can return a point-estimate scalar instead. Treat that
    as an estimate with unavailable CI bounds so callers can keep edited rows
    coherent instead of crashing during recomputation.
    """
    try:
        scale_value = effect_entry[scale_name]
    except (KeyError, TypeError):
        label = " for %s" % metric if metric is not None else ""
        raise ValueError("Missing %s study effect%s" % (scale_name, label))

    if _is_effect_triplet(scale_value):
        return tuple(scale_value)

    if isinstance(scale_value, (list, tuple)):
        if len(scale_value) == 1:
            return scale_value[0], None, None
        label = " for %s" % metric if metric is not None else ""
        raise ValueError(
            "Expected %s study effect%s to contain 1 or 3 values; got %d"
            % (scale_name, label, len(scale_value))
        )

    return scale_value, None, None


def normalize_effect_result(effect_result, metric=None):
    for scale_name in ("calc_scale", "display_scale"):
        if scale_name in effect_result:
            effect_result[scale_name] = effect_triplet(
                effect_result,
                scale_name,
                metric=metric,
            )
    return effect_result


def normalize_diagnostic_effects(effects):
    for metric, effect_entry in list(effects.items()):
        if not isinstance(effect_entry, dict):
            effects[metric] = {"calc_scale": effect_entry}
            effect_entry = effects[metric]

        normalize_effect_result(effect_entry, metric=metric)
    return effects
