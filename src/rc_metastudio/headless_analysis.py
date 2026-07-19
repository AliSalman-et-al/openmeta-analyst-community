import os

import ma_data_table_model
import ma_dataset
import meta_globals
from rc_metastudio import meta_py_r
import project_adapter
import project_format
import settings


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
    dataset = project_adapter.project_to_dataset(document.project)
    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=False)
    state = project_adapter.state_to_model_state(dataset, document.state)
    model.set_state(state)
    return model


def _add_case_covariates(model, covariates):
    for covariate in covariates:
        model.dataset.add_covariate(
            ma_dataset.Covariate(covariate["name"], covariate["type"]),
            covariate["values"],
        )


def run_headless_analysis(case):
    model = load_dataset_model(case.dataset_path)
    _add_case_covariates(model, case.covariates)
    selected_covariates = [
        ma_dataset.Covariate(covariate["name"], covariate["type"])
        for covariate in case.covariates
    ]
    covariate_kwargs = (
        {"covs_to_include": selected_covariates} if selected_covariates else {}
    )
    settings.make_r_tmp()
    if case.metric is not None:
        model.set_current_metric(case.metric)
    data_type = case.data_type or model.get_current_outcome_type(get_str=False)

    if data_type == meta_globals.BINARY:
        meta_py_r.ma_dataset_to_simple_binary_robj(model, **covariate_kwargs)
        if case.analysis_type in ["cumulative", "leave-one-out"]:
            return meta_py_r.run_workflow_analysis(
                case.analysis_type,
                case.method,
                case.parameters,
            )
        if case.analysis_type == "meta_regression":
            return meta_py_r.run_meta_regression(
                model.dataset,
                [],
                selected_covariates,
                case.metric,
                conf_level=case.parameters.get("conf.level"),
                params=case.parameters,
            )
        if case.analysis_type == "subgroup":
            return meta_py_r.run_workflow_analysis(
                "subgroup", case.method, case.parameters
            )
        return meta_py_r.run_binary_ma(case.method, case.parameters)
    if data_type == meta_globals.CONTINUOUS:
        meta_py_r.ma_dataset_to_simple_continuous_robj(model, **covariate_kwargs)
        if case.analysis_type in ["cumulative", "leave-one-out"]:
            return meta_py_r.run_workflow_analysis(
                case.analysis_type,
                case.method,
                case.parameters,
            )
        if case.analysis_type == "meta_regression":
            return meta_py_r.run_meta_regression(
                model.dataset,
                [],
                selected_covariates,
                case.metric,
                conf_level=case.parameters.get("conf.level"),
                params=case.parameters,
            )
        if case.analysis_type == "subgroup":
            return meta_py_r.run_workflow_analysis(
                "subgroup", case.method, case.parameters
            )
        return meta_py_r.run_continuous_ma(case.method, case.parameters)
    if data_type == meta_globals.DIAGNOSTIC:
        meta_py_r.ma_dataset_to_simple_diagnostic_robj(model)
        return meta_py_r.run_diagnostic_multi(case.method, case.parameters)
    raise ValueError(
        "Headless harness only covers binary, continuous, and diagnostic analyses."
    )
