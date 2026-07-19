import json
import datetime
import hashlib
from importlib import metadata
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
import zipfile

import headless_analysis
import meta_globals
from rc_metastudio import meta_py_r
from plot_defaults import FOREST_ARM_LABELS


DEFAULT_TOLERANCES = {
    "estimate": 0.001,
    "lower_bound": 0.001,
    "upper_bound": 0.001,
    "p_value": 0.001,
    "tau_squared": 0.001,
    "q": 0.001,
    "i_squared": 0.5,
}


GOLDEN_MATRIX_SOURCE_PROJECTS = {
    "binary": "amino.rcms",
    "continuous": "continuous.rcms",
    "diagnostic": "lymph.rcms",
}

GOLDEN_MATRIX_METRICS = {
    "binary": ["OR", "RD", "RR", "AS", "YUQ", "YUY"],
    "continuous": ["MD", "SMD"],
    "diagnostic": ["Sens", "Spec", "PLR", "NLR", "DOR"],
}


RCMetaR_R_PACKAGE = "RCMetaR"


MODERN_BASELINE_ENVIRONMENT_EXPECTED = {
    "id": "rc-metastudio-python3-pyqt5-r4-RCMetaR",
    "os": "Windows",
    "python": "3.11",
    "pyqt": "5.15.11",
    "r": "R version 4.6.0",
    "rpy2": "3.6.7",
    "package": RCMetaR_R_PACKAGE,
}


def _common_plot_params(path):
    return {
        "conf.level": 95.0,
        "digits": 3.0,
        "fp_col1_str": "Study or Subgroup",
        "fp_col2_str": "[default]",
        "fp_col3_str": FOREST_ARM_LABELS[0],
        "fp_col4_str": FOREST_ARM_LABELS[1],
        "fp_xlabel": "[default]",
        "fp_outpath": path,
        "fp_plot_lb": "[default]",
        "fp_plot_ub": "[default]",
        "fp_show_col1": True,
        "fp_show_col2": True,
        "fp_show_col3": True,
        "fp_show_col4": True,
        "fp_show_summary_line": True,
        "fp_xticks": "[default]",
    }


def _analysis_output_path(filename):
    import settings

    return settings.analysis_output_path(filename)


def golden_coverage_matrix(root_dir=None, method_discoverer=None):
    root_dir = os.path.abspath(
        root_dir or os.path.join(os.path.dirname(__file__), "..")
    )
    if method_discoverer is None:
        meta_py_r.RlibLoader().load_RCMetaR()
        method_discoverer = lambda data_family, dataset, metric: (
            discover_reference_methods(root_dir, data_family, dataset, metric)
        )

    rows = []
    omissions = _golden_matrix_omissions()
    for data_family in ["binary", "continuous", "diagnostic"]:
        dataset = GOLDEN_MATRIX_SOURCE_PROJECTS[data_family]
        for metric in GOLDEN_MATRIX_METRICS[data_family]:
            methods = _discover_or_omit(
                method_discoverer, omissions, data_family, dataset, metric
            )
            workflows = (
                ["standard"]
                if data_family == "diagnostic"
                else ["standard", "cumulative", "leave-one-out"]
            )
            for workflow in workflows:
                rows.append(
                    _coverage_row(
                        data_family,
                        workflow,
                        dataset,
                        metric,
                        methods,
                        ["headless", "gui"] if workflow == "standard" else ["headless"],
                    )
                )

    rows.extend(
        [
            _coverage_row(
                "binary",
                "meta-regression",
                "amino.rcms",
                "OR",
                {"Random": "binary.random"},
                ["headless", "gui"],
            ),
            _coverage_row(
                "continuous",
                "meta-regression",
                "continuous.rcms",
                "SMD",
                {"Random": "continuous.random"},
                ["headless", "gui"],
            ),
            _coverage_row(
                "binary",
                "subgroup",
                "amino.rcms",
                "OR",
                {"Random": "binary.random"},
                ["headless", "gui"],
            ),
            _coverage_row(
                "continuous",
                "subgroup",
                "continuous.rcms",
                "SMD",
                {"Random": "continuous.random"},
                ["headless", "gui"],
            ),
            _coverage_row(
                "diagnostic",
                "diagnostic-multi-metric",
                "lymph.rcms",
                "Sens-Spec",
                _discover_or_omit(
                    method_discoverer, omissions, "diagnostic", "lymph.rcms", "Sens"
                ),
                ["headless", "gui"],
            ),
            _coverage_row(
                "diagnostic",
                "diagnostic-multi-metric",
                "lymph.rcms",
                "PLR-NLR-DOR",
                _discover_or_omit(
                    method_discoverer, omissions, "diagnostic", "lymph.rcms", "DOR"
                ),
                ["headless", "gui"],
            ),
            _coverage_row(
                "binary",
                "csv-created-project",
                "csv-import",
                "OR",
                {"Random": "binary.random"},
                ["headless", "gui"],
            ),
        ]
    )
    return {"matrix": "golden-coverage", "rows": rows, "omissions": omissions}


def write_golden_coverage_matrix(report_path, root_dir=None, method_discoverer=None):
    report_path = os.path.abspath(report_path)
    matrix = golden_coverage_matrix(
        root_dir=root_dir, method_discoverer=method_discoverer
    )
    with open(report_path, "w") as f:
        json.dump(matrix, f, indent=2, sort_keys=True)
    return matrix


