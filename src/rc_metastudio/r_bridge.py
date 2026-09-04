# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""R bridge for RCMetaR calls through rpy2."""

import locale
import math
import os
import re
import sys
from collections.abc import Mapping
from typing import Callable, Literal, overload

from rc_metastudio import r_runtime
from rc_metastudio.analysis_method_labels import (
    method_display_label,
    normalize_available_method_labels,
)
from rc_metastudio import result_sections
from rc_metastudio.analysis_errors import DiagnosticExecutionError
from rc_metastudio.analysis_results import AnalysisResult, parse_analysis_result
from rc_metastudio.study_effect_shapes import (
    effect_triplet as effect_triplet,
    normalize_diagnostic_effects,
    normalize_effect_result,
)
from rc_metastudio.r_call_serialization import require_r_transaction, serialized_r_call
from rc_metastudio.meta_globals import (
    BINARY,
    CONTINUOUS,
    EMPTY_VALS,
    INVALID_CONFIDENCE_LEVEL_MESSAGE,
    ONE_ARM_METRICS,
    PERCENTAGE_DISPLAY_DIGITS,
    TWO_ARM_METRICS,
    TYPE_TO_STR_DICT,
    normalize_confidence_level_params,
    tabulate,
    validate_confidence_level,
)

try:
    import rpy2.robjects as ro
except Exception as error:
    raise RuntimeError(
        "Cannot initialize rpy2. Check the bundled R runtime configuration."
    ) from error
import rpy2.robjects
import rpy2.rinterface
from rpy2.rinterface_lib.embedded import RRuntimeError


try:
    import rpy2.rinterface_lib.conversion as _rpy2_conversion

    _rpy2_rchar_to_str = _rpy2_conversion._rchar_to_str

    def _rchar_to_str_as_utf8(rchar, encoding: str) -> str:
        try:
            return str(_rpy2_conversion._utf8_rchar_to_str(rchar))
        except UnicodeDecodeError:
            return str(_rpy2_rchar_to_str(rchar, encoding))

    # This private rpy2 hook is intentionally replaced at the integration
    # boundary; its runtime signature is not expressible in rpy2's stubs.
    setattr(_rpy2_conversion, "_rchar_to_str", _rchar_to_str_as_utf8)
except (ImportError, AttributeError):
    pass

# R console callbacks on Windows are emitted in the native ANSI code page.
# rpy2 otherwise initializes this private decoder from Python's UTF-8 default,
# which turns ordinary non-ASCII diagnostics into callback UnicodeDecodeError
# messages. Keep non-Windows behavior unchanged.
if sys.platform == "win32":
    try:
        from rpy2.rinterface_lib import callbacks as _rpy2_callbacks

        setattr(
            _rpy2_callbacks,
            "_CCHAR_ENCODING",
            locale.getpreferredencoding(False),
        )
    except (ImportError, AttributeError):
        pass


_RFunction = Callable[..., object]


def _r_function(function_name: str) -> _RFunction:
    """Return a callable R function after checking rpy2's dynamic lookup."""
    function = ro.r[function_name]
    if not callable(function):
        raise TypeError("R object %r is not callable" % function_name)
    return function


def _r_eval(expression: str) -> object:
    """Evaluate an R expression after checking rpy2's dynamic evaluator."""
    evaluator = ro.r
    if not callable(evaluator):
        raise TypeError("rpy2's R evaluator is not callable")
    return evaluator(expression)


def _call_dynamic(function: object, *args: object, **kwargs: object) -> object:
    """Call a value returned by R after checking that it is callable."""
    caller = getattr(function, "__call__", None)
    if not callable(caller):
        raise TypeError("R value is not callable")
    return caller(*args, **kwargs)


def _first_dynamic(value: object) -> object:
    """Read the first element of an R vector after checking its shape."""
    getitem = getattr(value, "__getitem__", None)
    if not callable(getitem):
        raise TypeError("R value is not indexable")
    return getitem(0)


def _r_is_null(r_object):
    """True if an rpy2 object is R's NULL.

    rpy2 >= 3.x represents NULL as a ``NULLType`` singleton whose ``str()`` is
    an object repr (e.g. ``<rpy2...NULLType object at 0x...>``), not the literal
    ``"NULL"`` emitted by older rpy2 builds. Code that detected NULL via
    ``str(x) == "NULL"`` therefore silently misfires (e.g. treating a list with
    NULL names as if it had names). Prefer identity/type checks and keep the
    string fallback for older rpy2 compatibility.
    """
    try:
        if r_object is rpy2.rinterface.NULL:
            return True
        if isinstance(r_object, type(rpy2.rinterface.NULL)):
            return True
    except Exception:
        pass
    return str(r_object) == "NULL"


@serialized_r_call
def execute_r_string(r_str):
    require_r_transaction()
    try:
        return _r_eval(r_str)
    except Exception:
        # An R error can leave the process in a package-specific directory.
        reset_r_working_directory()
        raise


@serialized_r_call
def execute_r_function(function_name, *args, **kwargs):
    require_r_transaction()
    return _r_function(function_name)(*args, **kwargs)


class RLibraryLoader:
    def load_meta(self):
        return self._load_r_lib("meta", expected_version="8.5-0")

    def load_metafor(self):
        return self._load_r_lib("metafor")

    def load_rcmetar(self):
        return self._load_r_lib("RCMetaR")

    def load_grid(self):
        return self._load_r_lib("grid")

    def _load_r_lib(self, name, expected_version=None):
        try:
            execute_r_function("library", name)
            if expected_version is not None:
                version = get_r_package_version(name)
                if version != expected_version:
                    raise RuntimeError(
                        "%s package version %s is required; found %s"
                        % (name, expected_version, version)
                    )
            msg = "%s package successfully loaded" % name
            return (True, msg)
        except Exception as exc:
            raise RuntimeError(
                "The %s R package is not installed.\nPlease \
install this package and then restart RC MetaStudio."
                % name
            ) from exc


@serialized_r_call
def get_r_library_paths():
    """Return the library paths visible to R."""
    return list(execute_r_string(".libPaths()"))


@serialized_r_call
def get_r_version_string():
    return str(execute_r_string("R.version.string")[0])


@serialized_r_call
def get_r_package_version(package_name):
    if package_name == "meta":
        return str(
            execute_r_string("as.character(packageDescription('meta')$Version)")[0]
        )
    version = execute_r_function("packageVersion", package_name)
    return str(execute_r_function("as.character", version)[0])


@serialized_r_call
def reset_r_working_directory():
    """Reset R's working directory to the application data directory."""
    # Fix paths issue in windows
    from rc_metastudio import settings

    base_path = settings.get_base_path()
    base_path = settings.to_posix_path(base_path)

    execute_r_function("setwd", base_path)


@serialized_r_call
def impute_diagnostic_data(diagnostic_data):
    diagnostic_data = normalize_confidence_level_params(diagnostic_data)

    # rpy2 cannot convert None values in this parameter mapping.
    for param, val in list(diagnostic_data.items()):
        if val is None:
            diagnostic_data.pop(param)

    dataf = _r_function("data.frame")(**diagnostic_data)
    two_by_two = execute_r_function("rcmetar.impute.diagnostic", dataf)

    imputed_2x2 = named_r_list_to_dict(two_by_two)

    return imputed_2x2


@serialized_r_call
def impute_binary_data(binary_data):
    binary_data = normalize_confidence_level_params(binary_data)
    remove_entries_with_value(None, binary_data)

    dataf = _r_function("data.frame")(**binary_data)
    two_by_two = execute_r_function("rcmetar.impute.binary", dataf)

    res_as_dict = r_object_to_python(two_by_two)

    return res_as_dict


@serialized_r_call
def back_calculate_continuous_data(
    group1_data, group2_data, effect_data, confidence_level
):
    confidence_level = validate_confidence_level(confidence_level)
    remove_entries_with_value(None, group1_data)
    remove_entries_with_value(None, group2_data)
    remove_entries_with_value(None, effect_data)

    dataf_grp1 = _r_function("data.frame")(**group1_data)
    dataf_grp2 = _r_function("data.frame")(**group2_data)
    dataf_effect = _r_function("data.frame")(**effect_data)

    r_res = execute_r_function(
        "rcmetar.back.calculate.continuous",
        dataf_grp1,
        dataf_grp2,
        dataf_effect,
        confidence_level,
    )

    res_as_dict = r_object_to_python(r_res)

    return res_as_dict


def remove_entries_with_value(value_to_remove, values):
    """Remove dictionary entries that equal ``value_to_remove``."""
    for parameter, value in list(values.items()):
        if value == value_to_remove:
            values.pop(parameter)


