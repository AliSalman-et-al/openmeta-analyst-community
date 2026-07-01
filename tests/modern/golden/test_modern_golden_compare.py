import json
import os
import sys
import types
from contextlib import contextmanager

sys.path.insert(0, os.path.abspath("src"))

from modern_golden_compare import (
    ACCEPTED_EXCEPTION,
    CAPTURE_ERROR,
    MISSING_OUTPUT,
    NUMERIC_DRIFT,
    PASS,
    TEXT_ARTIFACT_DRIFT,
    UNSUPPORTED_WORKFLOW,
    compare_golden_baseline,
    main,
)


def test_modern_comparison_classifies_compatible_capture_as_pass():
    report = compare_golden_baseline(_baseline(), _modern())

    assert report["passed"] is True
    assert report["rows"][0]["classification"] == PASS
    assert report["rows"][0]["id"] == "amino-binary-random"


def test_modern_comparison_classifies_numeric_drift_with_row_context():
    modern = _modern()
    modern["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = 0.773

    row = compare_golden_baseline(_baseline(), modern)["rows"][0]

    assert row["classification"] == NUMERIC_DRIFT
    assert row["id"] == "amino-binary-random"
    assert "Summary.estimate" in row["detail"]


def test_modern_comparison_classifies_non_numeric_result_drift():
    modern = _modern()
    modern["curated_golden_set"][0]["texts"]["Summary"] = "changed"

    row = compare_golden_baseline(_baseline(), modern)["rows"][0]

    assert row["classification"] == TEXT_ARTIFACT_DRIFT
    assert row["id"] == "amino-binary-random"


def test_modern_comparison_classifies_missing_output_unsupported_and_capture_error():
    baseline = _baseline()
    missing = compare_golden_baseline(baseline, {"curated_golden_set": []})["rows"][0]
    unsupported = compare_golden_baseline(baseline, _modern(status="unsupported"))[
        "rows"
    ][0]
    failed = compare_golden_baseline(
        baseline, _modern(status="failure", failure={"message": "R failed"})
    )["rows"][0]

    assert missing["classification"] == MISSING_OUTPUT
    assert unsupported["classification"] == UNSUPPORTED_WORKFLOW
    assert failed["classification"] == CAPTURE_ERROR


def test_modern_comparison_consumes_committed_manifest_ids():
    report = compare_golden_baseline(
        _baseline(),
        _modern(),
        manifest={"curated_golden_set": ["amino-binary-random", "continuous-random"]},
    )

    assert report["passed"] is False
    assert report["rows"][0]["id"] == "continuous-random"
    assert report["rows"][0]["classification"] == MISSING_OUTPUT


def test_modern_comparison_marks_only_matching_exception_as_accepted():
    modern = _modern()
    modern["curated_golden_set"][0]["outputs"]["Summary"]["estimate"] = 0.773

    report = compare_golden_baseline(
        _baseline(), modern, [{"id": "amino-binary-random", "reason": "documented"}]
    )

    assert report["passed"] is True
    assert report["rows"][0]["classification"] == ACCEPTED_EXCEPTION
    assert report["rows"][0]["exception"] == "documented"


def test_modern_comparison_cli_writes_report(tmp_path):
    reference = tmp_path / "reference.json"
    modern = tmp_path / "modern.json"
    report = tmp_path / "report.json"
    reference.write_text(json.dumps(_baseline()))
    modern.write_text(json.dumps(_modern()))

    assert main([str(reference), str(modern), "--report", str(report)]) == 0
    assert json.loads(report.read_text())["passed"] is True


def test_curated_golden_set_includes_sequential_binary_and_continuous_workflows():
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        bundles = dict(
            (bundle["id"], bundle)
            for bundle in golden_analysis.curated_golden_bundles()
        )

    assert bundles["amino-binary-cumulative"]["case"].analysis_type == "cumulative"
    assert "Cumulative Summary" in bundles["amino-binary-cumulative"]["expected"]
    assert (
        bundles["amino-binary-leave-one-out"]["case"].analysis_type == "leave-one-out"
    )
    assert "Leave-one-out Summary" in bundles["amino-binary-leave-one-out"]["expected"]
    assert bundles["continuous-cumulative"]["case"].analysis_type == "cumulative"
    assert "Cumulative Summary" in bundles["continuous-cumulative"]["expected"]
    assert bundles["continuous-leave-one-out"]["case"].analysis_type == "leave-one-out"
    assert "Leave-one-out Summary" in bundles["continuous-leave-one-out"]["expected"]


def test_golden_summary_parser_reads_current_openmetar_summary_display():
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        parsed = golden_analysis._parse_summary(
            """
$model.title
[1] "Binary Random-Effects Model\\n\\nMetric: Odds Ratio"

$table.titles
[1] " Model Results"       " Heterogeneity"       " Results (log scale)"

$arrays
$arrays$arr1
               [,1]       [,2]          [,3]          [,4]
res.col.labels "Estimate" "Lower bound" "Upper bound" "p-Value"
res.col.vals   "0.770"    "0.485"       "1.222"       "0.267"

$arrays$arr2
               [,1]    [,2]       [,3]           [,4]
het.col.labels "tau^2" "Q(df=18)" "Het. p-Value" "I^2"
het.col.vals   "0.378" "33.360"   "0.015"        "46.044"

$arrays$arr3
alt.col.labels "Estimate" "Lower bound" "Upper bound" "Std. error"
alt.col.vals   "-0.262"   "-0.724"      "0.200"       "0.236"
"""
        )

    assert parsed == {
        "estimate": 0.770,
        "lower_bound": 0.485,
        "upper_bound": 1.222,
        "p_value": 0.267,
        "tau_squared": 0.378,
        "q": 33.360,
        "i_squared": 46.044,
    }


def test_compare_bundle_requires_expected_plot_artifacts(tmp_path):
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        plot = tmp_path / "forest.png"
        plot.write_bytes(b"png")
        bundle = {
            "expected": {"Summary": {}},
            "artifacts": {"Forest Plot": str(plot)},
            "tolerances": {},
        }

        comparisons = golden_analysis.compare_bundle(
            bundle,
            {"texts": {"Summary": "ok"}, "images": {"forest plot": str(plot)}},
        )
        missing = golden_analysis.compare_bundle(
            bundle,
            {
                "texts": {"Summary": "ok"},
                "images": {"Forest Plot": str(tmp_path / "missing.png")},
            },
        )

    assert {
        "metric": "artifact_present",
        "section": "Forest Plot",
        "passed": True,
        "expected": True,
        "observed": True,
        "tolerance": None,
        "drift": None,
    } in comparisons
    assert any(
        row["metric"] == "artifact_present" and row["passed"] is False
        for row in missing
    )


def test_headless_analysis_dispatches_sequential_binary_and_continuous_workflows(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("OMA_STUB_BACKEND", raising=False)
    with _import_legacy_golden_modules() as (_, headless_analysis, meta_globals):
        calls = []

        class Model(object):
            dataset = object()

            def set_current_metric(self, metric):
                calls.append(("metric", metric))

        monkeypatch.setattr(
            headless_analysis, "load_dataset_model", lambda path: Model()
        )
        monkeypatch.setattr(
            headless_analysis.meta_py_r,
            "ma_dataset_to_simple_binary_robj",
            lambda model: calls.append(("data", "binary")),
            raising=False,
        )
        monkeypatch.setattr(
            headless_analysis.meta_py_r,
            "ma_dataset_to_simple_continuous_robj",
            lambda model: calls.append(("data", "continuous")),
            raising=False,
        )
        monkeypatch.setattr(
            headless_analysis.meta_py_r,
            "run_workflow_analysis",
            lambda workflow, method, params: {
                "texts": {"Summary": "%s:%s" % (workflow, method)}
            },
            raising=False,
        )

        binary = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "b.oma"),
            "binary.random",
            {},
            metric="OR",
            data_type=meta_globals.BINARY,
            analysis_type="cumulative",
        )
        continuous = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "c.oma"),
            "continuous.random",
            {},
            metric="SMD",
            data_type=meta_globals.CONTINUOUS,
            analysis_type="leave-one-out",
        )

        assert (
            headless_analysis.run_headless_analysis(binary)["texts"]["Summary"]
            == "cumulative:binary.random"
        )
        assert (
            headless_analysis.run_headless_analysis(continuous)["texts"]["Summary"]
            == "leave-one-out:continuous.random"
        )


