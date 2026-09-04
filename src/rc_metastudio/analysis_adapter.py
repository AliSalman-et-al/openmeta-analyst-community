# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed, Qt-independent requests at the Analysis Adapter boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Protocol, TypeAlias, cast, runtime_checkable

from rc_metastudio import r_bridge
from rc_metastudio import analysis_dataset
from rc_metastudio import result_sections
from rc_metastudio.analysis_results import AnalysisResult, parse_analysis_result
from rc_metastudio.analysis_errors import DiagnosticExecutionError


AnalysisValue: TypeAlias = bool | int | float | str | None
AnalysisFamily: TypeAlias = Literal["binary", "continuous", "diagnostic"]
AnalysisWorkflow: TypeAlias = Literal[
    "standard",
    "cumulative",
    "leave-one-out",
    "subgroup",
    "bootstrap",
    "meta-regression",
]

_FAMILY_METRICS: Mapping[AnalysisFamily, frozenset[str]] = {
    "binary": frozenset(
        {"OR", "RD", "RR", "AS", "YUQ", "YUY", "PR", "PLN", "PLO", "PAS", "PFT"}
    ),
    "continuous": frozenset({"MD", "SMD", "TX Mean"}),
    "diagnostic": frozenset({"Sens", "Spec", "PLR", "NLR", "DOR"}),
}


class CovariateDataset(Protocol):
    """Dataset operation required by covariate-qualified study selection."""

    def get_covariate_values(
        self, covariate: str, ids_for_keys: bool = False
    ) -> Mapping[int, object]: ...


class CovariateSelectionModel(Protocol):
    """Model operations required by covariate-qualified study selection."""

    dataset: CovariateDataset

    def get_studies(
        self, only_if_included: bool = True
    ) -> list[analysis_dataset.Study]: ...


class MetaRegressionModel(Protocol):
    """Model operation required by meta-regression conversion."""

    dataset: analysis_dataset.Dataset


@runtime_checkable
class DiagnosticExecutionModel(Protocol):
    """Model queries required before diagnostic execution."""

    def included_studies_have_raw_data(self) -> bool: ...

    def included_studies_have_point_estimates(self, effect: str) -> bool: ...


@dataclass(frozen=True)
class AnalysisParameter:
    """One normalized value passed to the R analysis boundary."""

    name: str
    value: AnalysisValue