def named_r_list_to_dict(named_r_list):
    keys = named_r_list.names
    if _r_is_null(keys):
        raise ValueError("R list has no names")
    return dict(zip(keys, r_iterable_to_list(named_r_list)))


def r_object_to_python(data):
    if _r_is_null(data):
        return None

    # Matrix/array ``names`` in rpy2 is an alias for ``dimnames``.  Looking at
    # names first therefore turns a matrix into a mapping whose keys are
    # StrVector reprs (``[1] \"row 1\"``).  Dimensions are the stronger shape
    # signal and must be handled before ordinary named vectors/lists.
    if _r_dims(data):
        return [_r_na_to_none(value) for value in list(data)]
    if _has_r_names(data):
        return {
            key: r_object_to_python(value)
            for key, value in named_r_list_to_dict(data).items()
        }
    if _is_r_iterable(data):
        return [r_object_to_python(value) for value in r_iterable_to_list(data)]
    return _r_na_to_none(data)


def r_iterable_to_list(r_iterable):
    return [
        _r_singleton_to_scalar(value)
        if _is_r_iterable(value) and len(value) == 1
        else value
        for value in r_iterable
    ]


def _r_singleton_to_scalar(singleton):
    if len(singleton) != 1:
        raise ValueError("expected an R sequence with one element")
    if isinstance(singleton, rpy2.robjects.vectors.FactorVector):
        return execute_r_function("as.character", singleton)[0]
    return _r_na_to_none(singleton[0])


def _r_na_to_none(value):
    return None if str(value) == "NA" else value


def _is_r_iterable(value, exclude_strings=True):
    if exclude_strings and isinstance(value, str):
        return False
    try:
        iter(value)
    except TypeError:
        return False
    return True


def _has_r_names(value):
    if _r_is_null(value):
        return False
    # rpy2 exposes matrix/array dimnames through ``names`` as well.  Those
    # are labels for axes, not key/value names for a mapping.
    if _r_dims(value):
        return False
    try:
        names = value.names
    except Exception:
        return False
    return not _r_is_null(names)


@serialized_r_call
def impute_continuous_data(continuous_data, alpha):
    if not continuous_data:
        return {"succeeded": False}

    dataf = _r_function("data.frame")(**continuous_data)
    c_data = execute_r_function("rcmetar.impute.continuous.study", dataf, alpha=alpha)

    return r_object_to_python(c_data)


@serialized_r_call
def impute_pre_post_continuous_data(continuous_data, correlation, alpha):
    if len(list(continuous_data.items())) == 0:
        return {"succeeded": False}

    dataf = _r_function("data.frame")(**continuous_data)
    c_data = execute_r_function(
        "rcmetar.impute.continuous.prepost",
        dataf,
        correlation=correlation,
        alpha=alpha,
    )
    pythonized_data = r_object_to_python(c_data)

    return pythonized_data


@serialized_r_call
def get_confidence_multiplier_from_r(confidence_level):
    confidence_level = validate_confidence_level(confidence_level)
    confidence_multiplier = execute_r_function(
        "rcmetar.get.mult.from.conf.level", confidence_level
    )
    multiplier = float(confidence_multiplier[0])
    if not math.isfinite(multiplier):
        raise ValueError(INVALID_CONFIDENCE_LEVEL_MESSAGE)
    return multiplier


@serialized_r_call
def set_confidence_level(confidence_level):
    confidence_level = validate_confidence_level(confidence_level)
    new_level = execute_r_function(
        "rcmetar.set.global.conf.level", float(confidence_level)
    )
    return float(new_level[0])


def _r_null_if_none(value):
    return rpy2.rinterface.NULL if value is None else value


@serialized_r_call
def get_params(method_name):
    param_list = execute_r_function("rcmetar.method.parameters", str(method_name))
    param_d = {}
    for name, r_obj in zip(param_list.names, param_list):
        param_d[name] = r_obj

    order_vars = None
    if "var_order" in param_d:
        order_vars = list(param_d["var_order"])

    pretty_names_and_descriptions = r_object_to_python(
        param_d.get("pretty.names", _r_function("list")())
    )

    return (
        r_object_to_python(param_d["parameters"]),
        r_object_to_python(param_d["defaults"]),
        order_vars,
        pretty_names_and_descriptions,
    )


@serialized_r_call
def get_available_methods(
    for_data_type=None, data_obj_name=None, metric=None, workflow="standard"
):
    """Returns a list of methods available in RCMetaR for the particular data_type
    (if one is given).
    """
    data_arg = None if data_obj_name is None else ro.globalenv[str(data_obj_name)]
    methods = execute_r_function(
        "rcmetar.available.methods",
        **{
            "data.type": _r_null_if_none(
                None if for_data_type is None else str(for_data_type)
            ),
            "om.data": _r_null_if_none(data_arg),
            "metric": _r_null_if_none(None if metric is None else str(metric)),
            "workflow": str(workflow),
        },
    )
    return normalize_available_method_labels(r_object_to_python(methods))


@serialized_r_call
def get_method_description(method_name):
    return execute_r_function("rcmetar.method.description", str(method_name))[0]


@serialized_r_call
def get_analysis_plot_capabilities(data_type, method_name, workflow="standard"):
    capabilities = execute_r_function(
        "rcmetar.analysis.plot.capabilities",
        str(data_type),
        str(method_name),
        workflow=str(_normalize_rcmetar_workflow(workflow)),
    )
    return r_object_to_python(capabilities)


@serialized_r_call
def dataset_to_simple_continuous_r_object(
    table_model, var_name="tmp_obj", covs_to_include=None, studies=None
):
    if studies is None:
        # grab all studies. note: the list is pulled out in reverse order from the
        studies = table_model.get_studies()
    # the study_ids preserve the ordering
    study_ids = [study.id for study in studies]

    estimates, standard_errors = table_model.get_current_estimates_and_standard_errors(
        only_these_studies=study_ids
    )

    data_kwargs = _analysis_data_kwargs(
        studies,
        study_ids,
        table_model.dataset,
        covs_to_include,
        y=estimates,
        standard_errors=standard_errors,
    )

    # One-arm continuous models use only the estimate and standard error.
    if (
        table_model.current_effect not in ONE_ARM_METRICS
    ) and table_model.included_studies_have_raw_data():
        raw_data = table_model.get_current_raw_data(only_these_studies=study_ids)
        data_kwargs.update(
            {
                "N1": _r_numeric_vector(_get_col(raw_data, 0)),
                "mean1": _r_numeric_vector(_get_col(raw_data, 1)),
                "sd1": _r_numeric_vector(_get_col(raw_data, 2)),
                "N2": _r_numeric_vector(_get_col(raw_data, 3)),
                "mean2": _r_numeric_vector(_get_col(raw_data, 4)),
                "sd2": _r_numeric_vector(_get_col(raw_data, 5)),
            }
        )

    r_obj = execute_r_function("rcmetar.create.continuous.data", **data_kwargs)
    ro.globalenv[var_name] = r_obj
    return r_obj


@serialized_r_call
def dataset_to_simple_binary_r_object(
    table_model,
    var_name="tmp_obj",
    include_raw_data=True,
    covs_to_include=None,
    studies=None,
):
    """Convert the table's selected outcome and follow-up to an RCMetaR object."""
    if studies is None:
        # grab the study names. note: the list is pulled out in reverse order from the
        studies = table_model.get_studies(only_if_included=True)

    study_ids = [study.id for study in studies]

    estimates, standard_errors = table_model.get_current_estimates_and_standard_errors(
        only_if_included=True, only_these_studies=study_ids
    )

    data_kwargs = _analysis_data_kwargs(
        studies,
        study_ids,
        table_model.dataset,
        covs_to_include,
        y=estimates,
        standard_errors=standard_errors,
    )

    # first try and construct an object with raw data
    if include_raw_data and table_model.included_studies_have_raw_data():
        # now figure out the raw data
        raw_data = table_model.get_current_raw_data(only_these_studies=study_ids)

        g1_events = _get_col(raw_data, 0)

        g1_totals = _get_col(raw_data, 1)

        group1_nonevents = [
            total - events for total, events in zip(g1_totals, g1_events)
        ]

        # now, for group 2; we only set up the string
        # for group two if we have a two-arm metric
        group2_events, group2_nonevents = [0], [0]
        if table_model.current_effect in TWO_ARM_METRICS:
            g2_events = _get_col(raw_data, 2)

            g2_totals = _get_col(raw_data, 3)
            group2_nonevents = [
                total - events for total, events in zip(g2_totals, g2_events)
            ]
            group2_events = g2_events

        data_kwargs.update(
            {
                "g1O1": _r_numeric_vector(g1_events),
                "g1O2": _r_numeric_vector(group1_nonevents),
                "g2O1": _r_numeric_vector(group2_events),
                "g2O2": _r_numeric_vector(group2_nonevents),
            }
        )

    r_obj = execute_r_function("rcmetar.create.binary.data", **data_kwargs)
    ro.globalenv[var_name] = r_obj
    return r_obj


