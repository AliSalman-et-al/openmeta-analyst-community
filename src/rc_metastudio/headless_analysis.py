import os

from rc_metastudio import dataset_table_model
from rc_metastudio import analysis_dataset
from rc_metastudio import meta_globals
from rc_metastudio import analysis_adapter
from rc_metastudio import project_adapter
from rc_metastudio import project_format
from rc_metastudio import settings


class HeadlessAnalysisCase:
    def __init__(
        self,
        dataset_path,
        method,
        parameters,
        metric=None,
        data_type=None,
        analysis_type=None,
        covariates=None,
    ):
        self.dataset_path = dataset_path
        self.method = method
        self.parameters = parameters
        self.metric = metric
        self.data_type = data_type
        self.analysis_type = analysis_type
        self.covariates = covariates or []


def load_dataset_model(dataset_path):
    dataset_path = os.path.abspath(dataset_path)
    document = project_format.load_project(dataset_path)
    runtime_project = project_adapter.document_to_runtime_project(document)
    model = dataset_table_model.DatasetTableModel(
        dataset=runtime_project.dataset, add_blank_study=False
    )
    model.set_state(runtime_project.model_state)
    return model


def _add_case_covariates(model, covariates):
    for covariate in covariates:
        model.dataset.add_covariate(
            analysis_dataset.Covariate(covariate["name"], covariate["type"]),
            covariate["values"],
        )


def _analysis_metric(case_metric, parameters, fallback=None):
    for metric in (case_metric, parameters.get("measure"), fallback):
        if isinstance(metric, str) and metric.strip():
            return metric
    raise ValueError("metric must be a non-empty string")


def run_headless_analysis(case):
    model = load_dataset_model(case.dataset_path)
    _add_case_covariates(model, case.covariates)
    selected_covariates = [
        analysis_dataset.Covariate(covariate["name"], covariate["type"])
        for covariate in case.covariates
    ]
    settings.make_r_tmp()
    data_type = (
        case.data_type
        if case.data_type is not None
        else model.get_current_outcome_type(get_str=False)
    )
    family = {
        meta_globals.BINARY: "binary",
        meta_globals.CONTINUOUS: "continuous",
        meta_globals.DIAGNOSTIC: "diagnostic",
    }.get(data_type)
    if family is None:
        raise ValueError(
            "Headless harness only covers binary, continuous, and diagnostic analyses."
        )

    if family == "diagnostic":
        workflow = case.analysis_type or "standard"
        if workflow == "meta_regression":
            workflow = "meta-regression"
        if workflow == "meta-regression":
            method = case.method or "diagnostic.reitsma"
            if isinstance(method, list):
                if len(method) != 1:
                    raise ValueError(
                        "Diagnostic meta-regression requires exactly one method."
                    )
                method = method[0]
            metric = _analysis_metric(case.metric, case.parameters)
            effective_parameters = dict(case.parameters)
            effective_parameters["measure"] = metric
            request = analysis_adapter.make_analysis_request(
                data_type=family,
                workflow=workflow,
                method=method,
                metric=metric,
                parameters=effective_parameters,
            )
            study_selection = analysis_adapter.select_studies_for_covariates(
                model, tuple(selected_covariates)
            )
            return analysis_adapter.execute_meta_regression_request(
                model,
                study_selection.studies,
                tuple(selected_covariates),
                request,
                False,
                effective_parameters.get("conf.level", 95),
            )
        if case.metric is not None:
            model.set_current_metric(case.metric)
        methods = case.method if isinstance(case.method, list) else [case.method]
        parameter_values = (
            case.parameters if isinstance(case.parameters, list) else [case.parameters]
        )
        if len(methods) != len(parameter_values):
            raise ValueError(
                "Diagnostic methods and parameter sets must have equal lengths."
            )
        requests = []
        for method, params in zip(methods, parameter_values):
            metric = _analysis_metric(case.metric, params)
            effective_parameters = dict(params)
            effective_parameters["measure"] = metric
            requests.append(
                analysis_adapter.make_analysis_request(
                    data_type=family,
                    workflow="standard",
                    method=method,
                    metric=metric,
                    parameters=effective_parameters,
                )
            )
        return analysis_adapter.execute_analysis_requests(model, tuple(requests))

    workflow = case.analysis_type or "standard"
    if workflow == "meta_regression":
        workflow = "meta-regression"
    effective_metric = _analysis_metric(
        case.metric, case.parameters, getattr(model, "current_effect", None)
    )
    effective_parameters = dict(case.parameters)
    effective_parameters["measure"] = effective_metric
    model.set_current_metric(effective_metric)
    request = analysis_adapter.make_analysis_request(
        data_type=family,
        workflow=workflow,
        method=case.method or "meta_regression",
        metric=effective_metric,
        parameters=effective_parameters,
    )
    if workflow == "meta-regression":
        study_selection = analysis_adapter.select_studies_for_covariates(
            model, tuple(selected_covariates)
        )
        return analysis_adapter.execute_meta_regression_request(
            model,
            study_selection.studies,
            tuple(selected_covariates),
            request,
            False,
            effective_parameters.get("conf.level"),
        )
    return analysis_adapter.execute_analysis_requests(
        model, (request,), selected_covariates=tuple(selected_covariates)
    )