def comprehensive_golden_baseline_manifest(root_dir=None, timestamp=None):
    captured_at = (
        timestamp
        or datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {
        "baseline": "comprehensive-golden",
        "captured_at": captured_at,
        "coverage_matrix": "docs/verification/golden-coverage-matrix.md",
        "coverage_manifest": "docs/verification/golden-coverage-manifest.json",
        "schema": "docs/verification/golden-baseline.schema.json",
        "curated_golden_set": [
            bundle["id"] for bundle in curated_golden_bundles(root_dir)
        ],
        "artifact_bundle": {
            "path": "artifacts/golden-baseline/comprehensive-golden-baseline.zip",
            "storage": "ignored-local-or-ci-release-artifact",
        },
        "capture_metadata": {
            "required_fields": [
                "python",
                "os",
                "r",
                "rpy2",
                "pyqt",
                "package_versions",
                "commit_sha",
                "capture_mode",
                "capture_command",
                "baseline_environment",
                "authoritative",
                "authority",
            ],
            "local_default_capture_mode": "local-debug",
            "authoritative_capture_mode": "authoritative",
            "authority_values": ["authoritative", "local-debug"],
            "baseline": "rc-metastudio-behavior",
            "baseline_environment": dict(MODERN_BASELINE_ENVIRONMENT_EXPECTED),
            "authoritative_requires_baseline_environment_match": True,
        },
        "bundle_contents": [
            "capture",
            "texts",
            "artifacts",
            "plot-similarity-metadata",
            "omissions",
        ],
    }


def write_comprehensive_golden_baseline_manifest(report_path, root_dir=None):
    report_path = os.path.abspath(report_path)
    manifest = comprehensive_golden_baseline_manifest(root_dir=root_dir)
    with open(report_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def discover_reference_methods(root_dir, data_family, dataset, metric):
    model = headless_analysis.load_dataset_model(
        os.path.join(root_dir, "sample_projects", dataset)
    )
    model.set_current_metric(metric)
    if data_family == "binary":
        meta_py_r.ma_dataset_to_simple_binary_robj(model)
    elif data_family == "continuous":
        meta_py_r.ma_dataset_to_simple_continuous_robj(model)
    elif data_family == "diagnostic":
        meta_py_r.ma_dataset_to_simple_diagnostic_robj(model)
    else:
        raise ValueError("Unknown data family: %s" % data_family)
    return meta_py_r.get_available_methods(
        for_data_type=data_family, data_obj_name="tmp_obj", metric=metric
    )


def _discover_or_omit(method_discoverer, omissions, data_family, dataset, metric):
    try:
        return method_discoverer(data_family, dataset, metric)
    except Exception as exc:
        omissions.append(
            {
                "branch": "%s %s %s methods" % (data_family, dataset, metric),
                "reason": str(exc),
                "follow_up": "Re-run method discovery in the Reference Environment.",
            }
        )
        return {}


def _coverage_row(data_family, workflow, dataset, metric, methods, capture_modes):
    method_values = sorted(set(methods.values()))
    return {
        "id": _coverage_row_id(data_family, workflow, metric),
        "data_family": data_family,
        "workflow": workflow,
        "dataset": dataset,
        "metrics": [metric],
        "methods": method_values,
        "method_classes": sorted(
            set([_method_class(method) for method in method_values])
        ),
        "capture_modes": capture_modes,
        "artifacts": _workflow_artifacts(workflow),
        "options": _workflow_options(workflow),
        "project_state": "sample_projects/%s" % dataset
        if dataset.endswith(".rcms")
        else dataset,
        "status": "included",
    }


def _coverage_row_id(data_family, workflow, metric):
    prefix = data_family + "-"
    return (
        "%s-%s" % (workflow, metric)
        if workflow.startswith(prefix)
        else "%s-%s-%s" % (data_family, workflow, metric)
    )


def _method_class(method):
    for name in ["random", "fixed", "peto", "mh", "inv.var", "bivariate", "hsroc"]:
        if name in method.lower():
            return name
    return method


def _workflow_artifacts(workflow):
    if workflow == "meta-regression":
        return ["summary", "numeric outputs", "regression plot"]
    if workflow in [
        "standard",
        "cumulative",
        "leave-one-out",
        "subgroup",
        "diagnostic-multi-metric",
        "csv-created-project",
    ]:
        return ["summary", "numeric outputs", "forest plot"]
    return ["summary", "numeric outputs"]


def _workflow_options(workflow):
    options = ["default confidence level"]
    if workflow in [
        "standard",
        "cumulative",
        "leave-one-out",
        "subgroup",
        "diagnostic-multi-metric",
        "csv-created-project",
    ]:
        options.append("default plot parameters")
    if workflow in ["meta-regression", "subgroup"]:
        options.append("covariate selection")
    if workflow == "csv-created-project":
        options.append("CSV import mapping")
    return options


def _golden_matrix_omissions():
    return [
        {
            "branch": "Network Meta-Analysis",
            "reason": "Deferred from Release Cutover by ADR 0035.",
            "follow_up": "Add a post-cutover network baseline before porting network workflows.",
        },
        {
            "branch": "Diagnostic Meta-Regression and Subgroup Analysis",
            "reason": "Not a minimum Release Cutover gate until Reference Implementation feasibility is discovered.",
            "follow_up": "Add rows if method discovery reports feasible diagnostic advanced-analysis paths.",
        },
    ]


def curated_golden_bundles(root_dir=None):
    root_dir = root_dir or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    sample = lambda name: os.path.join(root_dir, "sample_projects", name)
    binary_params = dict(
        _common_plot_params(_analysis_output_path("golden_amino_forest.png")),
        **{
            "measure": "OR",
            "rm.method": "DL",
            "to": "only0",
            "adjust": 0.5,
        },
    )
    continuous_params = dict(
        _common_plot_params(_analysis_output_path("golden_continuous_forest.png")),
        **{
            "fp_show_col3": False,
            "fp_show_col4": False,
            "measure": "SMD",
            "rm.method": "DL",
        },
    )
    diagnostic_params = dict(
        _common_plot_params(_analysis_output_path("golden_lymph_forest_dor.png")),
        **{
            "fp_col3_str": "[default]",
            "fp_show_col4": False,
            "measure": "DOR",
            "rm.method": "DL",
            "to": "only0",
            "adjust": 0.5,
        },
    )
    regression_path = _analysis_output_path("reg.png")
    regression_display_path = _analysis_output_path("reg.display.svg")
    binary_regression_params = {
        "conf.level": 95.0,
        "bp_outpath": regression_path,
        "bp_display_path": regression_display_path,
    }
    continuous_regression_params = dict(binary_regression_params)
    binary_subgroup_params = dict(
        binary_params,
        **{
            "cov_name": "golden_group",
            "fp_outpath": _analysis_output_path("golden_amino_subgroup_forest.png"),
        },
    )
    continuous_subgroup_params = dict(
        continuous_params,
        **{
            "cov_name": "golden_group",
            "fp_outpath": _analysis_output_path(
                "golden_continuous_subgroup_forest.png"
            ),
        },
    )
    binary_cumulative_params = dict(
        binary_params,
        **{"fp_outpath": _analysis_output_path("golden_amino_cumulative_forest.png")},
    )
    binary_loo_params = dict(
        binary_params,
        **{"fp_outpath": _analysis_output_path("golden_amino_loo_forest.png")},
    )
    continuous_cumulative_params = dict(
        continuous_params,
        **{
            "fp_outpath": _analysis_output_path(
                "golden_continuous_cumulative_forest.png"
            )
        },
    )
    continuous_loo_params = dict(
        continuous_params,
        **{"fp_outpath": _analysis_output_path("golden_continuous_loo_forest.png")},
    )
    for plot_params in (
        binary_params,
        continuous_params,
        diagnostic_params,
        binary_subgroup_params,
        continuous_subgroup_params,
        binary_cumulative_params,
        binary_loo_params,
        continuous_cumulative_params,
        continuous_loo_params,
    ):
        root, _extension = os.path.splitext(str(plot_params["fp_outpath"]))
        plot_params["fp_display_path"] = root + ".display.svg"
    amino_group = dict(
        (name, "early" if i % 2 == 0 else "late")
        for i, name in enumerate(
            [
                "Gonzalez",
                "Prins",
                "Giamarellou",
                "Maller",
                "Sturm",
                "Marik",
                "Muijsken",
                "Vigano",
                "Hansen",
                "De Vries",
                "Mauracher",
                "Nordstrom",
                "Rozdzinski",
                "Ter Braak",
                "Tulkens",
                "Van der Auwera",
                "Klastersky",
                "Vanhaeverbeek",
                "Hollender",
            ]
        )
    )
    continuous_group = dict(
        (name, "early" if i % 2 == 0 else "late")
        for i, name in enumerate(
            ["Carroll", "Grant", "Peck", "Donat", "Stewart", "Young"]
        )
    )
    amino_year = dict((name, 1980 + i) for i, name in enumerate(amino_group.keys()))
    continuous_year = dict(
        (name, 1990 + i) for i, name in enumerate(continuous_group.keys())
    )
    return [
        {
            "id": "amino-binary-random",
            "dataset": "amino.rcms",
            "data_family": "binary",
            "method": "binary.random",
            "metric": "OR",
            "parameters": binary_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {
                "Summary": {
                    "estimate": 0.770,
                    "lower_bound": 0.485,
                    "upper_bound": 1.222,
                    "p_value": 0.267,
                    "tau_squared": 0.378,
                    "q": 33.360,
                    "i_squared": 46.0,
                }
            },
            "artifacts": {"Forest Plot": binary_params["fp_outpath"]},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("amino.rcms"),
                "binary.random",
                binary_params,
                metric="OR",
                data_type=meta_globals.BINARY,
            ),
        },
        {
            "id": "continuous-random",
            "dataset": "continuous.rcms",
            "data_family": "continuous",
            "method": "continuous.random",
            "metric": "SMD",
            "parameters": continuous_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {
                "Summary": {
                    "estimate": 0.358,
                    "lower_bound": 0.152,
                    "upper_bound": 0.565,
                    "p_value": 0.001,
                    "tau_squared": 0.037,
                    "q": 11.914,
                    "i_squared": 58.0,
                }
            },
            "artifacts": {"Forest Plot": continuous_params["fp_outpath"]},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("continuous.rcms"),
                "continuous.random",
                continuous_params,
                metric="SMD",
                data_type=meta_globals.CONTINUOUS,
            ),
        },
        {
            "id": "lymph-diagnostic-random-dor",
            "dataset": "lymph.rcms",
            "data_family": "diagnostic",
            "method": ["diagnostic.random"],
            "metric": "DOR",
            "parameters": [diagnostic_params],
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {
                "Odds Ratio Summary": {
                    "estimate": 9.648,
                    "lower_bound": 5.529,
                    "upper_bound": 16.835,
                    "p_value": 0.001,
                    "tau_squared": 0.704,
                    "q": 42.259,
                    "i_squared": 62.0,
                }
            },
            "artifacts": {"Odds Ratio Forest Plot": diagnostic_params["fp_outpath"]},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("lymph.rcms"),
                ["diagnostic.random"],
                [diagnostic_params],
                data_type=meta_globals.DIAGNOSTIC,
            ),
        },
        {
            "id": "amino-binary-cumulative",
            "dataset": "amino.rcms",
            "data_family": "binary",
            "method": "binary.random",
            "metric": "OR",
            "parameters": binary_cumulative_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Cumulative Summary": {}},
            "artifacts": {
                "Cumulative Forest Plot": binary_cumulative_params["fp_outpath"]
            },
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("amino.rcms"),
                "binary.random",
                binary_cumulative_params,
                metric="OR",
                data_type=meta_globals.BINARY,
                analysis_type="cumulative",
            ),
        },
        {
            "id": "amino-binary-leave-one-out",
            "dataset": "amino.rcms",
            "data_family": "binary",
            "method": "binary.random",
            "metric": "OR",
            "parameters": binary_loo_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Leave-one-out Summary": {}},
            "artifacts": {"Leave-one-out Forest plot": binary_loo_params["fp_outpath"]},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("amino.rcms"),
                "binary.random",
                binary_loo_params,
                metric="OR",
                data_type=meta_globals.BINARY,
                analysis_type="leave-one-out",
            ),
        },
        {
            "id": "continuous-cumulative",
            "dataset": "continuous.rcms",
            "data_family": "continuous",
            "method": "continuous.random",
            "metric": "SMD",
            "parameters": continuous_cumulative_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Cumulative Summary": {}},
            "artifacts": {
                "Cumulative Forest Plot": continuous_cumulative_params["fp_outpath"]
            },
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("continuous.rcms"),
                "continuous.random",
                continuous_cumulative_params,
                metric="SMD",
                data_type=meta_globals.CONTINUOUS,
                analysis_type="cumulative",
            ),
        },
        {
            "id": "continuous-leave-one-out",
            "dataset": "continuous.rcms",
            "data_family": "continuous",
            "method": "continuous.random",
            "metric": "SMD",
            "parameters": continuous_loo_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Leave-one-out Summary": {}},
            "artifacts": {
                "Leave-one-out Forest plot": continuous_loo_params["fp_outpath"]
            },
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("continuous.rcms"),
                "continuous.random",
                continuous_loo_params,
                metric="SMD",
                data_type=meta_globals.CONTINUOUS,
                analysis_type="leave-one-out",
            ),
        },
        {
            "id": "amino-binary-meta-regression",
            "dataset": "amino.rcms",
            "data_family": "binary",
            "method": "meta_regression",
            "metric": "OR",
            "parameters": binary_regression_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Summary": {}},
            "artifacts": {"Regression Plot": _analysis_output_path("reg.png")},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("amino.rcms"),
                None,
                binary_regression_params,
                metric="OR",
                data_type=meta_globals.BINARY,
                analysis_type="meta_regression",
                covariates=[
                    {"name": "golden_year", "type": "continuous", "values": amino_year}
                ],
            ),
        },
        {
            "id": "continuous-meta-regression",
            "dataset": "continuous.rcms",
            "data_family": "continuous",
            "method": "meta_regression",
            "metric": "SMD",
            "parameters": continuous_regression_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Summary": {}},
            "artifacts": {"Regression Plot": _analysis_output_path("reg.png")},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("continuous.rcms"),
                None,
                continuous_regression_params,
                metric="SMD",
                data_type=meta_globals.CONTINUOUS,
                analysis_type="meta_regression",
                covariates=[
                    {
                        "name": "golden_year",
                        "type": "continuous",
                        "values": continuous_year,
                    }
                ],
            ),
        },
        {
            "id": "amino-binary-subgroup",
            "dataset": "amino.rcms",
            "data_family": "binary",
            "method": "binary.random",
            "metric": "OR",
            "parameters": binary_subgroup_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Subgroup Summary": {}},
            "artifacts": {"Subgroup Forest Plot": binary_subgroup_params["fp_outpath"]},
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("amino.rcms"),
                "binary.random",
                binary_subgroup_params,
                metric="OR",
                data_type=meta_globals.BINARY,
                analysis_type="subgroup",
                covariates=[
                    {"name": "golden_group", "type": "factor", "values": amino_group}
                ],
            ),
        },
        {
            "id": "continuous-subgroup",
            "dataset": "continuous.rcms",
            "data_family": "continuous",
            "method": "continuous.random",
            "metric": "SMD",
            "parameters": continuous_subgroup_params,
            "tolerances": DEFAULT_TOLERANCES,
            "expected": {"Subgroup Summary": {}},
            "artifacts": {
                "Subgroups Forest Plot": continuous_subgroup_params["fp_outpath"]
            },
            "case": headless_analysis.HeadlessAnalysisCase(
                sample("continuous.rcms"),
                "continuous.random",
                continuous_subgroup_params,
                metric="SMD",
                data_type=meta_globals.CONTINUOUS,
                analysis_type="subgroup",
                covariates=[
                    {
                        "name": "golden_group",
                        "type": "factor",
                        "values": continuous_group,
                    }
                ],
            ),
        },
    ]