def _data_blank_or_none(*args):
    """Returns True if there is a blank or none value in args,
    Returns False otherwise
    """
    if args is None:
        return True

    for x in args:
        if x in EMPTY_VALS:
            return True
    return False


@serialized_r_call
def dataset_to_simple_diagnostic_r_object(
    table_model,
    var_name="tmp_obj",
    metric="Sens",
    covs_to_include=None,
    effects_on_disp_scale=False,
    studies=None,
):
    """This converts a DatasetTableModel to an RCMetaR OMData object. We use type DatasetTableModel
    rather than a DataSet model directly to access the current variables. Furthermore, this allows
    us to check which studies (if any) were excluded by the user.


    """
    # grab the study names. note: the list is pulled out in reverse order from the
    if studies is None:
        studies = table_model.get_studies(only_if_included=True)
    study_ids = [study.id for study in studies]

    estimates, standard_errors = table_model.get_current_estimates_and_standard_errors(
        only_if_included=True, only_these_studies=study_ids, effect=metric
    )

    data_kwargs = _analysis_data_kwargs(
        studies,
        study_ids,
        table_model.dataset,
        covs_to_include,
        y=estimates,
        standard_errors=standard_errors,
    )

    # first try and construct an object with raw data
    raw_data = table_model.get_current_raw_data(only_these_studies=study_ids)
    has_raw_data = len(raw_data) == len(studies) and all(
        not any(value in EMPTY_VALS for value in row) for row in raw_data
    )
    has_point_estimates = (
        len(estimates) == len(studies)
        and len(standard_errors) == len(studies)
        and not any(value in EMPTY_VALS for value in estimates)
        and not any(value in EMPTY_VALS for value in standard_errors)
    )

    if has_raw_data:
        data_kwargs.update(
            {
                "TP": _r_numeric_vector(_get_col(raw_data, 0)),
                "FN": _r_numeric_vector(_get_col(raw_data, 1)),
                "FP": _r_numeric_vector(_get_col(raw_data, 2)),
                "TN": _r_numeric_vector(_get_col(raw_data, 3)),
            }
        )

    elif not has_point_estimates:
        raise ValueError(
            "Diagnostic analysis requires either complete TP/FN/FP/TN counts "
            "or complete entered effect estimates and confidence intervals "
            "for %s." % metric
        )

    try:
        r_obj = execute_r_function("rcmetar.create.diagnostic.data", **data_kwargs)
    except RRuntimeError as error:
        raise DiagnosticExecutionError(str(error)) from error
    ro.globalenv[var_name] = r_obj
    return r_obj


def _analysis_data_kwargs(
    studies, study_ids, dataset, covs_to_include, y, standard_errors
):
    return {
        "y": _r_numeric_vector(y),
        "SE": _r_numeric_vector(standard_errors),
        "study.names": _r_character_vector([study.name for study in studies]),
        "years": _r_year_vector([study.year for study in studies]),
        "covariates": _r_covariate_list(dataset, study_ids, covs_to_include),
    }


def _r_character_vector(values):
    converted = [
        ro.NA_Character if _data_blank_or_none(value) else str(value)
        for value in values
    ]
    return ro.StrVector(converted)


def _r_year_vector(values):
    converted = [
        ro.NA_Integer if _data_blank_or_none(value) else int(value) for value in values
    ]
    return ro.IntVector(converted)


def _r_numeric_vector(values):
    converted = [
        ro.NA_Real if _data_blank_or_none(value) else float(value) for value in values
    ]
    return ro.FloatVector(converted)


def _r_covariate_list(dataset, study_ids, covariates=None):
    if covariates is None:
        covariates = dataset.covariates
    covariates = [_r_covariate_values(cov, study_ids, dataset) for cov in covariates]
    return execute_r_function("list", *covariates)


def _r_covariate_values(cov, study_ids, dataset):
    values = _cov_values_for_studies(cov, study_ids, dataset)
    covariate_type = TYPE_TO_STR_DICT[cov.data_type]
    if cov.data_type == CONTINUOUS:
        covariate_values = _r_numeric_vector(values)
    else:
        covariate_values = _r_character_vector(values)
    return execute_r_function(
        "rcmetar.create.covariate.values",
        **{
            "cov.name": str(cov.name),
            "cov.vals": covariate_values,
            "cov.type": covariate_type,
            "ref.var": _cov_ref_value(values),
        },
    )


def _cov_values_for_studies(cov, study_ids, dataset):
    covariate_values_by_study = dataset.get_covariate_values(
        cov.name, ids_for_keys=True
    )
    return [covariate_values_by_study.get(study_id) for study_id in study_ids]


def _cov_ref_value(values):
    for value in values:
        if not _data_blank_or_none(value):
            return str(value)
    return ""


def _r_source_string_literal(value):
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace("\r", "\\r")
    text = text.replace("\n", "\\n")
    text = text.replace("\t", "\\t")
    text = "".join(
        (
            "\\u%04x" % ord(character)
            if ord(character) <= 0xFFFF
            else "\\U%08x" % ord(character)
        )
        if ord(character) > 0x7F
        else character
        for character in text
    )
    return "'%s'" % text


def covariate_to_r_expression(
    cov, study_ids, dataset, named_list=True, return_covariate_values=False
):
    """The string is constructed so that the covariate
    values are in the same order as the 'study_names'
    list.
    """
    covariate_expression = None
    if named_list:
        covariate_expression = "%s=c(" % cov.name
    else:
        covariate_expression = "c("

    covariate_values_by_study = dataset.get_covariate_values(
        cov.name, ids_for_keys=True
    )

    # get the study ids in the same order as the names
    covariate_values = []

    for study_id in study_ids:
        if cov.data_type == CONTINUOUS:
            if study_id in covariate_values_by_study:
                covariate_values.append("%s" % covariate_values_by_study[study_id])
            else:
                covariate_values.append("NA")
        else:
            if study_id in covariate_values_by_study:
                # factor; note the string.
                covariate_values.append(
                    _r_source_string_literal(covariate_values_by_study[study_id])
                )
            else:
                covariate_values.append("NA")
    covariate_expression += ",".join(covariate_values) + ")"

    if return_covariate_values:
        return (covariate_expression, covariate_values)
    return covariate_expression


@overload
def run_small_study_effects(
    table_model,
    request,
    res_name="small_study_effects_result",
    data_name="tmp_obj",
    preview: Literal[False] = False,
) -> AnalysisResult: ...


@overload
def run_small_study_effects(
    table_model,
    request,
    res_name="small_study_effects_result",
    data_name="tmp_obj",
    preview: Literal[True] = True,
) -> Mapping[str, object]: ...


@serialized_r_call
def run_small_study_effects(
    table_model,
    request,
    res_name="small_study_effects_result",
    data_name="tmp_obj",
    preview=False,
) -> AnalysisResult | Mapping[str, object]:
    """Run the complete guided small-study effects workflow in one R call.

    Conversion is intentionally performed at this boundary.  RCMetaR then
    reconstructs compatible raw effects, computes eligibility, validates the
    request, and executes all selected procedures against one eligible set.
    """
    if not isinstance(request, dict):
        raise TypeError("small-study effects request must be a mapping")
    version = request.get("version")
    if type(version) is not int or version != 1:
        raise ValueError("unsupported small-study effects request version")
    family = request.get("data.type")
    if family == "binary":
        dataset_to_simple_binary_r_object(table_model, var_name=data_name)
    elif family == "continuous":
        dataset_to_simple_continuous_r_object(table_model, var_name=data_name)
    elif family == "diagnostic":
        dataset_to_simple_diagnostic_r_object(
            table_model, var_name=data_name, metric=request.get("metric", "DOR")
        )
    else:
        raise ValueError("unsupported small-study effects data family: %r" % family)
    r_request = dict(request)
    r_request["preview"] = bool(preview)
    result = execute_r_function(
        "rcmetar.run.small.study.effects",
        _r_object_from_symbol(data_name),
        _to_r_params(r_request),
    )
    if preview:
        return r_object_to_python(result.rx2("eligibility"))
    ro.globalenv[_r_symbol(res_name)] = result
    return parse_out_results(result)


