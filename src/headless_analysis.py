import os

import legacy_pickle
import ma_data_table_model
import ma_dataset
import meta_globals
import meta_py_r


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


def _load_pickle(path):
    # Datasets are legacy Python-2 pickles; read them through the shared
    # project-file compatibility loader so Qt4 text values normalize at the
    # same boundary as the GUI open path.
    return legacy_pickle.load_legacy_pickle(path)


def load_dataset_model(dataset_path):
    dataset_path = os.path.abspath(dataset_path)
    dataset = _load_pickle(dataset_path)
    model = ma_data_table_model.DatasetModel(dataset=dataset, add_blank_study=False)
    state_path = dataset_path + ".state"
    if os.path.exists(state_path):
        state = _load_pickle(state_path)
    else:
        state = model.make_reasonable_stateful_dict(dataset)
    if isinstance(state.get("current_time_point"), str):
        state["current_time_point"] = dataset.outcome_names_to_follow_ups[
            state["current_outcome"]
        ].get_key(state["current_time_point"])
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
    if not os.path.exists("r_tmp"):
        os.mkdir("r_tmp")
    if case.metric is not None:
        model.set_current_metric(case.metric)
    data_type = case.data_type or model.get_current_outcome_type(get_str=False)

    if data_type == meta_globals.BINARY:
        meta_py_r.ma_dataset_to_simple_binary_robj(model, **covariate_kwargs)
        if case.analysis_type in ["cumulative", "leave-one-out"]:
            return meta_py_r.run_meta_method(
                {"cumulative": "cum.ma.binary", "leave-one-out": "loo.ma.binary"}[
                    case.analysis_type
                ],
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
            )
        if case.analysis_type == "subgroup":
            return meta_py_r.run_meta_method(
                "subgroup.ma.binary", case.method, case.parameters
            )
        return meta_py_r.run_binary_ma(case.method, case.parameters)
    if data_type == meta_globals.CONTINUOUS:
        meta_py_r.ma_dataset_to_simple_continuous_robj(model, **covariate_kwargs)
        if case.analysis_type in ["cumulative", "leave-one-out"]:
            return meta_py_r.run_meta_method(
                {
                    "cumulative": "cum.ma.continuous",
                    "leave-one-out": "loo.ma.continuous",
                }[case.analysis_type],
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
            )
        if case.analysis_type == "subgroup":
            return meta_py_r.run_meta_method(
                "subgroup.ma.continuous", case.method, case.parameters
            )
        return meta_py_r.run_continuous_ma(case.method, case.parameters)
    if data_type == meta_globals.DIAGNOSTIC:
        meta_py_r.ma_dataset_to_simple_diagnostic_robj(model)
        return meta_py_r.run_diagnostic_multi(case.method, case.parameters)
    raise ValueError(
        "Headless harness only covers binary, continuous, and diagnostic analyses."
    )