def parsed_numeric_sections(result):
    parsed = {}
    for name, text in result.get("texts", {}).items():
        values = _parse_summary(text)
        values.update(_parse_result_table(text))
        values.update(_parse_weights(text))
        if values:
            parsed[name] = values
    return parsed


def compare_bundle(bundle, result):
    actual = parsed_numeric_sections(result)
    comparisons = []
    for section, expected_values in bundle["expected"].items():
        if not expected_values:
            comparisons.append(
                {
                    "section": section,
                    "metric": "text_present",
                    "expected": True,
                    "observed": section in result.get("texts", {}),
                    "tolerance": None,
                    "drift": None,
                    "passed": section in result.get("texts", {}),
                }
            )
        for metric, expected in expected_values.items():
            observed = actual.get(section, {}).get(metric)
            drift = None if observed is None else abs(observed - expected)
            tolerance = bundle["tolerances"][metric]
            comparisons.append(
                {
                    "section": section,
                    "metric": metric,
                    "expected": expected,
                    "observed": observed,
                    "tolerance": tolerance,
                    "drift": drift,
                    "passed": drift is not None and drift <= tolerance,
                }
            )
    comparisons.extend(_compare_artifacts(bundle, result))
    return comparisons


def _compare_artifacts(bundle, result):
    comparisons = []
    images = result.get("images", {})
    for label in sorted(bundle.get("artifacts", {})):
        image_label = _matching_key(images, label)
        path = images.get(image_label) if image_label is not None else None
        present = bool(path and os.path.exists(path))
        comparisons.append(
            {
                "section": label,
                "metric": "artifact_present",
                "expected": True,
                "observed": present,
                "tolerance": None,
                "drift": None,
                "passed": present,
            }
        )
    return comparisons