@serialized_r_call
def regenerate_small_study_effects_funnel(params_path, output_path=None):
    """Regenerate a funnel from persisted per-run data and presentation params."""
    if not load_vars_for_plot(params_path):
        raise ValueError(
            "small-study effects plot data is incomplete: %s" % params_path
        )
    result = execute_r_function(
        "rcmetar.regenerate.small.study.funnel",
        _r_object_from_symbol("om.data"),
        _r_object_from_symbol("res"),
        _r_object_from_symbol("params"),
        _r_null_if_none(output_path),
    )
    return str(result[0]) if output_path is None and len(result) else output_path


@serialized_r_call
def generate_small_study_effects_funnel(file_path, params_name="params"):
    """Write a funnel artifact using the loaded per-run funnel parameters."""
    execute_r_function(
        "rcmetar.regenerate.small.study.funnel",
        _r_object_from_symbol("om.data"),
        _r_object_from_symbol("res"),
        _r_object_from_symbol(params_name),
        str(file_path),
    )


def _r_param_value(param):
    if isinstance(param, ro.ListVector):
        return param
    if param is None:
        return rpy2.rinterface.NULL
    if isinstance(param, bool):
        return ro.BoolVector([param])
    if isinstance(param, int) and not isinstance(param, bool):
        return ro.IntVector([param])
    if isinstance(param, float):
        return ro.FloatVector([ro.NA_Real if math.isnan(param) else param])
    if isinstance(param, str):
        return ro.StrVector([param])
    if isinstance(param, dict):
        return ro.ListVector(
            {str(key): _r_param_value(value) for key, value in param.items()}
        )
    if isinstance(param, (list, tuple)):
        if not param:
            return ro.StrVector([])
        if all(isinstance(value, bool) for value in param):
            return ro.BoolVector(list(param))
        if all(
            isinstance(value, int) and not isinstance(value, bool) for value in param
        ):
            return ro.IntVector(list(param))
        if all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in param
        ):
            return _r_numeric_vector(param)
        return _r_character_vector(param)
    return ro.StrVector([str(param)])


def _to_r_params(params):
    """Given a Python dictionary of method arguments, return a named R list."""
    return ro.ListVector(
        {str(param): _r_param_value(params[param]) for param in list(params.keys())}
    )


def _r_symbol(name):
    name = str(name)
    if not name.replace(".", "_").isidentifier():
        raise ValueError("Unsafe R symbol name: %s" % name)
    return name


def _r_object_from_symbol(name):
    return ro.globalenv[_r_symbol(name)]


def _normalize_rcmetar_workflow(workflow):
    if workflow is None:
        return "standard"
    workflow = str(workflow)
    known_workflows = {
        "standard",
        "cumulative",
        "leave-one-out",
        "subgroup",
        "bootstrap",
        "meta-regression",
    }
    if workflow not in known_workflows:
        raise ValueError("Unknown RCMetaR workflow: %s" % workflow)
    return workflow


@serialized_r_call
def run_versioned_analysis_request(
    request: Mapping[str, object],
    res_name: str = "result",
    data_name: str = "tmp_obj",
):
    """Execute one complete immutable request through the public RCMetaR API."""
    data_type, method, metric, workflow, params = _validated_versioned_request(request)
    return _execute_versioned_request(
        data_type, method, metric, workflow, params, res_name, data_name
    )


def _validated_versioned_request(
    request: Mapping[str, object],
) -> tuple[str, str, str, object, Mapping[str, object]]:
    version = request.get("version")
    if type(version) is not int or version != 1:
        raise ValueError("unsupported analysis request version")
    data_type = request.get("data_type")
    method = request.get("method")
    metric = request.get("metric")
    workflow = request.get("workflow")
    params = request.get("params")
    if not isinstance(data_type, str) or not data_type:
        raise ValueError("analysis request data_type must be non-empty text")
    if not isinstance(method, str) or not method:
        raise ValueError("analysis request method must be non-empty text")
    if not isinstance(metric, str) or not metric:
        raise ValueError("analysis request metric must be non-empty text")
    if not isinstance(workflow, str) or not workflow:
        raise ValueError("analysis request workflow must be non-empty text")
    if not isinstance(params, Mapping):
        raise TypeError("analysis request params must be a mapping")
    return data_type, method, metric, workflow, {
        str(key): value for key, value in params.items()
    }


def _execute_versioned_request(
    data_type: str,
    method: str,
    metric: str,
    workflow: object,
    params: Mapping[str, object],
    res_name: str,
    data_name: str,
) -> object:
    normalized = {
        "version": 1,
        "data_type": data_type,
        "method": method,
        "metric": metric,
        "params": _to_r_params(params),
        "workflow": _normalize_rcmetar_workflow(workflow),
    }
    result = execute_r_function(
        "rcmetar.run.analysis",
        _r_object_from_symbol(data_name),
        _to_r_params(normalized),
    )
    ro.globalenv[_r_symbol(res_name)] = result
    return parse_out_results(result)


@serialized_r_call
def run_versioned_analysis_requests(
    requests: list[Mapping[str, object]],
    res_name: str = "result",
    diagnostic_data_name: str = "tmp_obj",
):
    """Execute a validated diagnostic request set through one R operation."""
    methods, param_values, workflow = _validated_versioned_requests(requests)
    normalized_workflow = _normalize_rcmetar_workflow(workflow)
    return _execute_versioned_requests(
        methods, param_values, normalized_workflow, res_name, diagnostic_data_name
    )


def _validated_versioned_requests(
    requests: list[Mapping[str, object]],
) -> tuple[list[str], list[dict[str, object]], str]:
    if not requests:
        raise ValueError("at least one analysis request is required")
    methods: list[str] = []
    param_values: list[dict[str, object]] = []
    first = _validated_versioned_request(requests[0])
    data_type, _, _, workflow, _ = first
    for request in requests:
        current_data_type, method, _, current_workflow, values = (
            _validated_versioned_request(request)
        )
        if current_data_type != data_type or current_workflow != workflow:
            raise ValueError("one execution cannot mix analysis workflows")
        methods.append(method)
        param_values.append(dict(values))
    return methods, param_values, str(workflow)


def _execute_versioned_requests(
    methods: list[str],
    param_values: list[dict[str, object]],
    normalized_workflow: str,
    res_name: str,
    diagnostic_data_name: str,
) -> object:
    params = [_to_r_params(values) for values in param_values]
    try:
        result = execute_r_function(
            "rcmetar.run.diagnostic.analyses",
            _r_object_from_symbol(diagnostic_data_name),
            _r_character_vector(methods),
            execute_r_function("list", *params),
            workflow=normalized_workflow,
            version=1,
        )
    except RRuntimeError as error:
        raise DiagnosticExecutionError(str(error)) from error
    ro.globalenv[_r_symbol(res_name)] = result
    return parse_out_results(result)


@serialized_r_call
def load_vars_for_plot(params_path, return_params_dict=False):
    """Loads the three necessary (for plot generation) variables
    into R. we assume a naming convention in which params_path
    is the base, data is stored in *.data, params in *.params
    and result in *.res.
    """
    for var in ("data", "params", "res"):
        cur_path = "%s.%s" % (params_path, var)
        if os.path.exists(cur_path):
            load_in_r(cur_path)
        else:
            return False

    if return_params_dict:
        r_object = execute_r_string("params")
        params_dict = r_object_to_python(r_object)
        return params_dict
    return True


@serialized_r_call
def write_out_plot_data(params_out_path, plot_data_name="plot.data"):
    execute_r_function(
        "rcmetar.save.plot.data",
        _r_object_from_symbol(plot_data_name),
        str(params_out_path),
    )


@serialized_r_call
def load_in_r(fpath):
    """Loads what is presumed to be .Rdata into the R environment"""
    execute_r_function("load", str(fpath))


@serialized_r_call
def update_plot_params(
    plot_params, plot_params_name="params", write_them_out=False, outpath=None
):
    # Plot parameters include both study-length vectors and one value per
    # plotted funnel.  A data frame recycles or rejects those heterogeneous
    # lengths; a named list preserves the serialized parameter contract.
    ro.globalenv["tmp.params"] = _to_r_params(plot_params)
    plot_params_symbol = _r_symbol(plot_params_name)

    for param_name in plot_params:
        param_name = _r_symbol(param_name)
        execute_r_string(
            "%s$%s <- tmp.params$%s" % (plot_params_symbol, param_name, param_name)
        )

    if write_them_out:
        execute_r_function("save", **{"list": plot_params_symbol, "file": str(outpath)})


@serialized_r_call
def regenerate_plot_data(
    om_data_name="om.data",
    res_name="res",
    plot_params_name="params",
    plot_data_name="plot.data",
):

    plot_data = execute_r_function(
        "rcmetar.regenerate.plot.data",
        _r_object_from_symbol(om_data_name),
        _r_object_from_symbol(res_name),
        _r_object_from_symbol(plot_params_name),
    )
    ro.globalenv[_r_symbol(plot_data_name)] = plot_data


