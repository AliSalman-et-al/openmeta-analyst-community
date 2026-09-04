"""Exercise Unicode, R NULL, vector parameters, and text decoding through rpy2.

The real bridge initializes embedded R, so this test runs in a subprocess and
skips when the in-process R stack is unavailable.
"""

import os
import textwrap

from ._r_driver_support import run_python_driver

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


_DRIVER = textwrap.dedent(
    """
    import locale, os, sys, tempfile
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    os.environ.setdefault(
        "RCMS_QT6_BUILD_ROOT",
        os.path.join(__REPO_ROOT__, "build", "qt6-verification"),
    )
    sys.path.insert(0, os.path.join(__REPO_ROOT__, "src"))
    sys.path.insert(0, os.path.join(__REPO_ROOT__, "tests", "python", "fast"))

    from rc_metastudio.qt6_ui import prepare_generated_ui_imports
    prepare_generated_ui_imports()

    from rc_metastudio import r_backend
    r_backend.install_r_backend()
    try:
        from rc_metastudio import r_bridge
        from rc_metastudio.meta_globals import FACTOR
        try:
            r_bridge.RLibraryLoader().load_rcmetar()
        except Exception:
            source_package = os.path.join(__REPO_ROOT__, "r", "RCMetaR")
            r_bridge.ro.r("devtools::load_all")(source_package, quiet=True)
    except Exception as exc:
        # R / rpy2 / RCMetaR not available in this environment.
        sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
        sys.exit(42)

    ro = r_bridge.ro

    from rc_metastudio.r_call_serialization import r_transaction

    with r_transaction():
        ro.globalenv["workflow_data"] = ro.r("list()")
    original_execute_r_function = r_bridge.execute_r_function

    def raise_workflow_r_error(name, *args, **kwargs):
        if name == "rcmetar.run.diagnostic.analyses":
            raise r_bridge.RRuntimeError("workflow execution failed")
        return original_execute_r_function(name, *args, **kwargs)

    r_bridge.execute_r_function = raise_workflow_r_error
    try:
        r_bridge.run_versioned_analysis_requests(
            [{
                "version": 1,
                "data_type": "diagnostic",
                "workflow": "subgroup",
                "method": "diagnostic.random",
                "metric": "Sens",
                "params": {"measure": "Sens"},
            }],
            diagnostic_data_name="workflow_data",
        )
    except r_bridge.DiagnosticExecutionError as exc:
        assert "workflow execution failed" in str(exc)
    else:
        raise AssertionError("diagnostic workflow R failure was not translated")
    finally:
        r_bridge.execute_r_function = original_execute_r_function

    assert not hasattr(r_bridge, "_sanitize_for_R")

    assert r_bridge._r_is_null(ro.r("list()").names) is True
    assert r_bridge._r_is_null(ro.r("c(a=1)").names) is False
    # Native translation maps τ² to t² on Windows, so decode R text as UTF-8.
    from rpy2.rinterface_lib import callbacks, conversion, openrlib

    if sys.platform == "win32":
        assert callbacks._CCHAR_ENCODING == locale.getpreferredencoding(False)

    tau_squared = chr(0x03C4) + chr(0x00B2)
    rchar = openrlib.rlib.Rf_mkCharCE(
        conversion.ffi.new("char[]", tau_squared.encode("utf-8")),
        openrlib.rlib.CE_UTF8,
    )
    assert conversion._rchar_to_str(rchar, "cp1252") == tau_squared

    params, defaults, var_order, pretty = r_bridge.get_params("binary.random")
    assert isinstance(defaults, dict)
    assert "conf.level" in defaults or "rm.method" in defaults

    class FakeCovariate:
        def __init__(self, name, data_type):
            self.name = name
            self.data_type = data_type

    class FakeStudy:
        def __init__(self, study_id, name, year):
            self.id = study_id
            self.name = name
            self.year = year
            self.include = True

    class FakeDataset:
        def __init__(self, covariates, values):
            self.covariates = covariates
            self._values = values

        def get_covariate_values(self, covariate, ids_for_keys=False):
            assert ids_for_keys is True
            return self._values[covariate]

    class FakeModel:
        def __init__(self, data_type, raw_data, effect="OR"):
            self.current_effect = effect
            self._raw_data = raw_data
            self._data_type = data_type
            self._studies = [
                FakeStudy(1, 'O\\'Brien "quote" \\\\back café τ', 1993),
                FakeStudy(2, "Plain study", None),
            ]
            covariates = [
                FakeCovariate('Group "label" \\\\ café τ', FACTOR),
                FakeCovariate("Dose", r_bridge.CONTINUOUS),
            ]
            self.dataset = FakeDataset(
                covariates,
                {
                    covariates[0].name: {
                        1: 'alpha "quoted" \\\\ café τ',
                        2: "beta",
                    },
                    covariates[1].name: {
                        1: 1.5,
                        2: 2.5,
                    },
                },
            )

        def get_studies(self, only_if_included=True):
            return self._studies

        def get_current_estimates_and_standard_errors(self, **kwargs):
            return [-0.5596157879, -0.8295982833], [0.6172133998, 0.7152562329]

        def included_studies_have_raw_data(self):
            return True

        def get_current_raw_data(self, **kwargs):
            return self._raw_data

        def included_studies_have_point_estimates(self, effect=None):
            return True

    def assert_text_survived(var_name):
        assert list(ro.r("%s@study.names" % var_name)) == [
            'O\\'Brien "quote" \\\\back café τ',
            "Plain study",
        ]
        assert list(ro.r("%s@years" % var_name))[0] == 1993
        assert bool(ro.r("is.na(%s@years[2])" % var_name)[0]) is True
        assert list(ro.r("%s@covariates[[1]]@cov.name" % var_name)) == [
            'Group "label" \\\\ café τ'
        ]
        assert list(ro.r("%s@covariates[[1]]@cov.vals" % var_name)) == [
            'alpha "quoted" \\\\ café τ',
            "beta",
        ]
        assert list(ro.r("%s@covariates[[1]]@ref.var" % var_name)) == [
            'alpha "quoted" \\\\ café τ'
        ]

    quoted_values_str, quoted_values = r_bridge.covariate_to_r_expression(
        FakeCovariate("region", FACTOR),
        [1, 2],
        FakeDataset(
            [],
            {
                "region": {
                    1: "control τ",
                    2: "O'Brien \\\\ north",
                }
            },
        ),
        named_list=False,
        return_covariate_values=True,
    )
    assert quoted_values == ["'control \\\\u03c4'", "'O\\\\'Brien \\\\\\\\ north'"]
    assert list(ro.r(quoted_values_str)) == ["control τ", "O'Brien \\\\ north"]

    binary_model = FakeModel("binary", [[6, 27, 9, 27], [3, 59, 7, 64]])
    r_bridge.dataset_to_simple_binary_r_object(binary_model, var_name="issue146_binary")
    assert_text_survived("issue146_binary")

    continuous_model = FakeModel(
        "continuous",
        [[27, 5.1, 1.2, 27, 6.2, 1.5], [59, 3.4, 0.9, 64, 4.1, 1.1]],
        effect="MD",
    )
    r_bridge.dataset_to_simple_continuous_r_object(
        continuous_model,
        var_name="issue146_continuous",
    )
    assert_text_survived("issue146_continuous")
    # The production forest renderer cannot compose a study label from a
    # missing year. Preserve the conversion assertion above, then provide a
    # valid analysis fixture for the cross-layer display contract below.
    ro.r("issue146_continuous@years[2] <- 2001L")

    analysis_dir = tempfile.mkdtemp(prefix="rcmetastudio-display-contract-")
    forest_path = os.path.join(analysis_dir, "forest.png")
    forest_display_path = os.path.join(analysis_dir, "forest.display.svg")
    continuous_result = r_bridge.run_versioned_analysis_request(
        {
            "version": 1,
            "data_type": "continuous",
            "method": "continuous.random",
            "metric": "MD",
            "workflow": "standard",
            "params": {
                "conf.level": 95.0,
                "digits": 3,
                "measure": "MD",
                "rm.method": "DL",
                "fp_style": "default",
                "fp_col1_str": "Study or Subgroup",
                "fp_col2_str": "[default]",
                "fp_col3_str": "Intervention",
                "fp_col4_str": "Control",
                "fp_xlabel": "[default]",
                "fp_outpath": forest_path,
                "fp_display_path": forest_display_path,
                "fp_plot_lb": "[default]",
                "fp_plot_ub": "[default]",
                "fp_show_col1": True,
                "fp_show_col2": True,
                "fp_show_col3": True,
                "fp_show_col4": True,
                "fp_show_summary_line": True,
                "fp_xticks": "[default]",
                "create.plot": True,
                "write.to.file": False,
            },
        },
        data_name="issue146_continuous",
    )
    assert continuous_result["images"]["Forest Plot"] == forest_path
    assert continuous_result["display_images"]["Forest Plot"] == forest_display_path

    from PyQt6 import QtWidgets
    from rc_metastudio import results_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    result_window = results_window.ResultsWindow(continuous_result)
    result_window.resize(700, 500)
    result_window.show()
    for _ in range(5):
        app.processEvents()
    plot_item = next(
        item for item in result_window.scene.items()
        if isinstance(item, results_window.QGraphicsSvgItem)
    )
    initial_window_width = result_window.width()
    initial_plot_width = plot_item.sceneBoundingRect().width()
    initial_available_width = (
        result_window.graphics_view.viewport().width()
        - result_window.x_coord
        - results_window.padding
    )
    assert initial_plot_width >= initial_available_width * 0.9

    result_window.resize(
        initial_window_width - 200,
        result_window.height(),
    )
    for _ in range(3):
        app.processEvents()
    shrunken_width = plot_item.sceneBoundingRect().width()
    assert shrunken_width < initial_plot_width

    result_window.resize(
        initial_window_width,
        result_window.height(),
    )
    for _ in range(3):
        app.processEvents()
    assert plot_item.sceneBoundingRect().width() > shrunken_width

    before_splitter_width = plot_item.sceneBoundingRect().width()
    result_window.results_nav_splitter.moveSplitter(360, 1)
    for _ in range(3):
        app.processEvents()
    assert plot_item.sceneBoundingRect().width() < before_splitter_width
    result_window.close()
    app.processEvents()

    diagnostic_model = FakeModel("diagnostic", [[6, 21, 9, 18], [3, 56, 7, 57]])
    original_execute_r_function = r_bridge.execute_r_function

    def raise_conversion_r_error(name, *args, **kwargs):
        if name == "rcmetar.create.diagnostic.data":
            raise r_bridge.RRuntimeError("diagnostic conversion failed")
        return original_execute_r_function(name, *args, **kwargs)

    r_bridge.execute_r_function = raise_conversion_r_error
    try:
        r_bridge.dataset_to_simple_diagnostic_r_object(
            diagnostic_model,
            var_name="failed_diagnostic",
        )
    except r_bridge.DiagnosticExecutionError as exc:
        assert "diagnostic conversion failed" in str(exc)
    else:
        raise AssertionError("diagnostic conversion R failure was not translated")
    finally:
        r_bridge.execute_r_function = original_execute_r_function

    r_bridge.dataset_to_simple_diagnostic_r_object(
        diagnostic_model,
        var_name="issue146_diagnostic",
    )
    assert_text_survived("issue146_diagnostic")

    from rc_metastudio import analysis_adapter

    class FilteredDiagnosticDataset:
        def __init__(self, covariate):
            self.covariate = covariate

        def get_covariate_values(self, covariate, ids_for_keys=False):
            assert ids_for_keys is True
            assert covariate == self.covariate.name
            return {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}

    class FilteredDiagnosticModel:
        def __init__(self):
            self.current_effect = "Sens"
            self._studies = [
                FakeStudy(1, "Included 1", 1990),
                FakeStudy(2, "Included 2", 1991),
                FakeStudy(3, "Included 3", 1992),
                FakeStudy(4, "Included 4", 1993),
                FakeStudy(5, "Included 5", 1994),
                FakeStudy(6, "Missing moderator", 1995),
            ]
            self.covariate = FakeCovariate("Moderator", r_bridge.CONTINUOUS)
            self.dataset = FilteredDiagnosticDataset(self.covariate)

        def get_studies(self, only_if_included=True):
            assert only_if_included is True
            return self._studies

        def get_current_estimates_and_standard_errors(
            self, only_if_included=True, only_these_studies=None, effect=None
        ):
            assert only_if_included is True
            values = {
                1: (0.1, 0.05),
                2: (0.2, 0.05),
                3: (0.3, 0.05),
                4: (0.4, 0.05),
                5: (0.5, 0.05),
                6: (None, None),
            }
            studies = self._studies
            if only_these_studies is not None:
                studies = [
                    study for study in studies if study.id in only_these_studies
                ]
            return tuple(zip(*(values[study.id] for study in studies)))

        def included_studies_have_raw_data(self):
            return True

        def get_current_raw_data(
            self, only_if_included=True, only_these_studies=None
        ):
            assert only_if_included is True
            values = {
                1: [10, 5, 4, 10],
                2: [12, 4, 6, 10],
                3: [8, 7, 5, 13],
                4: [15, 3, 8, 9],
                5: [11, 6, 7, 12],
                6: [20, 2, 10, 10],
            }
            studies = self._studies
            if only_these_studies is not None:
                studies = [
                    study for study in studies if study.id in only_these_studies
                ]
            return [values[study.id] for study in studies]

        def included_studies_have_point_estimates(self, effect=None):
            return False

    filtered_model = FilteredDiagnosticModel()
    selected = analysis_adapter.select_studies_for_covariates(
        filtered_model, (filtered_model.covariate,)
    )
    assert len(selected.studies) == 5
    assert selected.has_missing_values is True
    assert selected.excluded_study_names == ("Missing moderator",)

    diagnostic_meta_request = analysis_adapter.make_analysis_request(
        data_type="diagnostic",
        workflow="meta-regression",
        method="diagnostic.reitsma",
        metric="Sens",
        parameters={
            "conf.level": 95.0,
            "digits": 3,
            "estimator": "REML",
            "adjust": 0.5,
            "correction.policy": "All studies if any zero exists",
        },
    )
    previous_cwd = os.getcwd()
    previous_scratch_dir = os.environ.pop("RCMS_ANALYSIS_SCRATCH_DIR", None)
    try:
        with tempfile.TemporaryDirectory(prefix="rcmetar-meta-regression-") as isolated_cwd:
            try:
                os.chdir(isolated_cwd)
                diagnostic_meta_result = analysis_adapter.execute_meta_regression_request(
                    filtered_model,
                    selected.studies,
                    (filtered_model.covariate,),
                    diagnostic_meta_request,
                    False,
                    95.0,
                )
            finally:
                os.chdir(previous_cwd)
    finally:
        if previous_scratch_dir is not None:
            os.environ["RCMS_ANALYSIS_SCRATCH_DIR"] = previous_scratch_dir
    assert "Sensitivity coefficients" in diagnostic_meta_result["texts"]
    assert list(ro.r("tmp_obj@study.names")) == [
        "Included 1",
        "Included 2",
        "Included 3",
        "Included 4",
        "Included 5",
    ]
    assert list(ro.r("tmp_obj@TP")) == [10, 12, 8, 15, 11]
    assert list(ro.r("tmp_obj@FN")) == [5, 4, 7, 3, 6]
    assert list(ro.r("tmp_obj@FP")) == [4, 6, 5, 8, 7]
    assert list(ro.r("tmp_obj@TN")) == [10, 10, 13, 9, 12]
    assert list(ro.r("tmp_obj@covariates[[1]]@cov.vals")) == [1, 2, 3, 4, 5]

    invalid_confidence_level_checks = ro.r('''
      c(
        inherits(try(rcmetar.set.global.conf.level(100), silent=TRUE), "try-error"),
        inherits(try(rcmetar.get.mult.from.conf.level(100), silent=TRUE), "try-error"),
        inherits(try(rcmetar.get.mult.from.conf.level(0), silent=TRUE), "try-error"),
        inherits(try(rcmetar.get.mult.from.conf.level(Inf), silent=TRUE), "try-error")
      )
    ''')
    assert all(bool(value) for value in invalid_confidence_level_checks)

    from tests.analysis_regression.golden.support import golden_analysis

    subgroup_bundle = [
        bundle for bundle in golden_analysis.curated_golden_bundles()
        if bundle["id"] == "amino-binary-subgroup"
    ][0]
    subgroup_result = golden_analysis.headless_analysis.run_headless_analysis(subgroup_bundle["case"])
    assert "Subgroup Summary" in subgroup_result["texts"]

    sys.stdout.write("OK\\n")
    # Hard-exit so embedded-R finalizers don't run: rpy2/R teardown can
    # segfault on interpreter shutdown on Windows, which would turn a passing
    # check into a spurious non-zero exit.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


_NULL_RESULT_DRIVER = textwrap.dedent(
    """
    import os, sys
    os.environ["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, os.path.join(__REPO_ROOT__, "src"))
    from rc_metastudio import r_backend
    r_backend.install_r_backend()
    try:
        from rc_metastudio import r_bridge
    except Exception as exc:
        sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
        sys.exit(42)

    assert r_bridge.r_object_to_python(r_bridge.ro.r("NULL")) is None
    null_section_result = r_bridge.ro.r(
        "list(Warning='kept', `Trim-and-fill data`=NULL, References='refs')"
    )
    parsed_null_section = r_bridge.parse_out_results(null_section_result)
    assert "Trim-and-fill data" not in parsed_null_section["texts"]
    assert parsed_null_section["texts"]["Warning"] == "kept"
    nested_section_result = r_bridge.ro.r(
        "list(Warning='kept', Summary='kept summary', `Trim-and-fill data`="
        "list(fit=list(effect=c(0.1, 0.2), se=c(0.05, 0.06)), side='left'), "
        "References='refs')"
    )
    parsed_nested_section = r_bridge.parse_out_results(nested_section_result)
    assert "Trim-and-fill data" not in parsed_nested_section["texts"]
    assert parsed_nested_section["texts"]["Warning"] == "kept"
    assert parsed_nested_section["texts"]["Summary"] == "kept summary"
    sys.stdout.write("OK\\n")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


_RCHAR_UTF8_DRIVER = textwrap.dedent(
    """
    import os
    import sys

    repo_root = __REPO_ROOT__
    os.environ["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    sys.path.insert(0, os.path.join(repo_root, "src"))
    sys.path.insert(0, os.path.join(repo_root, "tests", "python", "fast"))

    from rc_metastudio import r_backend
    r_backend.install_r_backend()
    try:
        from rc_metastudio import r_bridge
    except Exception as exc:
        sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
        sys.exit(42)

    from rpy2.rinterface_lib import conversion, openrlib

    tau_squared = chr(0x03C4) + chr(0x00B2)
    rchar = openrlib.rlib.Rf_mkCharCE(
        conversion.ffi.new("char[]", tau_squared.encode("utf-8")),
        openrlib.rlib.CE_UTF8,
    )
    assert conversion._rchar_to_str(rchar, "cp1252") == tau_squared

    r_result = r_bridge.ro.r(
        '''
        tau_squared <- paste0(intToUtf8(0x03c4), intToUtf8(0x00b2))
        i_squared <- paste0("I", intToUtf8(0x00b2))
        list(Summary=paste(
          "Heterogeneity",
          paste(" ", tau_squared, "     Q(df=12)  Het. p-value       ", i_squared, sep=""),
          " 0.366   163.165       < 0.001  92.645%",
          sep="\\n"
        ))
        '''
    )
    text = r_bridge.parse_out_results(r_result)["texts"]["Summary"]
    assert tau_squared in text, text
    assert "t²" not in text, text

    sys.stdout.write("OK\\n")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


_SUMMARY_PRINT_DRIVER = textwrap.dedent(
    """
    import os
    import shutil
    import subprocess
    import sys
    import tempfile
    import textwrap

    repo_root = __REPO_ROOT__
    r_exe = shutil.which("R")
    if not r_exe:
        sys.stdout.write("SKIP R executable not found\\n")
        sys.exit(42)

    with tempfile.TemporaryDirectory() as r_lib:
        env = dict(os.environ)
        existing_r_libs = env.get("R_LIBS")
        env["R_LIBS"] = (
            r_lib if not existing_r_libs
            else r_lib + os.pathsep + existing_r_libs
        )
        install = subprocess.run(
            [r_exe, "CMD", "INSTALL", "--library=" + r_lib, os.path.join(repo_root, "r", "RCMetaR")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env,
        )
        if install.returncode != 0:
            sys.stdout.write("SKIP R CMD INSTALL RCMetaR failed\\n%s\\n%s\\n" % (install.stdout[-2000:], install.stderr[-2000:]))
            sys.exit(42)

        env["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
        env["R_LIBS"] = (
            r_lib if not existing_r_libs
            else r_lib + os.pathsep + existing_r_libs
        )
        os.environ.update(env)
        sys.path.insert(0, os.path.join(repo_root, "src"))
        sys.path.insert(0, os.path.join(repo_root, "tests", "python", "fast"))

        from rc_metastudio import r_backend
        r_backend.install_r_backend()
        try:
            from rc_metastudio import r_bridge
            r_bridge.RLibraryLoader().load_rcmetar()
        except Exception as exc:
            sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
            sys.exit(42)

        ro = r_bridge.ro
        summary_expr = textwrap.dedent(
            '''
            summary <- structure(
              list(
                model.title = "Binary Random-Effects Model\\\\n\\\\nMetric: Odds Ratio",
                table.titles = c(" Model Results"),
                arrays = list(
                  arr1 = structure(
                    rbind(
                      c("Estimate", "Lower bound", "Upper bound", "p-Value"),
                      c("0.770", "0.485", "1.222", "0.267")
                    ),
                    class = "summary.data"
                  )
                )
              ),
              class = "summary.display"
            )
            paste(capture.output(print(summary)), collapse="\\n")
            '''
        )
        rendered = str(ro.r(summary_expr)[0])
        assert "Binary Random-Effects Model" in rendered, rendered
        assert "Model Results" in rendered, rendered
        assert " Model Results" not in rendered, rendered
        assert "p-value" in rendered, rendered
        assert "p-Value" not in rendered, rendered
        assert "\\n\\n\\n" not in rendered, rendered
        assert "Estimate" in rendered and "0.770" in rendered, rendered
        assert "$model.title" not in rendered, rendered
        assert "$arrays" not in rendered, rendered
        assert 'attr(,"class")' not in rendered, rendered
        assert bool(ro.r('!is.null(getS3method("print", "summary.display", optional=TRUE))')[0])
        assert bool(ro.r('!is.null(getS3method("print", "summary.data", optional=TRUE))')[0])
        assert str(ro.r('RCMetaR:::forest.plot.p.value.label(0.0002, 3)')[0]) == "P< 0.001"
        assert str(ro.r('RCMetaR:::forest.plot.p.value.label(0.015, 3)')[0]) == "P=0.015"

        meta_regression_expr = textwrap.dedent(
            '''
            dir.create("r_tmp", showWarnings=FALSE)
            rcmetar.set.global.conf.level(95)

            regression_display <- RCMetaR:::create.regression.display(
              list(
                b = c(0.1, 0.2),
                ci.lb = c(0.0, 0.1),
                ci.ub = c(0.2, 0.3),
                se = c(0.01, 0.02),
                zval = c(10, 2.5),
                pval = c(0.0002, 0.267),
                method = "REML", test = "z", k = 13, p = 2, m = 1,
                tau2 = 0.0764, se.tau2 = 0.0591, I2 = 68.39, H2 = 3.16, R2 = 75.62,
                QM = 16.3571, QMp = 0.0002, QE = 30.7331, QEp = 0.0012
              ),
              list(digits = 3, measure = "OR", inference.method = "z"),
              list(
                cov.display.col = c("intercept", "latitude"),
                levels.display.col = character(0),
                studies.display.col = character(0),
                factor.n.levels = numeric(0),
                n.cont.covs = 1,
                cont.cov.names = "latitude",
                cont.cov.ranges = list(latitude=c(6, 55)),
                factor.cov.names = character(0),
                factor.ref.levels = character(0)
              )
            )
            regression_text <- paste(capture.output(print(regression_display)), collapse="\\n")
            stopifnot(grepl("< 0.001", regression_text, fixed=TRUE))
            stopifnot(grepl("Heterogeneity explained (R²)", regression_text, fixed=TRUE))
            stopifnot(grepl("Overall moderators (Qₘ)", regression_text, fixed=TRUE))

            advanced_data <- new(
              "BinaryData",
              g1O1=c(6, 3, 19, 26, 8, 6),
              g1O2=c(21, 56, 145, 129, 24, 74),
              g2O1=c(9, 7, 13, 49, 6, 3),
              g2O2=c(18, 57, 139, 96, 29, 73),
              y=c(-0.5596157879, -0.8295982833, 0.3372298124, -0.9291879730, 0.4769240721, 0.6795415285),
              SE=c(0.6172133998, 0.7152562329, 0.3790058736, 0.2775577532, 0.6064784349, 0.7260937568),
              study.names=c("Gonzalez", "Prins", "Maller", "Marik", "Muijsken", "De Vries"),
              years=as.integer(c(1993, 1993, 1993, 1991, 1988, 1990)),
              covariates=list(
                new("CovariateValues", cov.name="year", cov.vals=c(1993, 1993, 1993, 1991, 1988, 1990), cov.type="continuous", ref.var="1993")
              )
            )
            params <- data.frame(
              conf.level=95, digits=3, measure="OR", rm.method="DL", to="only0", adjust=0.5,
              fp_col1_str="Study or Subgroup", fp_col2_str="[default]", fp_col3_str="Ev/Trt", fp_col4_str="Ev/Ctrl",
              fp_xlabel="[default]", fp_outpath="./r_tmp/meta_regression_names_forest.png",
              fp_plot_lb="[default]", fp_plot_ub="[default]", fp_show_col1=TRUE,
              fp_show_col2=TRUE, fp_show_col3=TRUE, fp_show_col4=TRUE,
              fp_show_summary_line=TRUE, fp_xticks="[default]"
            )
            rcmetar.run.analysis(
              advanced_data,
              list(version=1, method="meta.regression", params=params, workflow="meta-regression")
            )
            '''
        )
        meta_reg_result = ro.r(meta_regression_expr)
        parsed_meta_regression = r_bridge.parse_out_results(meta_reg_result)
        regression_summary = parsed_meta_regression["texts"]["Summary"]
        assert "Overall moderators (Qₘ)" in regression_summary, regression_summary
        assert "Residual heterogeneity (Qₑ)" in regression_summary, regression_summary
        assert "Q<U+2098>" not in regression_summary, regression_summary
        assert "Q<U+2091>" not in regression_summary, regression_summary
        weights = parsed_meta_regression["texts"]["Weights"]
        assert weights.splitlines()[0].strip() == "Study names  Weights", weights
        assert "study names" not in weights, weights
        assert "Gonzalez" in weights, weights
        assert "De Vries" in weights, weights
        assert "Study 1" not in weights, weights

        named_weights_result = ro.r(
            '''
            list(
              Weights = structure(c(12.345, 67.89), names = c("Alpha Study", "Beta Study")),
              input_params = list(digits = 3)
            )
            '''
        )
        named_weights = r_bridge.parse_out_results(named_weights_result)["texts"]["Weights"]
        assert named_weights.splitlines()[0].strip() == "Study names  Weights", named_weights
        assert "Alpha Study" in named_weights, named_weights
        assert "Beta Study" in named_weights, named_weights
        assert "Study 1" not in named_weights, named_weights

        sys.stdout.write("OK\\n")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


_ADVANCED_RCMetaR_DRIVER = textwrap.dedent(
    """
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    repo_root = __REPO_ROOT__
    r_exe = shutil.which("R")
    if not r_exe:
        sys.stdout.write("SKIP R executable not found\\n")
        sys.exit(42)

    with tempfile.TemporaryDirectory() as r_lib:
        env = dict(os.environ)
        existing_r_libs = env.get("R_LIBS")
        env["R_LIBS"] = (
            r_lib if not existing_r_libs
            else r_lib + os.pathsep + existing_r_libs
        )
        install = subprocess.run(
            [r_exe, "CMD", "INSTALL", "--library=" + r_lib, os.path.join(repo_root, "r", "RCMetaR")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env,
        )
        if install.returncode != 0:
            sys.stdout.write("SKIP R CMD INSTALL RCMetaR failed\\n%s\\n%s\\n" % (install.stdout[-2000:], install.stderr[-2000:]))
            sys.exit(42)

        env["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
        os.environ.update(env)
        sys.path.insert(0, os.path.join(repo_root, "src"))
        sys.path.insert(0, os.path.join(repo_root, "tests", "python", "fast"))

        from rc_metastudio import r_backend
        r_backend.install_r_backend()
        try:
            from rc_metastudio import r_bridge
            r_bridge.RLibraryLoader().load_rcmetar()
        except Exception as exc:
            sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
            sys.exit(42)

        ro = r_bridge.ro
        ro.r(
            '''
            set.seed(113)
            dir.create("r_tmp", showWarnings=FALSE)
            rcmetar.set.global.conf.level(95)
            advanced_data <- new(
              "BinaryData",
              g1O1=c(6, 3, 19, 26, 8, 6),
              g1O2=c(21, 56, 145, 129, 24, 74),
              g2O1=c(9, 7, 13, 49, 6, 3),
              g2O2=c(18, 57, 139, 96, 29, 73),
              y=c(-0.5596157879, -0.8295982833, 0.3372298124, -0.9291879730, 0.4769240721, 0.6795415285),
              SE=c(0.6172133998, 0.7152562329, 0.3790058736, 0.2775577532, 0.6064784349, 0.7260937568),
              study.names=c("Gonzalez", "Prins", "Maller", "Marik", "Muijsken", "De Vries"),
              years=as.integer(c(1993, 1993, 1993, 1991, 1988, 1990)),
              covariates=list(
                new("CovariateValues", cov.name="year", cov.vals=c(1993, 1993, 1993, 1991, 1988, 1990), cov.type="continuous", ref.var="1993"),
                new("CovariateValues", cov.name="group", cov.vals=c("early", "late", "early", "late", "early", "late"), cov.type="factor", ref.var="early")
              )
            )
            params <- data.frame(
              conf.level=95, digits=3, measure="OR", rm.method="DL", to="only0", adjust=0.5,
              fp_col1_str="Study or Subgroup", fp_col2_str="[default]", fp_col3_str="Ev/Trt", fp_col4_str="Ev/Ctrl",
              fp_xlabel="[default]", fp_outpath="./r_tmp/issue113_forest.png",
              fp_plot_lb="[default]", fp_plot_ub="[default]", fp_show_col1=TRUE,
              fp_show_col2=TRUE, fp_show_col3=TRUE, fp_show_col4=TRUE,
              fp_show_summary_line=TRUE, fp_xticks="[default]",
              bootstrap.type="boot.ma", num.bootstrap.replicates=25,
              bootstrap.plot.path="./r_tmp/issue113_bootstrap.png",
              histogram.title="Bootstrap", histogram.xlab="Effect"
            )
            boot.result <- rcmetar.run.analysis(
              advanced_data,
              list(version=1, method="binary.random", params=params, workflow="bootstrap")
            )
            stopifnot("Summary" %in% names(boot.result))
            stopifnot("Histogram" %in% names(boot.result$images))
            stopifnot(file.exists(boot.result$images[["Histogram"]]))

            params$bootstrap.type <- "boot.meta.reg"
            params$bootstrap.plot.path <- "./r_tmp/issue113_bootstrap_meta_reg.png"
            boot.reg.result <- rcmetar.run.analysis(
              advanced_data,
              list(version=1, method="binary.random", params=params, workflow="bootstrap")
            )
            stopifnot("Summary" %in% names(boot.reg.result))
            stopifnot("Histograms" %in% names(boot.reg.result$images))
            stopifnot(file.exists(boot.reg.result$images[["Histograms"]]))

            perm.data <- data.frame(
              yi=advanced_data@y,
              vi=advanced_data@SE^2,
              slab=advanced_data@study.names,
              year=advanced_data@covariates[[1]]@cov.vals
            )
            perm.ma <- rcmetar.run.permutation(perm.data, method="DL", iter=20, digits=3)
            stopifnot("Summary" %in% names(perm.ma))
            stopifnot(nchar(perm.ma$Summary) > 0)

            perm.reg <- rcmetar.run.permutation(
              perm.data,
              method="DL",
              mods=list(numeric=c("year"), categorical=c(), interactions=list()),
              iter=20,
              digits=3
            )
            stopifnot("Standard Meta Regression Summary" %in% names(perm.reg))
            stopifnot("Permuted Meta-Regression Summary" %in% names(perm.reg))
            stopifnot(grepl("Coefficient table", perm.reg[["Standard Meta Regression Summary"]]))
            '''
        )

        ro.r(
            '''
            funnel_data <- new(
              "ContinuousData",
              y=seq(-0.4, 0.5, length.out=11),
              SE=seq(0.08, 0.22, length.out=11),
              study.names=paste0("funnel-study-", 1:11),
              years=as.integer(2010:2020)
            )
            funnel_result <- rcmetar.run.small.study.effects(
              funnel_data,
              list(
                version=1L,
                data.type="continuous", metric="MD",
                funnels=c("ordinary", "contour"),
                tests=c("mixed-effects-egger", "begg-mazumdar"), conf.level=95,
                `funnel.point.size`=c(1.0, 1.0)
              )
            )
            funnel_base <- unname(funnel_result$plot_params_paths[["Contour Funnel Plot"]])
            funnel_image <- unname(funnel_result$images[["Contour Funnel Plot"]])
            '''
        )
        funnel_base = str(ro.globalenv["funnel_base"][0])
        funnel_image = str(ro.globalenv["funnel_image"][0])
        assert os.path.exists(funnel_image)
        assert os.path.getsize(funnel_image) > 0
        parsed_funnel_result = r_bridge.parse_out_results(
            ro.globalenv["funnel_result"]
        )
        assert "Method details" in parsed_funnel_result["texts"]
        method_details = parsed_funnel_result["texts"]["Method details"]
        assert "Package:" in method_details
        assert (
            "Weighting: inverse-variance weights with REML heterogeneity"
            in method_details
        )
        assert "Inference: z test from metafor::regtest" in method_details
        assert "Weighting: not applicable (Kendall rank-based test)" in method_details
        assert "Inference: z test from Kendall rank correlation" in method_details
        funnel_params = r_bridge.load_vars_for_plot(
            funnel_base, return_params_dict=True
        )
        assert len(funnel_params["prepared.effects"]) == 11
        funnel_params["funnel.point.size"] = [1.5, 2.5]
        r_bridge.update_plot_params(
            funnel_params,
            write_them_out=True,
            outpath=funnel_base + ".params",
        )
        with tempfile.TemporaryDirectory(prefix="rcmetar-funnel-edit-") as edit_dir:
            regenerated_funnel = os.path.join(edit_dir, "contour.png")
            r_bridge.regenerate_small_study_effects_funnel(
                funnel_base, output_path=regenerated_funnel
            )
            assert os.path.exists(regenerated_funnel)
            assert os.path.getsize(regenerated_funnel) > 0

        sys.stdout.write("OK\\n")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


def test_RCMetaR_advanced_bootstrap_and_permutation_paths_execute():
    env = dict(os.environ)
    env["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    run_python_driver(_ADVANCED_RCMetaR_DRIVER, env=env)


def test_inprocess_rpy2_backend_contract():
    # Require the real in-process rpy2 path in this integration driver.
    env = dict(os.environ)
    env["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    result = run_python_driver(_DRIVER, env=env)
    combined_output = result.stdout + result.stderr
    assert "UnicodeDecodeError" not in combined_output
    assert "replacement element" not in combined_output


def test_rpy2_r_character_conversion_preserves_utf8_before_native_codepage():
    env = dict(os.environ)
    env["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    run_python_driver(_RCHAR_UTF8_DRIVER, env=env)


def test_r_null_result_sections_are_omitted_before_formatting():
    env = dict(os.environ)
    run_python_driver(_NULL_RESULT_DRIVER, env=env)


def test_RCMetaR_summary_capture_uses_formatted_print_methods():
    env = dict(os.environ)
    env["RCMS_REQUIRE_IN_PROCESS_RPY2"] = "1"
    run_python_driver(_SUMMARY_PRINT_DRIVER, env=env)