def _matching_key(mapping, expected):
    if expected in mapping:
        return expected
    expected_normalized = expected.lower()
    for key in mapping:
        if key.lower() == expected_normalized:
            return key
    return None


def run_curated_golden_set(report_path=None):
    meta_py_r.RlibLoader().load_RCMetaR()
    reports = []
    for bundle in curated_golden_bundles():
        result = headless_analysis.run_headless_analysis(bundle["case"])
        reports.append(
            {
                "id": bundle["id"],
                "dataset": bundle["dataset"],
                "method": bundle["method"],
                "metric": bundle["metric"],
                "parameters": bundle["parameters"],
                "tolerances": bundle["tolerances"],
                "artifacts": result.get("images", {}),
                "comparisons": compare_bundle(bundle, result),
            }
        )
    report = {
        "golden_set": "curated",
        "results": reports,
        "passed": all(c["passed"] for r in reports for c in r["comparisons"]),
    }
    if report_path:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, sort_keys=True)
    return report


def capture_bundle(
    bundle,
    runner=None,
    timestamp=None,
    capture_mode=None,
    capture_command=None,
    baseline_environment=None,
    reference_environment=None,
):
    runner = runner or headless_analysis.run_headless_analysis
    captured_at = (
        timestamp
        or datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    capture_mode = capture_mode or os.environ.get(
        "RCMS_GOLDEN_CAPTURE_MODE", "local-debug"
    )
    capture_command = (
        capture_command
        or os.environ.get("RCMS_GOLDEN_CAPTURE_COMMAND")
        or _capture_command()
    )
    tool_versions = _tool_versions()
    baseline_environment = _baseline_environment(
        baseline_environment or reference_environment, tool_versions
    )
    authoritative = (
        capture_mode == "authoritative" and baseline_environment["matches_expected"]
    )
    base = {
        "id": bundle["id"],
        "dataset": bundle["dataset"],
        "data_family": bundle["data_family"],
        "method": bundle["method"],
        "metric": bundle["metric"],
        "parameters": bundle["parameters"],
        "captured_at": captured_at,
        "tool_versions": tool_versions,
        "package_versions": _package_versions(tool_versions),
        "commit_sha": _commit_sha(),
        "capture_mode": capture_mode,
        "capture_command": capture_command,
        "baseline_environment": baseline_environment,
        "authoritative": authoritative,
        "authority": "authoritative" if authoritative else "local-debug",
    }
    try:
        result = runner(bundle["case"])
        base.update(
            {
                "status": "success",
                "outputs": parsed_numeric_sections(result),
                "texts": result.get("texts", {}),
                "artifacts": _capture_artifacts(bundle, result),
                "plot_descriptors": _capture_plot_descriptors(bundle, result),
            }
        )
    except Exception as exc:
        base.update(
            {
                "status": "failure",
                "failure": {"type": exc.__class__.__name__, "message": str(exc)},
                "traceback": traceback.format_exc(),
            }
        )
    return base


def capture_curated_binary_bundle(report_path=None):
    meta_py_r.RlibLoader().load_RCMetaR()
    capture = capture_bundle(curated_golden_bundles()[0])
    if report_path:
        with open(report_path, "w") as f:
            json.dump(capture, f, indent=2, sort_keys=True)
    return capture


def capture_comprehensive_golden_baseline(
    output_dir=None,
    runner=None,
    timestamp=None,
    capture_mode=None,
    capture_command=None,
    baseline_environment=None,
    reference_environment=None,
    root_dir=None,
):
    output_dir = os.path.abspath(
        output_dir
        or os.path.join(os.path.dirname(__file__), "..", "artifacts", "golden-baseline")
    )
    captures_dir = os.path.join(output_dir, "captures")
    artifacts_dir = os.path.join(output_dir, "artifacts")
    _ensure_dir(captures_dir)
    _ensure_dir(artifacts_dir)

    meta_py_r.RlibLoader().load_RCMetaR()
    rows = []
    for bundle in curated_golden_bundles(root_dir):
        capture = capture_bundle(
            bundle,
            runner=runner,
            timestamp=timestamp,
            capture_mode=capture_mode,
            capture_command=capture_command,
            baseline_environment=baseline_environment or reference_environment,
        )
        _preserve_capture_artifacts(capture, bundle["id"], artifacts_dir)
        rows.append(capture)
        _write_json(os.path.join(captures_dir, "%s.json" % bundle["id"]), capture)

    manifest = comprehensive_golden_baseline_manifest(
        root_dir=root_dir, timestamp=timestamp
    )
    manifest.update(
        {
            "curated_golden_set": rows,
            "passed": all(row.get("status") == "success" for row in rows),
            "capture_failures": [
                row["id"] for row in rows if row.get("status") == "failure"
            ],
        }
    )
    _write_json(os.path.join(output_dir, "manifest.json"), manifest)
    archive_path = os.path.join(output_dir, "comprehensive-golden-baseline.zip")
    _zip_directory(output_dir, archive_path)
    manifest["artifact_bundle"]["path"] = _normalize_path(archive_path)
    _write_json(os.path.join(output_dir, "manifest.json"), manifest)
    return manifest


def _capture_artifacts(bundle, result):
    images = result.get("images", {})
    artifacts = []
    for label, expected_path in sorted(bundle.get("artifacts", {}).items()):
        path = images.get(label, expected_path)
        artifacts.append(
            {
                "label": label,
                "path": _normalize_path(path),
                "sha256": _sha256(path) if path and os.path.exists(path) else None,
            }
        )
    return artifacts


def _capture_plot_descriptors(bundle, result):
    displays = result.get("display_images", {})
    capabilities = result.get("plot_capabilities", {})
    descriptors = []
    for label in sorted(bundle.get("artifacts", {})):
        display_label = _matching_key(displays, label)
        display_path = displays.get(display_label) if display_label is not None else None
        capability_label = _matching_key(capabilities, label)
        capability = (
            capabilities.get(capability_label, {})
            if capability_label is not None
            else {}
        )
        descriptors.append(
            {
                "artifact_label": label,
                "display": {
                    "identity": display_label,
                    "name": os.path.basename(display_path) if display_path else None,
                    "type": (
                        os.path.splitext(display_path)[1].lower().lstrip(".")
                        if display_path
                        else None
                    ),
                    "sha256": (
                        _sha256(display_path)
                        if display_path and os.path.exists(display_path)
                        else None
                    ),
                },
                "capability": {
                    "kind": capability.get("plot_kind"),
                    "editable": capability.get("editable"),
                    "styleable": capability.get("styleable"),
                    "composition": capability.get("composition"),
                    "regeneration": capability.get("regenerator"),
                },
            }
        )
    return descriptors


def _preserve_capture_artifacts(capture, bundle_id, artifacts_dir):
    bundle_dir = os.path.join(artifacts_dir, bundle_id)
    _ensure_dir(bundle_dir)
    for artifact in capture.get("artifacts", []):
        source = artifact.get("path")
        if not source or not os.path.exists(source):
            continue
        target = os.path.join(bundle_dir, os.path.basename(source))
        shutil.copy2(source, target)
        artifact["bundle_path"] = _normalize_path(target)
        artifact["sha256"] = _sha256(target)


def _write_json(path, data):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _ensure_dir(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _zip_directory(source_dir, archive_path):
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for dirpath, _dirnames, filenames in os.walk(source_dir):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                if os.path.abspath(path) == os.path.abspath(archive_path):
                    continue
                archive.write(path, _normalize_path(os.path.relpath(path, source_dir)))


def _normalize_path(path):
    return path.replace("\\", "/")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tool_versions():
    versions = {
        "rc_metastudio": str(meta_globals.VERSION),
        "python": sys.version.split()[0],
        "os": platform.system(),
        "platform": platform.platform(),
    }
    try:
        versions["r"] = meta_py_r.get_r_version_string()
    except Exception:
        versions["r"] = None
    for distribution in ("rpy2", "rpy2-rinterface", "rpy2-robjects"):
        try:
            versions[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            versions[distribution] = None
    versions["pyqt"] = _pyqt_version()
    return versions


def _pyqt_version():
    try:
        from PyQt6 import QtCore

        return getattr(QtCore, "PYQT_VERSION_STR", None)
    except Exception:
        pass
    return None


def _package_versions(tool_versions):
    return {
        "rc_metastudio": tool_versions.get("rc_metastudio"),
        "r": tool_versions.get("r"),
        "rpy2": tool_versions.get("rpy2"),
        "rpy2-rinterface": tool_versions.get("rpy2-rinterface"),
        "rpy2-robjects": tool_versions.get("rpy2-robjects"),
        "pyqt": tool_versions.get("pyqt"),
        "RCMetaR": _r_package_version(RCMetaR_R_PACKAGE),
    }


def _r_package_version(package_name):
    try:
        return meta_py_r.get_r_package_version(package_name)
    except Exception:
        return None


def _capture_command():
    return " ".join(sys.argv)


def _commit_sha():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        process = subprocess.Popen(
            ["git", "rev-parse", "HEAD"],
            cwd=root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _stderr = process.communicate()
        if process.returncode == 0:
            if not isinstance(stdout, str):
                stdout = stdout.decode("ascii", "replace")
            return stdout.strip()
    except Exception:
        pass
    return "unknown"


def _baseline_environment(baseline_environment, tool_versions):
    supplied = dict(baseline_environment or {})
    if not supplied:
        supplied = _baseline_environment_from_env(tool_versions)
    supplied["expected"] = dict(MODERN_BASELINE_ENVIRONMENT_EXPECTED)
    supplied["matches_expected"] = _matches_baseline_environment(supplied)
    return supplied


def _baseline_environment_from_env(tool_versions):
    return {
        "id": os.environ.get("RCMS_MODERN_BASELINE_ENVIRONMENT_ID", "local-debug"),
        "os": os.environ.get(
            "RCMS_MODERN_BASELINE_ENVIRONMENT_OS", tool_versions.get("os")
        ),
        "python": os.environ.get(
            "RCMS_MODERN_BASELINE_ENVIRONMENT_PYTHON", tool_versions.get("python")
        ),
        "pyqt": os.environ.get(
            "RCMS_MODERN_BASELINE_ENVIRONMENT_PYQT", tool_versions.get("pyqt")
        ),
        "r": os.environ.get(
            "RCMS_MODERN_BASELINE_ENVIRONMENT_R", tool_versions.get("r")
        ),
        "rpy2": os.environ.get(
            "RCMS_MODERN_BASELINE_ENVIRONMENT_RPY2", tool_versions.get("rpy2")
        ),
        "package": os.environ.get("RCMS_MODERN_BASELINE_PACKAGE", RCMetaR_R_PACKAGE),
    }


def _matches_baseline_environment(baseline_environment):
    for key, expected in MODERN_BASELINE_ENVIRONMENT_EXPECTED.items():
        observed = baseline_environment.get(key)
        if key in {"python", "r"}:
            if not str(observed or "").startswith(expected):
                return False
            continue
        if observed != expected:
            return False
    return True


def _parse_summary(text):
    structured = _parse_structured_summary_display(text)
    if structured:
        return structured

    values = {}
    number = r"(?:<\s*)?-?\d+(?:\.\d+)?"
    model = re.search(
        r"Estimate\s+Lower bound\s+Upper bound.*?\n\s*(%s)\s+(%s)\s+(%s)\s+(?:%s\s+)?(%s)"
        % (number, number, number, number, number),
        text,
        re.S,
    )
    heterogeneity = re.search(
        r"Heterogeneity.*?\n\s*(?:tau\^2|τ²|t²|Q).*?\n\s*((?:%s%%?\s+){3}%s%%?)"
        % (number, number),
        text,
        re.S,
    )
    if model:
        values.update(
            {
                "estimate": _to_float(model.group(1)),
                "lower_bound": _to_float(model.group(2)),
                "upper_bound": _to_float(model.group(3)),
                "p_value": _to_float(model.group(4)),
            }
        )
        if "Std. error" in model.group(0).splitlines()[0]:
            model_numbers = re.findall(number, model.group(0).splitlines()[-1])
            if len(model_numbers) >= 5:
                values["standard_error"] = _to_float(model_numbers[-2])
    if heterogeneity:
        row = re.findall(number, heterogeneity.group(1))
        values.update(
            {
                "tau_squared": _to_float(row[0]),
                "q": _to_float(row[1]),
                "heterogeneity_p_value": _to_float(row[2]),
                "i_squared": _to_float(row[3]),
            }
        )
        degrees = re.search(r"Q\(df=(\d+)\)", text)
        if degrees:
            values["heterogeneity_df"] = _to_float(degrees.group(1))
    calculation_scale = re.search(
        r"Calculation scale:\s*([^\n]+?)\s*-\s*estimate:\s*(%s),\s*"
        r"lower:\s*(%s),\s*upper:\s*(%s),\s*std\. error:\s*(%s)"
        % (number, number, number, number),
        text,
    )
    if calculation_scale:
        values.update(
            {
                "calculation_scale.estimate": _to_float(calculation_scale.group(2)),
                "calculation_scale.lower_bound": _to_float(calculation_scale.group(3)),
                "calculation_scale.upper_bound": _to_float(calculation_scale.group(4)),
                "calculation_scale.standard_error": _to_float(
                    calculation_scale.group(5)
                ),
            }
        )
    study_count = re.search(r"\(k\s*=\s*(\d+)\)", text)
    if study_count:
        values["study_count"] = _to_float(study_count.group(1))
    return values


def _parse_result_table(text):
    values = {}
    lines = text.splitlines()
    is_regression = any("Covariate" in line and "Coefficients" in line for line in lines)
    is_subgroup = any("Subgroups" in line and "Studies" in line for line in lines)
    in_heterogeneity = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Heterogeneity":
            in_heterogeneity = True
            continue
        if not stripped or stripped.startswith(("Model Results", "Metric:")):
            continue
        if in_heterogeneity:
            match = re.match(
                r"^\s*(.+?)\s{2,}(-?\d+(?:\.\d+)?)\s+\((\d+)\)\s+"
                r"(?:<\s*)?(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)%\s*$",
                line,
            )
            if match:
                prefix = "heterogeneity.%s" % _result_row_key(match.group(1))
                values.update(
                    {
                        "%s.q" % prefix: _to_float(match.group(2)),
                        "%s.df" % prefix: _to_float(match.group(3)),
                        "%s.p_value" % prefix: _to_float(match.group(4)),
                        "%s.i_squared" % prefix: _to_float(match.group(5)),
                    }
                )
            continue
        if is_subgroup:
            match = re.match(
                r"^\s*(.+?)\s{2,}(\d+)\s+(-?\d+(?:\.\d+)?)\s+"
                r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
                r"(-?\d+(?:\.\d+)?)\s+(?:<\s*)?(-?\d+(?:\.\d+)?)"
                r"(?:\s+(-?\d+(?:\.\d+)?))?\s*$",
                line,
            )
            if match:
                prefix = "model.%s" % _result_row_key(match.group(1))
                names = (
                    "studies",
                    "estimate",
                    "lower_bound",
                    "upper_bound",
                    "standard_error",
                    "p_value",
                    "z_value",
                )
                for metric, raw in zip(names, match.groups()[1:]):
                    if raw is not None:
                        values["%s.%s" % (prefix, metric)] = _to_float(raw)
            continue
        match = re.match(
            r"^\s*([+\-]?\s*.+?)\s{2,}(-?\d+(?:\.\d+)?)\s+"
            r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
            r"(-?\d+(?:\.\d+)?)(?:\s+(?:<\s*)?(-?\d+(?:\.\d+)?))?\s*$",
            line,
        )
        if match:
            prefix = "model.%s" % _result_row_key(match.group(1))
            first_metric = "coefficient" if is_regression else "estimate"
            names = (
                first_metric,
                "lower_bound",
                "upper_bound",
                "standard_error",
                "p_value",
            )
            for metric, raw in zip(names, match.groups()[1:]):
                if raw is not None:
                    values["%s.%s" % (prefix, metric)] = _to_float(raw)
    if is_regression:
        omnibus = re.search(r"Omnibus p-value\s*\n\s*(?:<\s*)?(-?\d+(?:\.\d+)?)", text)
        if omnibus:
            values["omnibus.p_value"] = _to_float(omnibus.group(1))
    return values


def _parse_weights(text):
    values = {}
    for name, raw in re.findall(r"^\s*(.+?)\s*:\s*(-?\d+(?:\.\d+)?)%\s*$", text, re.M):
        values["weight.%s" % _slug(name)] = _to_float(raw)
    return values


def _result_row_key(label):
    stripped = str(label).strip()
    if stripped.startswith("+"):
        return "through_%s" % _slug(stripped[1:])
    if stripped.startswith("-"):
        return "without_%s" % _slug(stripped[1:])
    return _slug(stripped)


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _parse_structured_summary_display(text):
    values = {}
    model_values = _parse_quoted_summary_row(text, ["res.col", "col"])
    if model_values:
        values.update(_extract_model_values(model_values))

    heterogeneity_values = _parse_quoted_summary_row(text, ["het.col"])
    if heterogeneity_values:
        values.update(_extract_heterogeneity_values(heterogeneity_values))

    return values


def _parse_quoted_summary_row(text, prefixes):
    for prefix in prefixes:
        labels_match = re.search(r"%s\.labels\s+([^\n]+)" % re.escape(prefix), text)
        values_match = re.search(r"%s\.vals\s+([^\n]+)" % re.escape(prefix), text)
        if not labels_match or not values_match:
            continue

        labels = re.findall(r'"([^"]+)"', labels_match.group(1))
        values = re.findall(r'"([^"]+)"', values_match.group(1))
        if labels and len(labels) == len(values):
            return dict(zip(labels, values))
    return {}


def _extract_model_values(row):
    extracted = {}
    mapping = {
        "Estimate": "estimate",
        "Lower bound": "lower_bound",
        "Upper bound": "upper_bound",
        "p-Value": "p_value",
        "p-value": "p_value",
        "p-Val": "p_value",
    }
    for label, key in mapping.items():
        if label in row:
            extracted[key] = _to_float(row[label])
    return extracted


def _extract_heterogeneity_values(row):
    extracted = {}
    for label, value in row.items():
        if label in {"tau^2", "τ²", "t²"}:
            extracted["tau_squared"] = _to_float(value)
        elif label.startswith("Q("):
            extracted["q"] = _to_float(value)
        elif label in {"I^2", "I²"}:
            extracted["i_squared"] = _to_float(value)
    return extracted


def _to_float(value):
    return float(str(value).replace("<", "").replace("%", "").strip())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--coverage-matrix":
        write_golden_coverage_matrix(sys.argv[2])
        print("wrote %s" % os.path.abspath(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "--baseline-manifest":
        write_comprehensive_golden_baseline_manifest(sys.argv[2])
        print("wrote %s" % os.path.abspath(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "--comprehensive-baseline":
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None
        report = capture_comprehensive_golden_baseline(output_dir=output_dir)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif len(sys.argv) > 1 and sys.argv[1] == "--compatibility-report":
        report_path = sys.argv[2] if len(sys.argv) > 2 else None
        report = run_curated_golden_set(report_path)
        print(json.dumps(report, indent=2, sort_keys=True))
        raise SystemExit(0 if report["passed"] else 1)
    else:
        report_path = sys.argv[1] if len(sys.argv) > 1 else None
        print(
            json.dumps(
                capture_curated_binary_bundle(report_path), indent=2, sort_keys=True
            )
        )