@serialized_r_call
def regenerate_regression_plot_data(
    om_data_name="om.data",
    res_name="res",
    plot_params_name="params",
    plot_data_name="plot.data",
):
    plot_data = execute_r_function(
        "rcmetar.regenerate.regression.plot.data",
        _r_object_from_symbol(om_data_name),
        _r_object_from_symbol(res_name),
        _r_object_from_symbol(plot_params_name),
    )
    ro.globalenv[_r_symbol(plot_data_name)] = plot_data


@serialized_r_call
def generate_reg_plot(file_path, params_name="plot.data"):
    execute_r_function(
        "rcmetar.draw.regression.plot",
        _r_object_from_symbol(params_name),
        str(file_path),
    )


@serialized_r_call
def generate_sroc_plot(file_path, params_name="plot.data"):
    execute_r_function(
        "rcmetar.draw.sroc.plot",
        _r_object_from_symbol(params_name),
        str(file_path),
    )


@serialized_r_call
def generate_forest_plot(file_path, params_name="plot.data"):
    execute_r_function(
        "rcmetar.draw.forest.plot",
        _r_object_from_symbol(params_name),
        str(file_path),
    )


@serialized_r_call
def parse_out_results(result):
    if _r_inherits(result, "try-error"):
        raise RuntimeError(_r_error_message(result))

    result = dict(_result_items_for_display(result))
    study_names = _study_names_from_result(result)
    metadata = _result_metadata(result)
    text_d = {}
    text_sources = {}

    for text_n, text in list(result.items()):
        if text_n in _RESULT_METADATA_KEYS or _r_is_null(text):
            continue
        _add_result_text(text_d, text_n, text, result, study_names)
        for index, key in enumerate(key for key in text_d if key not in text_sources):
            text_sources[key] = (text_n, index)

    sections = _text_section_metadata(text_sources, metadata["sections"])
    image_offset = len(sections)
    sections.extend(
        _image_section_metadata(
            metadata["images"],
            metadata["image_order"],
            metadata["image_var_names"],
            metadata["plot_capabilities"],
            metadata["sections"],
            image_offset,
        )
    )
    to_return = {
        "version": 1,
        "images": metadata["images"],
        "display_images": metadata["display_images"],
        "image_var_names": metadata["image_var_names"],
        "texts": text_d,
        "image_params_paths": metadata["image_params_paths"],
        "image_order": metadata["image_order"],
        "plot_capabilities": metadata["plot_capabilities"],
        "sections": sections,
    }
    return parse_analysis_result(to_return)


def _result_metadata(result):
    image_order = result.get("image_order")
    if image_order is None or _r_is_null(image_order):
        image_order = None
    else:
        image_order = list(image_order)
    return {
        "images": _r_mapping_or_empty(result.get("images")),
        "display_images": _r_mapping_or_empty(result.get("display_images")),
        "image_var_names": _r_mapping_or_empty(result.get("plot_names")),
        "image_params_paths": _r_mapping_or_empty(result.get("plot_params_paths")),
        "plot_capabilities": _r_mapping_or_empty(result.get("plot_capabilities")),
        "sections": _r_section_metadata(result.get("sections")),
        "image_order": image_order,
    }


_RESULT_METADATA_KEYS = frozenset(
    {
        "images",
        "display_images",
        "image_order",
        "plot_names",
        "plot_titles",
        "plot_params_paths",
        "plot_capabilities",
        "sections",
        "res",
        "res.info",
        "input_data",
        "input_params",
        "eligibility",
        "tests.data",
        "Trim-and-fill data",
    }
)


def _add_result_text(texts, name, value, result, study_names):
    title = _display_section_name(name)
    if name == "References":
        texts[title] = result_sections.format_references(value)
        return
    if name in ("weights", "Weights"):
        texts["Weights"] = make_weights_str(result)
        return
    if "gui.ignore" in name:
        return
    if _is_summary_display(value):
        texts[title] = _format_result_text(_capture_formatted_summary(value))
        return
    if _is_table_summary(value):
        texts.update(_format_table_summary(title, value, study_names=study_names))
        return
    if _has_r_names(value):
        texts.update(
            _format_named_result_summary(title, value, study_names=study_names)
        )
        return
    if _is_r_iterable(value):
        texts[title] = _format_r_vector(value, field_name=name)
        return
    texts[title] = _format_r_table_cell(value, field_name=name)


def _text_section_metadata(sources, producer_sections):
    by_source = {
        section["source_key"]: section
        for section in producer_sections
        if section.get("kind") == "text"
    }
    sections = []
    for order, (title, source) in enumerate(sources.items()):
        source_key, child_index = source
        supplied = by_source.get(source_key)
        semantic_id = (
            supplied["id"]
            if supplied is not None
            else _result_section_id("text", source_key)
        )
        if child_index:
            semantic_id = f"{semantic_id}:{child_index + 1}"
        sections.append(
            {
                "id": semantic_id,
                "kind": "text",
                "order": order,
                "title": supplied["title"]
                if supplied is not None and child_index == 0
                else title,
                "source_key": supplied["source_key"]
                if supplied is not None and child_index == 0
                else title,
            }
        )
    return sections


def _image_section_metadata(
    images, image_order, variable_names, capabilities, producer_sections, offset
):
    by_source = {
        section["source_key"]: section
        for section in producer_sections
        if section.get("kind") == "image"
    }
    sections = []
    used_ids = set()
    ordered_keys = [key for key in (image_order or images) if key in images]
    for index, image_key in enumerate(ordered_keys):
        supplied = by_source.get(image_key)
        capability = capabilities.get(image_key, {})
        semantic_key = variable_names.get(
            image_key,
            variable_names.get(
                image_key.lower(), capability.get("plot_kind", "plot")
            ),
        )
        semantic_id = (
            supplied["id"]
            if supplied is not None
            else _unique_result_section_id("image", semantic_key, used_ids)
        )
        used_ids.add(semantic_id)
        sections.append(
            {
                "id": semantic_id,
                "kind": "image",
                "order": offset + index,
                "title": supplied["title"] if supplied is not None else image_key,
                "source_key": image_key,
            }
        )
    return sections


def _unique_result_section_id(kind, source_key, used_ids):
    semantic_id = _result_section_id(kind, source_key)
    if semantic_id not in used_ids:
        return semantic_id
    suffix = 2
    while f"{semantic_id}:{suffix}" in used_ids:
        suffix += 1
    return f"{semantic_id}:{suffix}"


def _result_items_for_display(result):
    """Return ``(section, value)`` pairs without leaking R's NULL names."""
    if _r_is_null(result):
        return []
    names = _r_result_names(result)
    if names is not None:
        return [
            (name if name else "Result %d" % (index + 1), value)
            for index, (name, value) in enumerate(zip(names, list(result)))
        ]
    if isinstance(result, rpy2.robjects.vectors.ListVector):
        return [
            ("Result %d" % (index + 1), value)
            for index, value in enumerate(list(result))
        ]
    return [("Result", result)]


def _r_result_names(value):
    """Read partial names for a top-level R list without axis confusion."""
    if _r_is_null(value) or _r_dims(value):
        return None
    try:
        names = value.names
    except Exception:
        return None
    if _r_is_null(names):
        return None
    try:
        return [str(name) for name in list(names)]
    except Exception:
        return None


def _study_names_from_result(result):
    input_data = result.get("input_data")
    if input_data is None:
        return None
    try:
        study_names = [str(name) for name in list(input_data.do_slot("study.names"))]
    except Exception:
        return None
    if not study_names or any(name == "" for name in study_names):
        return None
    return study_names


def _r_mapping_or_empty(r_object):
    """Convert named R metadata to a mapping, including empty vectors."""
    if _r_is_null(r_object):
        return {}
    try:
        if len(r_object) == 0:
            return {}
    except TypeError:
        pass
    converted = r_object_to_python(r_object)
    return converted if isinstance(converted, Mapping) else {}


def _r_section_metadata(r_object):
    converted = r_object_to_python(r_object)
    if converted is None:
        return []
    if not isinstance(converted, list):
        raise ValueError("RCMetaR result sections must be a list")
    sections = []
    for item in converted:
        if not isinstance(item, Mapping):
            raise ValueError("RCMetaR result section must be a mapping")
        section = {
            key: value[0] if isinstance(value, list) and len(value) == 1 else value
            for key, value in item.items()
        }
        sections.append(section)
    return sections


def _r_inherits(r_object, class_name):
    try:
        return bool(execute_r_function("inherits", r_object, class_name)[0])
    except Exception:
        return False


def _r_error_message(r_object):
    try:
        if len(r_object) > 0:
            return str(r_object[0]).strip()
    except Exception:
        pass
    return str(r_object).strip()