@dataclass(frozen=True)
class AnalysisRequest:
    """A complete, locale-independent analysis invocation."""

    data_type: AnalysisFamily
    workflow: AnalysisWorkflow
    method: str
    metric: str
    parameters: tuple[AnalysisParameter, ...]
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError(f"unsupported analysis request version: {self.version}")
        _required_text("metric", self.metric)

    @property
    def semantic_id(self) -> str:
        """Stable identity for this request's meaning, excluding presentation."""
        payload = {
            "data_type": self.data_type,
            "metric": self.metric,
            "method": self.method,
            "parameters": [(item.name, item.value) for item in self.parameters],
            "version": self.version,
            "workflow": self.workflow,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def to_mapping(self) -> dict[str, object]:
        """Return the explicit wire representation consumed by RCMetaR."""
        parameters = self.parameter_values()
        parameters.setdefault("measure", self.metric)
        return {
            "version": self.version,
            "request.version": self.version,
            "data_type": self.data_type,
            "data.type": self.data_type,
            "workflow": self.workflow,
            "method": self.method,
            "metric": self.metric,
            "params": parameters,
            "parameters": self.parameter_values(),
        }

    def parameter_values(self) -> dict[str, AnalysisValue]:
        return {parameter.name: parameter.value for parameter in self.parameters}


@dataclass(frozen=True)
class StudySelectionResult:
    """Included studies that have values for every selected covariate."""

    studies: tuple[analysis_dataset.Study, ...]
    has_missing_values: bool
    excluded_study_names: tuple[str, ...] = ()


def select_studies_for_covariates(
    model: CovariateSelectionModel,
    selected_covariates: Sequence[analysis_dataset.Covariate],
) -> StudySelectionResult:
    """Select included studies with complete values for selected covariates."""
    covariate_values = {
        covariate.name: model.dataset.get_covariate_values(
            covariate.name, ids_for_keys=True
        )
        for covariate in selected_covariates
    }
    studies = []
    excluded_study_names = []
    has_missing_values = False
    for study in model.get_studies(only_if_included=True):
        if all(
            study.id in covariate_values[covariate.name]
            for covariate in selected_covariates
        ):
            studies.append(study)
        else:
            has_missing_values = True
            excluded_study_names.append(str(study.name))
    return StudySelectionResult(
        tuple(studies), has_missing_values, tuple(excluded_study_names)
    )


def make_analysis_request(
    *,
    data_type: str,
    workflow: str | None,
    method: str,
    metric: str,
    parameters: Mapping[str, object],
) -> AnalysisRequest:
    """Validate and freeze values selected by a user-facing configuration."""
    normalized_data_type = _analysis_family(data_type)
    normalized_method = _required_text("analysis method", method)
    normalized_workflow = _analysis_workflow(workflow or "standard")
    normalized_metric = _required_text("metric", metric)
    if normalized_metric not in _FAMILY_METRICS[normalized_data_type]:
        raise ValueError(
            f"metric {normalized_metric!r} is not valid for {normalized_data_type} analysis"
        )
    normalized_parameters = tuple(
        AnalysisParameter(_required_text("parameter name", name), _native_value(value))
        for name, value in sorted(parameters.items())
    )
    return AnalysisRequest(
        data_type=normalized_data_type,
        workflow=normalized_workflow,
        method=normalized_method,
        metric=normalized_metric,
        parameters=normalized_parameters,
    )


def _required_text(label: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _analysis_family(value: object) -> AnalysisFamily:
    if value == "binary":
        return "binary"
    if value == "continuous":
        return "continuous"
    if value == "diagnostic":
        return "diagnostic"
    raise ValueError(f"unsupported analysis data family: {value!r}")


def _analysis_workflow(value: object) -> AnalysisWorkflow:
    if value == "standard":
        return "standard"
    if value == "cumulative":
        return "cumulative"
    if value == "leave-one-out":
        return "leave-one-out"
    if value == "subgroup":
        return "subgroup"
    if value == "bootstrap":
        return "bootstrap"
    if value == "meta-regression":
        return "meta-regression"
    raise ValueError(f"unsupported analysis workflow: {value!r}")


def _native_value(value: object) -> AnalysisValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(
        "analysis parameters must be native bool, int, float, str, or None values; "
        f"received {type(value).__name__}"
    )


def _typed_result(value: object) -> AnalysisResult:
    """Parse raw boundary data once; R bridge results are already typed."""
    if isinstance(value, AnalysisResult):
        return value
    return parse_analysis_result(value)


def execute_analysis_requests(
    model: object,
    requests: Sequence[AnalysisRequest],
    selected_covariates: Sequence[analysis_dataset.Covariate] = (),
) -> AnalysisResult:
    """Execute a frozen set of analysis requests through the R backend."""
    if not requests:
        raise ValueError("No analysis requests were configured.")
    data_types = {request.data_type for request in requests}
    if len(data_types) != 1:
        raise ValueError("One execution cannot mix analysis data families.")
    data_type = requests[0].data_type
    if data_type == "binary":
        return _execute_binary_request(model, requests, selected_covariates)
    if data_type == "continuous":
        return _execute_continuous_request(model, requests, selected_covariates)
    if data_type == "diagnostic":
        return _execute_diagnostic_request(model, requests)
    raise ValueError("Unsupported analysis data family: %s" % data_type)


def _execute_binary_request(
    model: object,
    requests: Sequence[AnalysisRequest],
    selected_covariates: Sequence[analysis_dataset.Covariate],
) -> AnalysisResult:
    if len(requests) != 1:
        raise ValueError("Binary execution requires exactly one request.")
    r_bridge.dataset_to_simple_binary_r_object(
        model, **_conversion_kwargs(selected_covariates)
    )
    return _typed_result(_run_binary_request(requests[0]))


def _execute_continuous_request(
    model: object,
    requests: Sequence[AnalysisRequest],
    selected_covariates: Sequence[analysis_dataset.Covariate],
) -> AnalysisResult:
    if len(requests) != 1:
        raise ValueError("Continuous execution requires exactly one request.")
    r_bridge.dataset_to_simple_continuous_r_object(
        model, **_conversion_kwargs(selected_covariates)
    )
    return _typed_result(_run_continuous_request(requests[0]))


def _execute_diagnostic_request(
    model: object, requests: Sequence[AnalysisRequest]
) -> AnalysisResult:
    if not isinstance(model, DiagnosticExecutionModel):
        raise TypeError("Diagnostic execution requires the diagnostic model queries.")
    return _run_diagnostic_analysis_isolating_metric_failures(model, requests)


def execute_small_study_effects_request(model, request):
    """Execute the dedicated immutable small-study effects request boundary."""
    from rc_metastudio.publication_bias import execute_small_study_effects

    return execute_small_study_effects(model, request)


def _conversion_kwargs(
    selected_covariates: Sequence[analysis_dataset.Covariate],
) -> dict[str, object]:
    if not selected_covariates:
        return {}
    return {"covs_to_include": selected_covariates}


def execute_meta_regression_request(
    model: MetaRegressionModel,
    studies: Sequence[analysis_dataset.Study],
    selected_covariates: Sequence[analysis_dataset.Covariate],
    request: AnalysisRequest,
    fixed_effects: bool,
    default_confidence_level: object,
) -> AnalysisResult:
    """Convert the dataset and execute one frozen meta-regression request."""
    conversion_kwargs = {
        "covs_to_include": selected_covariates,
        "studies": studies,
    }
    if request.data_type == "diagnostic":
        r_bridge.dataset_to_simple_diagnostic_r_object(
            model, metric=request.metric, **conversion_kwargs
        )
    elif request.data_type == "continuous":
        r_bridge.dataset_to_simple_continuous_r_object(model, **conversion_kwargs)
    elif request.data_type == "binary":
        r_bridge.dataset_to_simple_binary_r_object(
            model, include_raw_data=False, **conversion_kwargs
        )
    else:
        raise ValueError(
            "Unsupported meta-regression data family: %s" % request.data_type
        )
    parameters = request.parameter_values()
    return _typed_result(
        r_bridge.run_meta_regression(
            model.dataset,
            list(studies),
            list(selected_covariates),
            request.metric,
            fixed_effects=fixed_effects,
            confidence_level=parameters.get("conf.level", default_confidence_level),
            params=parameters,
            method=request.method,
        )
    )


def _run_diagnostic_backend(workflow, method_names, parameter_values):
    requests = [
        {
            "version": 1,
            "request.version": 1,
            "data.type": "diagnostic",
            "workflow": workflow,
            "method": method,
            "params": params,
            "parameters": params,
        }
        for method, params in zip(method_names, parameter_values, strict=True)
    ]
    return r_bridge.run_versioned_analysis_requests(requests)


def _run_binary_request(request):
    return r_bridge.run_versioned_analysis_request(request.to_mapping())


def _run_continuous_request(request):
    return r_bridge.run_versioned_analysis_request(request.to_mapping())


def _diagnostic_direct_effects_need_metric_specific_data(model, requests):
    if model.included_studies_have_raw_data():
        return False

    joint_methods = [request for request in requests if request.method == "diagnostic.reitsma"]
    if joint_methods:
        raise ValueError(
            "Reitsma bivariate model requires complete TP/FN/FP/TN counts; "
            "entered diagnostic effects cannot be used for this method."
        )

    missing_metrics = [
        request.metric
        for request in requests
        if not model.included_studies_have_point_estimates(effect=request.metric)
    ]
    if missing_metrics:
        raise ValueError(
            "Diagnostic analysis requires complete TP/FN/FP/TN counts or "
            "complete entered effect estimates and confidence intervals for "
            "each selected metric. Missing entered estimates for: %s."
            % ", ".join(missing_metrics)
        )

    return True


def _run_diagnostic_analysis_isolating_metric_failures(model, requests):
    if _diagnostic_direct_effects_need_metric_specific_data(model, requests):
        return _run_diagnostic_with_metric_specific_data(model, requests)

    r_bridge.dataset_to_simple_diagnostic_r_object(model)
    try:
        method_names = [request.method for request in requests]
        parameter_values = [request.parameter_values() for request in requests]
        workflow = requests[0].workflow
        return _typed_result(
            _run_diagnostic_backend(workflow, method_names, parameter_values)
        )
    except DiagnosticExecutionError:
        return _run_diagnostic_with_shared_data_per_metric(requests)


def _run_diagnostic_with_shared_data_per_metric(requests):
    return _run_diagnostic_methods_per_metric(
        requests,
        lambda request: _run_diagnostic_backend(
            request.workflow, [request.method], [request.parameter_values()]
        ),
    )


def _run_diagnostic_with_metric_specific_data(model, requests):
    def run_metric(request):
        r_bridge.dataset_to_simple_diagnostic_r_object(model, metric=request.metric)
        return _run_diagnostic_backend(
            request.workflow, [request.method], [request.parameter_values()]
        )

    return _run_diagnostic_methods_per_metric(requests, run_metric)


def _run_diagnostic_methods_per_metric(requests, run_metric):
    merged_result = _empty_diagnostic_result()
    failures = []
    for request in requests:
        metric = request.metric
        try:
            metric_result = _typed_result(run_metric(request))
        except DiagnosticExecutionError as e:
            failures.append((metric, e))
            cast(dict[str, str], merged_result["texts"])["%s Error" % metric] = str(e)
        else:
            _merge_diagnostic_result(merged_result, metric_result)

    if failures and not _diagnostic_result_has_successes(_typed_result(merged_result)):
        raise RuntimeError(_format_diagnostic_failures(failures))

    if not merged_result["image_order"]:
        merged_result["image_order"] = None
    return _typed_result(merged_result)


def _empty_diagnostic_result() -> dict[str, object]:
    return {
        "texts": {},
        "images": {},
        "display_images": {},
        "image_var_names": {},
        "image_params_paths": {},
        "plot_capabilities": {},
        "image_order": [],
    }


def _merge_diagnostic_result(
    merged_result: dict[str, object], metric_result: AnalysisResult
) -> None:
    # References are a result-level collection rather than a metric-specific
    # section.  A plain mapping update would silently discard citations from
    # every metric except the last successful one.  Merge them first, keeping
    # producer order and the existing reference formatter's de-duplication
    # rules; the remaining keyed sections are intentionally metric-scoped.
    merged_texts = cast(dict[str, str], merged_result["texts"])
    metric_texts = cast(Mapping[str, str], metric_result.get("texts", {}))
    merged_references = _merge_reference_texts(
        merged_texts.get("References"), metric_texts.get("References")
    )
    if merged_references:
        merged_texts["References"] = merged_references

    for key in (
        "texts",
        "images",
        "display_images",
        "image_var_names",
        "image_params_paths",
        "plot_capabilities",
    ):
        if key == "texts":
            merged_texts.update(
                {
                    name: value
                    for name, value in metric_texts.items()
                    if name != "References"
                }
            )
        else:
            cast(dict[str, object], merged_result[key]).update(
                cast(Mapping[str, object], metric_result.get(key, {}))
            )

    image_order = cast(Sequence[str] | None, metric_result.get("image_order"))
    if image_order:
        merged_order = cast(list[str] | None, merged_result["image_order"])
        if merged_order is None:
            merged_result["image_order"] = list(image_order)
        else:
            merged_order.extend(image_order)


def _diagnostic_result_has_successes(result: AnalysisResult) -> bool:
    return bool(
        result["images"] or any(not key.endswith(" Error") for key in result["texts"])
    )


def _format_diagnostic_failures(failures):
    return "\n".join("%s failed: %s" % (metric, error) for metric, error in failures)


def _merge_reference_texts(existing, incoming):
    """Combine already-formatted reference sections without losing citations."""
    references = _reference_entries(existing) + _reference_entries(incoming)
    if not references:
        return ""
    return result_sections.format_references(
        result_sections.dedupe_references_preserving_order(references)
    )


def _reference_entries(value):
    if not value:
        return []
    if not isinstance(value, str):
        return [str(value)]
    entries = []
    for line in value.splitlines():
        line = line.strip()
        if not line:
            continue
        # parse_out_results numbers references for display.  Remove that
        # presentation detail before applying stable de-duplication.
        if ". " in line and line.split(". ", 1)[0].isdigit():
            line = line.split(". ", 1)[1]
        entries.append(line)
    return entries