def test_headless_analysis_dispatches_meta_regression_with_selected_covariates(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("OMA_STUB_BACKEND", raising=False)
    with _import_legacy_golden_modules() as (_, headless_analysis, meta_globals):
        calls = []

        class DataSet(object):
            def add_covariate(self, covariate, values):
                calls.append(("covariate", covariate, values))

        class Model(object):
            dataset = DataSet()

            def set_current_metric(self, metric):
                calls.append(("metric", metric))

        covariates = [
            {"name": "golden_year", "type": "continuous", "values": {"Study A": 1990}}
        ]

        monkeypatch.setattr(
            headless_analysis, "load_dataset_model", lambda path: Model()
        )
        monkeypatch.setattr(
            headless_analysis.meta_py_r,
            "ma_dataset_to_simple_binary_robj",
            lambda model, **kwargs: calls.append(("data", kwargs)),
            raising=False,
        )
        monkeypatch.setattr(
            headless_analysis.meta_py_r,
            "run_meta_regression",
            lambda dataset, studies, covs, metric, conf_level=None: {
                "texts": {"Summary": metric}
            },
            raising=False,
        )

        case = headless_analysis.HeadlessAnalysisCase(
            str(tmp_path / "b.oma"),
            None,
            {"conf.level": 95.0},
            metric="OR",
            data_type=meta_globals.BINARY,
            analysis_type="meta_regression",
            covariates=covariates,
        )

        assert headless_analysis.run_headless_analysis(case)["texts"]["Summary"] == "OR"
        assert ("data", {"covs_to_include": [("golden_year", "continuous")]}) in calls


def test_comprehensive_golden_baseline_capture_writes_reproducible_bundle(
    tmp_path, monkeypatch
):
    with _import_legacy_golden_modules() as (golden_analysis, _, _):
        bundles = [
            _capture_bundle("amino-binary-random", "amino.oma", "binary.random"),
            _capture_bundle("continuous-random", "continuous.oma", "continuous.random"),
        ]
        plot = tmp_path / "plot.png"
        plot.write_bytes(b"plot")

        monkeypatch.setattr(
            golden_analysis, "curated_golden_bundles", lambda root_dir=None: bundles
        )
        monkeypatch.setattr(
            golden_analysis.meta_py_r,
            "RlibLoader",
            lambda: types.SimpleNamespace(load_OpenMetaR=lambda: None),
        )
        monkeypatch.setattr(golden_analysis, "_commit_sha", lambda: "abc123")
        monkeypatch.setattr(
            golden_analysis,
            "_tool_versions",
            lambda: {
                "openmeta_analyst": "0.005",
                "python": "3.11.15",
                "os": "Windows",
                "r": "R version 4.6.0",
                "rpy2": "3.6.7",
                "pyqt": "5.15.11",
            },
        )

        def runner(case):
            if case == "failing-case":
                raise RuntimeError("modern baseline capture failed")
            return {
                "texts": {
                    "Summary": "Estimate Lower bound Upper bound\n 1.0 0.5 1.5 0.02"
                },
                "images": {"Forest Plot": str(plot)},
            }

        report = golden_analysis.capture_comprehensive_golden_baseline(
            output_dir=str(tmp_path / "artifacts" / "golden-baseline"),
            runner=runner,
            timestamp="2026-06-23T00:00:00Z",
            capture_mode="authoritative",
            capture_command="capture command",
            baseline_environment=dict(
                golden_analysis.MODERN_BASELINE_ENVIRONMENT_EXPECTED
            ),
        )

    capture_dir = tmp_path / "artifacts" / "golden-baseline" / "captures"
    archive_path = (
        tmp_path / "artifacts" / "golden-baseline" / "comprehensive-golden-baseline.zip"
    )

    assert report["baseline"] == "comprehensive-golden"
    assert report["passed"] is False
    assert [row["status"] for row in report["curated_golden_set"]] == [
        "success",
        "failure",
    ]
    assert report["curated_golden_set"][0]["authoritative"] is True
    assert (capture_dir / "amino-binary-random.json").exists()
    assert (capture_dir / "continuous-random.json").exists()
    assert archive_path.exists()
    assert report["artifact_bundle"]["path"].endswith(
        "comprehensive-golden-baseline.zip"
    )


@contextmanager
def _import_legacy_golden_modules():
    names = [
        "golden_analysis",
        "headless_analysis",
        "ma_data_table_model",
        "ma_dataset",
        "meta_globals",
        "meta_py_r",
    ]
    previous = dict((name, sys.modules.get(name)) for name in names)
    try:
        for name in ["golden_analysis", "headless_analysis"]:
            sys.modules.pop(name, None)
        sys.modules["ma_data_table_model"] = types.SimpleNamespace(DatasetModel=object)
        sys.modules["ma_dataset"] = types.SimpleNamespace(
            Covariate=lambda name, kind: (name, kind)
        )
        sys.modules["meta_globals"] = types.SimpleNamespace(
            BINARY="binary",
            CONTINUOUS="continuous",
            DIAGNOSTIC="diagnostic",
            VERSION=0.005,
        )
        sys.modules["meta_py_r"] = types.SimpleNamespace(RlibLoader=lambda: None)
        import golden_analysis
        import headless_analysis
        import meta_globals

        yield golden_analysis, headless_analysis, meta_globals
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _baseline():
    return {
        "curated_golden_set": [
            {
                "id": "amino-binary-random",
                "dataset": "amino.oma",
                "method": "binary.random",
                "metric": "OR",
                "tolerances": {"estimate": 0.001},
                "outputs": {"Summary": {"estimate": 0.77}},
                "texts": {"Summary": "same summary"},
                "artifacts": [
                    {
                        "label": "Forest Plot",
                        "kind": "plot",
                        "path": "reference.png",
                        "sha256": "abc",
                    }
                ],
            }
        ]
    }


def _capture_bundle(bundle_id, dataset, method):
    return {
        "id": bundle_id,
        "dataset": dataset,
        "data_family": "binary",
        "method": method,
        "metric": "OR",
        "parameters": {},
        "tolerances": {"estimate": 0.001},
        "expected": {"Summary": {}},
        "artifacts": {"Forest Plot": "./r_tmp/%s.png" % bundle_id},
        "case": "failing-case" if "continuous" in bundle_id else "passing-case",
    }


def _modern(status="success", failure=None):
    row = {
        "id": "amino-binary-random",
        "status": status,
        "outputs": {"Summary": {"estimate": 0.7705}},
        "texts": {"Summary": "same summary"},
        "artifacts": [
            {
                "label": "Forest Plot",
                "kind": "plot",
                "path": "modern.png",
                "sha256": "def",
            }
        ],
    }
    if failure:
        row["failure"] = failure
    return {"curated_golden_set": [row]}