def _is_table_summary(r_object):
    return len(_r_dims(r_object)) in (2, 3)


def _is_summary_display(r_object):
    return bool(execute_r_function("inherits", r_object, "summary.display")[0])


@serialized_r_call
def _capture_formatted_summary(r_object):
    capture_summary = _r_eval(
        "function(x) paste(capture.output(print(x)), collapse='\\n')"
    )
    return _first_dynamic(_call_dynamic(capture_summary, r_object))


def _format_table_summary(section_name, r_object, title=None, study_names=None):
    dims = _r_dims(r_object)
    if len(dims) == 2:
        if _is_large_display_shape(dims):
            return {section_name: _format_shape_summary(dims)}
        return {section_name: _format_r_matrix(r_object, study_names=study_names)}
    if len(dims) == 3:
        if _is_large_display_shape(dims):
            return {section_name: _format_shape_summary(dims)}
        return _format_r_array_sections(
            "Summary", section_name, r_object, study_names=study_names
        )
    return {section_name: _format_r_table_cell(r_object, field_name=section_name)}


def _is_named_table_summary(r_object):
    if not _has_r_names(r_object):
        return False

    for item in list(r_object):
        dims = _r_dims(item)
        if len(dims) in (2, 3):
            return True
    return False


def _result_section_id(kind, source_key):
    """Return a stable semantic ID supplied by the result producer's key."""
    normalized = re.sub(r"[^a-z0-9]+", "-", str(source_key).lower()).strip("-")
    return f"{kind}:{normalized or 'unnamed'}"


def _format_named_result_summary(parent_name, r_object, study_names=None):
    # The one-study methods wrap their four useful values in a technical
    # ``MAResults`` list for compatibility with the multi-study model.  It is
    # not a meaningful heading in the Results window, so unwrap that single
    # transport layer before rendering the fields.
    wrapped = _unwrapped_ma_results(r_object)
    if wrapped is not None:
        return {parent_name: _format_named_value(wrapped, study_names=study_names)}
    if _is_named_table_summary(r_object):
        return _format_named_table_summary(
            parent_name, r_object, study_names=study_names
        )
    if _is_named_text_summary(r_object):
        return _format_named_text_summary(parent_name, r_object)
    rendered = _format_named_value(r_object, study_names=study_names)
    return {parent_name: rendered} if rendered else {}


def _unwrapped_ma_results(r_object):
    if not _has_r_names(r_object):
        return None
    names = [str(name) for name in list(r_object.names)]
    if len(names) != 1 or names[0].replace(" ", "") != "MAResults":
        return None
    wrapped = list(r_object)[0]
    return wrapped if _has_r_names(wrapped) else None


def _is_named_text_summary(r_object):
    if not _has_r_names(r_object):
        return False

    has_named_text = False
    for item in list(r_object):
        # A named character vector is a structured estimate (for example,
        # Estimate/Lower bound/Upper bound), not a one-line text section.
        # Treating it as text silently discarded all but item[0].
        if not _is_r_string_vector(item) or _r_names_or_none(item) is not None:
            return False
        has_named_text = True
    return has_named_text


def _format_named_text_summary(parent_name, r_object):
    sections = {}
    for name, item in zip(list(r_object.names), list(r_object)):
        if name == "" or not _is_r_string_vector(item):
            continue
        sections[_summary_section_name(parent_name, _display_section_name(name))] = (
            _format_result_text(item[0])
        )

    if not sections:
        sections[parent_name] = _format_result_text(str(r_object))
    return sections


def _format_named_table_summary(parent_name, r_object, study_names=None):
    sections = {}
    for name, item in zip(list(r_object.names), list(r_object)):
        if name == "":
            continue
        sections.update(
            _format_named_table_item(parent_name, str(name), item, study_names)
        )

    if not sections:
        sections[parent_name] = _format_result_text(str(r_object))
    return sections


def _format_named_table_item(parent_name, name, item, study_names):
    display_name = _display_section_name(name)
    section_name = _summary_section_name(parent_name, display_name)
    dims = _r_dims(item)
    if len(dims) == 2:
        return _format_table_summary(
            section_name, item, display_name, study_names=study_names
        )
    if len(dims) == 3:
        return _format_r_array_sections(
            parent_name, display_name, item, study_names=study_names
        )
    if _is_r_string_vector(item):
        text = ", ".join(str(value) for value in item)
        return {section_name: _format_result_text(text)}
    if _has_r_names(item):
        rendered = _format_named_value(item, study_names=study_names)
    elif _is_r_iterable(item):
        rendered = _format_r_vector(item)
    else:
        rendered = _format_r_table_cell(item, field_name=name)
    return {section_name: rendered} if rendered else {}


def _format_named_value(r_object, study_names=None):
    """Render a named R list without exposing R's console representation."""
    lines = []
    names = list(r_object.names)
    named_items = list(zip(names, list(r_object)))
    named_items = sorted(
        enumerate(named_items),
        key=lambda pair: (_named_value_priority(pair[1][0]), pair[0]),
    )
    for _index, (name, item) in named_items:
        if not name or _r_is_null(item):
            continue
        label = _format_summary_label(name)
        rendered = _format_nested_value(item, study_names=study_names, field_name=name)
        if not rendered:
            continue
        if "\n" in rendered:
            lines.append("%s:" % label)
            lines.extend("  %s" % line for line in rendered.splitlines())
        else:
            lines.append("%s: %s" % (label, rendered))
    return "\n".join(lines)


def _format_nested_value(r_object, study_names=None, field_name=None):
    dims = _r_dims(r_object)
    if len(dims) == 2:
        if dims[0] > 20 or dims[0] * dims[1] > 100:
            return "%d rows x %d columns" % (dims[0], dims[1])
        return _format_r_matrix(r_object, study_names=study_names)
    if len(dims) == 3:
        rendered = _format_r_array_sections(
            "Summary", "Values", r_object, study_names=study_names
        )
        return "\n\n".join(rendered.values())
    if _has_r_names(r_object):
        return _format_named_value(r_object, study_names=study_names)
    if _is_r_iterable(r_object):
        return _format_r_vector(r_object, field_name=field_name)
    return _format_r_table_cell(r_object, field_name=field_name)


def _format_r_vector(r_object, field_name=None):
    names = _r_names_or_none(r_object)
    values = list(r_object)
    if not values:
        return ""
    if names is not None:
        return "\n".join(
            "%s: %s"
            % (
                _format_summary_label(name),
                _format_r_table_cell(value, field_name=name),
            )
            for name, value in zip(names, values)
        )
    if len(values) == 1:
        return _format_r_table_cell(values[0], field_name=field_name)
    return ", ".join(
        _format_r_table_cell(value, field_name=field_name) for value in values
    )


def _named_value_priority(name):
    """Order decision-relevant fields before implementation diagnostics."""
    compact = re.sub(r"[^a-z0-9]", "", str(name).lower())
    if compact in {"estimate", "te", "effect", "coefficient", "b"}:
        return 0
    if compact in {"lower", "lowerbound", "cilb", "ci95lb", "lowerci"}:
        return 1
    if compact in {"upper", "upperbound", "ciub", "ci95ub", "upperci"}:
        return 2
    if compact in {"p", "pvalue", "pval", "prz"}:
        return 3
    if compact in {"se", "stderr", "standarderror", "z", "zvalue", "zval"}:
        return 4
    return 10


def _is_large_display_shape(dims):
    return bool(dims) and (dims[0] > 20 or math.prod(dims) > 100)


def _format_shape_summary(dims):
    if len(dims) == 2:
        return "%d rows x %d columns" % (dims[0], dims[1])
    if len(dims) == 3:
        return "%d rows x %d columns x %d slices" % tuple(dims)
    return "Array with dimensions %s" % " x ".join(str(dim) for dim in dims)


def _format_summary_label(name):
    labels = {
        "normalized.partial.AUC": "Normalized partial AUC",
        "partial.FPR.bounds": "Partial FPR bounds",
        "false.positive.rate": "False-positive rate",
        "covariance.sensitivity.specificity": "Sensitivity-specificity covariance",
        "correlation.sensitivity.specificity": "Sensitivity-specificity correlation",
        "summary.seed": "Summary seed",
        "summary.iterations": "Summary iterations",
        "p.value": "p-value",
        "z.value": "z-value",
    }
    raw_name = str(name)
    if raw_name in labels:
        return labels[raw_name]
    compact_name = re.sub(r"[^a-z0-9]", "", raw_name.lower())
    if compact_name in {"b", "estimate"}:
        return "Estimate"
    if compact_name in {"lower", "cilb", "lowerbound", "lowerci", "lb"}:
        return "Lower bound"
    if compact_name in {"upper", "ciub", "upperbound", "upperci", "ub"}:
        return "Upper bound"
    if compact_name in {"se", "sei", "stderr", "standarderror"}:
        return "Std. error"
    if compact_name in {"sensitivity", "summarysensitivity"}:
        return "Sensitivity"
    if compact_name in {"specificity", "summaryspecificity"}:
        return "Specificity"
    # Keep one label policy for section titles and nested result values.  The
    # shared helper expands R's dotted/underscored identifiers and diagnostic
    # abbreviations without changing numeric/statistical content.
    return result_sections.normalize_identifier_label(raw_name)


def _summary_section_name(parent_name, child_name):
    if parent_name == "Summary":
        return child_name
    return "%s: %s" % (parent_name, child_name)


def _display_section_name(name):
    stable_titles = {
        "small-study-warning": "Warning",
        "small-study-data-eligibility": "Data and eligibility",
        "small-study-tests": "Tests",
        "small-study-pooled-comparison": "Pooled comparison",
        "small-study-references": "References",
        "small-study-failures": "Failures",
        "small-study-method-details": "Method details",
        "small-study-methods-not-applicable": "Methods not applicable",
        "small-study-extrapolation": "Extrapolation",
    }
    if name in stable_titles:
        return stable_titles[name]
    if str(name).startswith("small-study.trim-and-fill."):
        suffix = str(name).rsplit(".", 1)[-1]
        return "Trim-and-fill " + suffix.title()
    return method_display_label(str(name))


def _is_r_string_vector(r_object):
    return isinstance(r_object, rpy2.robjects.vectors.StrVector)


def _r_dims(r_object):
    if not isinstance(r_object, rpy2.robjects.vectors.Vector):
        return []
    try:
        dims = execute_r_function("dim", r_object)
    except Exception:
        return []
    if _r_is_null(dims):
        return []
    return [int(dim) for dim in list(dims)]


def _r_dimnames(r_object):
    dimnames = execute_r_function("dimnames", r_object)
    if _r_is_null(dimnames):
        return []
    return [
        None if _r_is_null(names) else [str(name) for name in list(names)]
        for names in list(dimnames)
    ]


def _r_names_or_none(r_object):
    if _r_dims(r_object):
        return None
    names = getattr(r_object, "names", None)
    if names is None or _r_is_null(names):
        return None
    names = [str(name) for name in list(names)]
    if not names or any(name == "" for name in names):
        return None
    return names


def _format_r_matrix(matrix, study_names=None):
    dims = _r_dims(matrix)
    dimnames = _r_dimnames(matrix)
    row_names = dimnames[0] if len(dimnames) > 0 and dimnames[0] is not None else None
    col_names = dimnames[1] if len(dimnames) > 1 and dimnames[1] is not None else None
    values = list(matrix)
    return _format_matrix_values(
        values, dims[0], dims[1], row_names, col_names, study_names=study_names
    )


def _format_r_array_sections(parent_name, array_name, r_array, study_names=None):
    dims = _r_dims(r_array)
    dimnames = _r_dimnames(r_array)
    row_names = dimnames[0] if len(dimnames) > 0 and dimnames[0] is not None else None
    col_names = dimnames[1] if len(dimnames) > 1 and dimnames[1] is not None else None
    slice_names = (
        dimnames[2]
        if len(dimnames) > 2 and dimnames[2] is not None
        else [str(index + 1) for index in range(dims[2])]
    )

    values = list(r_array)
    sections = {}
    slice_size = dims[0] * dims[1]
    for slice_index, slice_name in enumerate(slice_names):
        start = slice_index * slice_size
        end = start + slice_size
        title = "%s - %s" % (array_name, slice_name)
        sections[_summary_section_name(parent_name, title)] = _format_matrix_values(
            values[start:end],
            dims[0],
            dims[1],
            row_names,
            col_names,
            study_names=study_names,
        )
    return sections


def _format_matrix_values(values, nrow, ncol, row_names, col_names, study_names=None):
    # rpy2 exposes an R data.frame as a list of column vectors, while a plain
    # matrix is exposed as one column-major flat vector.  Both objects have
    # the same ``dim`` contract, so normalize the values before indexing.
    values = _matrix_cell_values(values, nrow, ncol)
    headers = _matrix_column_names(col_names, ncol)
    rows = []
    row_names = _matrix_row_names(row_names, nrow, study_names)
    include_row_names = row_names is not None
    if include_row_names:
        headers = [""] + headers

    for row_index in range(nrow):
        row = []
        if include_row_names:
            row.append(row_names[row_index])
        for col_index in range(ncol):
            field_name = headers[col_index + (1 if include_row_names else 0)]
            row.append(
                _format_r_table_cell(
                    values[row_index + (col_index * nrow)],
                    field_name=field_name,
                )
            )
        rows.append(row)

    return _format_text_table(headers, rows)


def _matrix_cell_values(values, nrow, ncol):
    """Return exactly ``nrow * ncol`` safe, column-major table cells."""
    values = list(values)
    expected = nrow * ncol
    if len(values) == expected:
        return values

    # A data.frame iterates over its ncol column vectors.  Flatten each
    # column explicitly; this is the common shape for named Reitsma tables.
    if len(values) == ncol:
        flattened = []
        for column in values:
            try:
                column_values = list(column)
            except TypeError:
                column_values = [column]
            flattened.extend(column_values[:nrow])
            if len(column_values) < nrow:
                flattened.extend([None] * (nrow - len(column_values)))
        values = flattened

    # Malformed or partially populated R objects should remain renderable;
    # missing cells are clearer than an indexing exception in the GUI.
    if len(values) < expected:
        values.extend([None] * (expected - len(values)))
    return values[:expected]


def _matrix_column_names(col_names, ncol):
    names = list(col_names) if col_names is not None else []
    names = names[:ncol]
    names.extend("V%s" % (index + 1) for index in range(len(names), ncol))
    return [_format_r_table_header(name) for name in names]


def _matrix_row_names(row_names, nrow, study_names):
    if row_names is None:
        return None
    names = list(row_names)[:nrow]
    if len(names) < nrow:
        names.extend(str(index + 1) for index in range(len(names), nrow))
    names = _display_row_names(names, study_names)
    return [result_sections.normalize_identifier_label(name) for name in names]


def _display_row_names(row_names, study_names):
    if row_names is None:
        return None
    if _row_names_are_generic_study_ids(row_names, study_names):
        return list(study_names)
    return row_names


def _row_names_are_generic_study_ids(row_names, study_names):
    if study_names is None or len(row_names) != len(study_names):
        return False
    expected_numbers = [str(index + 1) for index in range(len(row_names))]
    expected_studies = ["Study %s" % (index + 1) for index in range(len(row_names))]
    return list(row_names) in (expected_numbers, expected_studies)


def _format_r_table_cell(value, field_name=None):
    if _is_r_iterable(value) and len(value) == 1:
        value = _r_singleton_to_scalar(value)
    if value is None or str(value) == "NA":
        return "NA"
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            return "NA" if math.isnan(value) else ("-Inf" if value < 0 else "Inf")
        compact_name = re.sub(r"[^a-z0-9]", "", str(field_name or "").lower())
        if compact_name in {"p", "pvalue", "pval", "prz", "qmp", "qep"}:
            if value < 0.001:
                return "< 0.001"
            return "%.3f" % value
        if float(value).is_integer():
            return str(int(value))
        return "%.4g" % value
    return _format_result_text(str(value))


def _format_text_table(headers, rows):
    table_rows = [headers] + rows
    widths = [
        max(len(str(row[col_index])) for row in table_rows)
        for col_index in range(len(headers))
    ]
    rendered_rows = []
    for row_index, row in enumerate(table_rows):
        cells = []
        for col_index, cell in enumerate(row):
            cell = str(cell)
            if col_index == 0:
                cells.append(cell.ljust(widths[col_index]))
            else:
                cells.append(cell.rjust(widths[col_index]))
        rendered_rows.append("  ".join(cells).rstrip())
        if row_index == 0:
            rendered_rows.append("  ".join("-" * width for width in widths).rstrip())
    return "\n".join(rendered_rows)


def _format_r_table_header(value):
    normalized = str(value).strip()
    # Percentile column labels such as ``2.5%`` are already meaningful; do
    # not run them through identifier normalization, which would turn the
    # decimal point into a space.
    percentile = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", normalized)
    if percentile:
        return "%s%%" % percentile.group(1)
    if re.fullmatch(
        r"\d+(?:\.\d+)?\s*%?\s*ci[._\s]*(?:lb|lower)",
        normalized,
        flags=re.IGNORECASE,
    ):
        return "Lower bound"
    if re.fullmatch(
        r"\d+(?:\.\d+)?\s*%?\s*ci[._\s]*(?:ub|upper)",
        normalized,
        flags=re.IGNORECASE,
    ):
        return "Upper bound"
    compact = normalized.lower().replace(".", " ").replace("_", " ").replace("-", " ")
    compact = " ".join(compact.split())
    if compact == "p value":
        return "p-value"
    if normalized.lower() == "pr(>|z|)":
        return "p-value"
    if compact == "het p value":
        return "Het. p-value"
    if compact == "omnibus p value":
        return "Omnibus p-value"
    if compact == "z value":
        return "z-value"
    if compact in ("hpd low", "hpd lower", "ci lb", "lower bound"):
        return "Lower bound"
    if compact in ("hpd high", "hpd upper", "ci ub", "upper bound"):
        return "Upper bound"
    if compact == "median estimate":
        return "Median estimate"
    return result_sections.normalize_identifier_label(normalized)


def _format_result_text(text):
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(
        r"<U\+([0-9A-Fa-f]{4,6})>",
        lambda match: chr(int(match.group(1), 16)),
        text,
    )
    text = _clean_console_text(text)
    text = _replace_result_labels(text)
    return text


def _clean_console_text(text):
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if stripped == "NULL" or stripped.startswith(('attr(,"', "[[", "$")):
            continue
        cleaned_lines.append(_console_payload(line, stripped))
    return "\n".join(cleaned_lines).strip()


def _console_payload(line, stripped):
    match = re.match(r"^\[\d+\]\s+(.*)$", stripped)
    if match is None:
        return line
    payload = match.group(1)
    quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', payload)
    if quoted and " ".join(quoted) == payload.replace('"', "").strip():
        return ", ".join(quoted)
    return payload


def _replace_result_labels(text):
    for raw_label, display_label in (
        ("Zhou.Dendukuri", "Zhou-Dendukuri"),
        ("Holling.Unadjusted", "Holling (unadjusted)"),
        ("Holling.Adjusted", "Holling (adjusted)"),
        ("posLR", "Positive Likelihood Ratio"),
        ("negLR", "Negative Likelihood Ratio"),
        ("invnegLR", "Inverse Negative Likelihood Ratio"),
    ):
        text = text.replace(raw_label, display_label)
    insensitive_replacements = (
        (r"\bHPD[._\s]+(?:low|lower)\b", "Lower bound"),
        (r"\bHPD[._\s]+(?:high|upper)\b", "Upper bound"),
        (r"\bci[._\s]*lb\b", "Lower bound"),
        (r"\bci[._\s]*ub\b", "Upper bound"),
        (r"\blower[._]+bound\b", "Lower bound"),
        (r"\bupper[._]+bound\b", "Upper bound"),
        (r"\bhet[._\s]+p[._\s-]*value\b", "Het. p-value"),
        (r"\bp[._\s-]*value\b", "p-value"),
        (r"\bz[._\s-]*value\b", "z-value"),
    )
    for pattern, replacement in insensitive_replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\bLower Bound\b", "Lower bound", text)
    text = re.sub(r"\bUpper Bound\b", "Upper bound", text)
    return text


def make_weights_str(results):
    """Make a string representing the weights due to each study in the meta analysis"""
    weights_object = results.get("weights", results.get("Weights"))
    if weights_object is None:
        raise Exception("make_weights_str() requires 'weights' in the results")

    raw_weights = _weight_values(weights_object)
    if not raw_weights:
        return "No study weights available.\n"
    weights = [_format_weight(value) for value in raw_weights]
    study_names = _weight_study_names(results, weights_object, len(weights))
    return _weight_table(study_names, weights)


def _weight_values(weights_object):
    return list(weights_object) if _is_r_iterable(weights_object) else [weights_object]


def _format_weight(value):
    scalar = value
    if _is_r_iterable(value) and len(value) == 1:
        scalar = _r_singleton_to_scalar(value)
    if scalar is None or str(scalar) == "NA":
        return "NA"
    try:
        return "{0:.{digits}f}%".format(float(scalar), digits=PERCENTAGE_DISPLAY_DIGITS)
    except (TypeError, ValueError):
        return _format_r_table_cell(scalar)


def _weight_study_names(results, weights_object, count):
    if "input_data" in results:
        study_names = list(results["input_data"].do_slot("study.names"))
    else:
        weight_names = _r_names_or_none(weights_object)
        if weight_names is not None and len(weight_names) == count:
            study_names = weight_names
        else:
            study_names = _default_study_names(count)
    return study_names if len(study_names) == count else _default_study_names(count)


def _default_study_names(count):
    return ["Study %d" % (index + 1) for index in range(count)]


def _weight_table(study_names, weights):
    table, widths = tabulate(
        [study_names, weights], sep=": ", return_col_widths=True, align=["L", "R"]
    )
    header = "{0:<{widths[0]}}  {1:<{widths[1]}}".format(
        "Study names", "Weights", widths=widths
    )
    return "\n".join([header, table]) + "\n"


def _get_col(m, i):
    col_vals = []
    for x in m:
        col_vals.append(x[i])
    return col_vals


@serialized_r_call
def diagnostic_effects_for_study(
    tp, fn, fp, tn, metrics=("Spec", "Sens"), confidence_level=95.0
):
    confidence_level = validate_confidence_level(confidence_level)
    r_res = execute_r_function(
        "rcmetar.diagnostic.study.effects",
        tp,
        fn,
        fp,
        tn,
        metrics=_r_character_vector(metrics),
        **{"conf.level": confidence_level},
    )
    return normalize_diagnostic_effects(
        r_object_to_python(r_res),
        require_triplets=True,
    )


@serialized_r_call
def continuous_effect_for_study(
    n1,
    m1,
    sd1,
    se1=None,
    n2=None,
    m2=None,
    sd2=None,
    se2=None,
    metric="MD",
    two_arm=True,
    confidence_level=95.0,
):
    confidence_level = validate_confidence_level(confidence_level)
    r_res = execute_r_function(
        "rcmetar.continuous.study.effect",
        n1=_r_null_if_none(n1),
        m1=_r_null_if_none(m1),
        sd1=_r_null_if_none(sd1),
        se1=_r_null_if_none(se1),
        n2=_r_null_if_none(n2),
        m2=_r_null_if_none(m2),
        sd2=_r_null_if_none(sd2),
        se2=_r_null_if_none(se2),
        metric=str(metric),
        **{"two.arm": bool(two_arm), "conf.level": confidence_level},
    )
    return normalize_effect_result(
        r_object_to_python(r_res),
        metric=metric,
    )


@serialized_r_call
def effect_for_study(
    e1, n1, e2=None, n2=None, two_arm=True, metric="OR", confidence_level=95
):
    """Compute an estimate and confidence interval for binary study data."""
    confidence_level = validate_confidence_level(confidence_level)
    r_res = execute_r_function(
        "rcmetar.binary.study.effect",
        e1=_r_null_if_none(e1),
        n1=_r_null_if_none(n1),
        e2=_r_null_if_none(e2),
        n2=_r_null_if_none(n2),
        **{
            "two.arm": bool(two_arm),
            "metric": str(metric),
            "conf.level": confidence_level,
        },
    )
    return normalize_effect_result(
        r_object_to_python(r_res),
        metric=metric,
    )


def binary_convert_scale(x, metric_name, convert_to="display.scale", n1=None):
    # convert_to is either 'display.scale' or 'calc.scale'
    return generic_convert_scale(x, metric_name, "binary", convert_to, n1)


def continuous_convert_scale(x, metric_name, convert_to="display.scale"):
    return generic_convert_scale(x, metric_name, "continuous", convert_to)


def diagnostic_convert_scale(x, metric_name, convert_to="display.scale"):
    return generic_convert_scale(x, metric_name, "diagnostic", convert_to)


@serialized_r_call
def generic_convert_scale(
    x, metric_name, data_type, convert_to="display.scale", n1=None
):
    if x is None or x == "":
        return None
    islist = isinstance(x, list) or isinstance(
        x, tuple
    )  # being loose with what qualifies as a 'list' here.
    if islist:
        x_arg = _r_numeric_vector(x)
        n1_arg = (
            rpy2.rinterface.NULL if n1 is None else _r_numeric_vector([n1] * len(x))
        )
    else:
        x_arg = x
        n1_arg = _r_null_if_none(n1)

    transformed = execute_r_function(
        "rcmetar.convert.scale",
        x=x_arg,
        metric=str(metric_name),
        **{"data.type": str(data_type), "convert.to": str(convert_to), "n1": n1_arg},
    )
    transformed_ls = [x_i for x_i in transformed]
    if not islist:
        # scalar
        return transformed_ls[0]
    return transformed_ls
