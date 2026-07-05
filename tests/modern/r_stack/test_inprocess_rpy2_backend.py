"""Regression tests for the in-process rpy2 backend porting layer.

When the modern build runs the real (in-process) rpy2 backend, five
Python-3 / rpy2-3.x incompatibilities each broke the Python<->R boundary and
made analyses dead-end:

1. Dead latin-1 sanitizers and R-source construction paths stripped or rejected
   non-Latin-1 user text before it reached R.

2. rpy2 >= 3.x represents R's NULL as a ``NULLType`` whose ``str()`` is an
   object repr, not the literal ``"NULL"``. NULL detection done via
   ``str(x) == "NULL"`` silently misfired (e.g. treating a list with NULL
   names as a named list), raising ``'NULLType' object is not iterable``.

3. Subgroup forest plots can compute vector-valued plot parameters such as
   ``fp_xticks``. Assigning those vectors directly into the one-row R params
   data frame emitted the "replacement element ... rows to replace 1 rows"
   warning and left saved plot params in an inconsistent shape.

4. rpy2 asks R to translate CHARSXP values through the native Windows codepage
   when the Python encoding is cp1252. R's native translation maps ``τ`` to
   ASCII ``t`` while preserving ``²``, so the heterogeneity label ``τ²``
   reached Python and the results window as ``t²``.

Because importing the real ``meta_py_r`` initialises embedded R, this runs in a
subprocess and skips when the in-process backend (R/rpy2) is unavailable, so it
exercises the fixes locally without disturbing the stub-backed tests.
"""

import os
import subprocess
import sys
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


_DRIVER = textwrap.dedent(
    """
    import os, sys
    os.environ["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    sys.path.insert(0, os.path.join(__REPO_ROOT__, "src"))

    import modern_compat
    modern_compat.install()
    try:
        import meta_py_r
        meta_py_r.RlibLoader().load_OpenMetaR()
    except Exception as exc:
        # R / rpy2 / OpenMetaR not available in this environment.
        sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
        sys.exit(42)

    ro = meta_py_r.ro

    # Fix 1: non-Latin-1 user text must remain valid text at the R boundary.
    assert not hasattr(meta_py_r, "_sanitize_for_R")

    # Fix 2: NULL detection works against rpy2's NULLType.
    assert meta_py_r._r_is_null(ro.r("list()").names) is True
    assert meta_py_r._r_is_null(ro.r("c(a=1)").names) is False

    # Fix 4: R character scalars must reach Python as UTF-8 instead of first
    # passing through cp1252/native translation, which maps τ² to t².
    from rpy2.rinterface_lib import conversion, openrlib

    tau_squared = chr(0x03C4) + chr(0x00B2)
    rchar = openrlib.rlib.Rf_mkCharCE(
        conversion.ffi.new("char[]", tau_squared.encode("utf-8")),
        openrlib.rlib.CE_UTF8,
    )
    assert conversion._rchar_to_str(rchar, "cp1252") == tau_squared

    # End-to-end through the core porting fixes: get_params parses a real method's
    # partly NULL-named parameter structure.
    params, defaults, var_order, pretty = meta_py_r.get_params("binary.random")
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

        def get_values_for_cov(self, covariate, ids_for_keys=False):
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
                FakeCovariate('Group "label" \\\\ café τ', meta_py_r.FACTOR),
                FakeCovariate("Dose", meta_py_r.CONTINUOUS),
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

        def get_cur_ests_and_SEs(self, **kwargs):
            return [-0.5596157879, -0.8295982833], [0.6172133998, 0.7152562329]

        def included_studies_have_raw_data(self):
            return True

        def get_cur_raw_data(self, **kwargs):
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

    quoted_values_str, quoted_values = meta_py_r.cov_to_str(
        FakeCovariate("region", meta_py_r.FACTOR),
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
        return_cov_vals=True,
    )
    assert quoted_values == ["'control \\\\u03c4'", "'O\\\\'Brien \\\\\\\\ north'"]
    assert list(ro.r(quoted_values_str)) == ["control τ", "O'Brien \\\\ north"]

    binary_model = FakeModel("binary", [[6, 27, 9, 27], [3, 59, 7, 64]])
    meta_py_r.ma_dataset_to_simple_binary_robj(binary_model, var_name="issue146_binary")
    assert_text_survived("issue146_binary")

    continuous_model = FakeModel(
        "continuous",
        [[27, 5.1, 1.2, 27, 6.2, 1.5], [59, 3.4, 0.9, 64, 4.1, 1.1]],
        effect="MD",
    )
    meta_py_r.ma_dataset_to_simple_continuous_robj(
        continuous_model,
        var_name="issue146_continuous",
    )
    assert_text_survived("issue146_continuous")

    diagnostic_model = FakeModel("diagnostic", [[6, 21, 9, 18], [3, 56, 7, 57]])
    meta_py_r.ma_dataset_to_simple_diagnostic_robj(
        diagnostic_model,
        var_name="issue146_diagnostic",
    )
    assert_text_survived("issue146_diagnostic")

    invalid_conf_level_checks = ro.r('''
      c(
        inherits(try(openmetar.set.global.conf.level(100), silent=TRUE), "try-error"),
        inherits(try(openmetar.get.mult.from.conf.level(100), silent=TRUE), "try-error"),
        inherits(try(openmetar.get.mult.from.conf.level(0), silent=TRUE), "try-error"),
        inherits(try(openmetar.get.mult.from.conf.level(Inf), silent=TRUE), "try-error")
      )
    ''')
    assert all(bool(value) for value in invalid_conf_level_checks)

    import golden_analysis

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


_RCHAR_UTF8_DRIVER = textwrap.dedent(
    """
    import os
    import sys

    repo_root = __REPO_ROOT__
    os.environ.pop("OMA_STUB_BACKEND", None)
    os.environ["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    sys.path.insert(0, os.path.join(repo_root, "src"))

    import modern_compat
    modern_compat.install()
    try:
        import meta_py_r
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

    r_result = meta_py_r.ro.r(
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
    text = meta_py_r.parse_out_results(r_result)["texts"]["Summary"]
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
            [r_exe, "CMD", "INSTALL", "--library=" + r_lib, os.path.join(repo_root, "src", "R", "OpenMetaR")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env,
        )
        if install.returncode != 0:
            sys.stdout.write("SKIP R CMD INSTALL OpenMetaR failed\\n%s\\n%s\\n" % (install.stdout[-2000:], install.stderr[-2000:]))
            sys.exit(42)

        env.pop("OMA_STUB_BACKEND", None)
        env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
        env["R_LIBS"] = (
            r_lib if not existing_r_libs
            else r_lib + os.pathsep + existing_r_libs
        )
        os.environ.update(env)
        sys.path.insert(0, os.path.join(repo_root, "src"))

        import modern_compat
        modern_compat.install()
        try:
            import meta_py_r
            meta_py_r.RlibLoader().load_OpenMetaR()
        except Exception as exc:
            sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
            sys.exit(42)

        ro = meta_py_r.ro
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
        assert str(ro.r('OpenMetaR:::forest.plot.p.value.label(0.0002, 3)')[0]) == "P< 0.001"
        assert str(ro.r('OpenMetaR:::forest.plot.p.value.label(0.015, 3)')[0]) == "P=0.015"

        meta_regression_expr = textwrap.dedent(
            '''
            dir.create("r_tmp", showWarnings=FALSE)
            openmetar.set.global.conf.level(95)

            regression_display <- OpenMetaR:::create.regression.display(
              list(
                b = c(0.1, 0.2),
                ci.lb = c(0.0, 0.1),
                ci.ub = c(0.2, 0.3),
                se = c(0.01, 0.02),
                pval = c(0.0002, 0.267),
                QMp = 0.0002
              ),
              list(digits = 3, measure = "OR"),
              list(
                cov.display.col = c("intercept", "latitude"),
                levels.display.col = character(0),
                studies.display.col = character(0),
                factor.n.levels = numeric(0),
                n.cont.covs = 1
              )
            )
            regression_text <- paste(capture.output(print(regression_display)), collapse="\\n")
            stopifnot(grepl("< 0.001", regression_text, fixed=TRUE))
            stopifnot(!grepl("Omnibus p-value\\\\n 0.000", regression_text))

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
              fp_col1_str="Studies", fp_col2_str="[default]", fp_col3_str="Ev/Trt", fp_col4_str="Ev/Ctrl",
              fp_xlabel="[default]", fp_outpath="./r_tmp/meta_regression_names_forest.png",
              fp_plot_lb="[default]", fp_plot_ub="[default]", fp_show_col1=TRUE,
              fp_show_col2=TRUE, fp_show_col3=TRUE, fp_show_col4=TRUE,
              fp_show_summary_line=TRUE, fp_xticks="[default]"
            )
            openmetar.run.analysis(
              advanced_data,
              list(method="meta.regression", params=params, workflow="meta-regression")
            )
            '''
        )
        meta_reg_result = ro.r(meta_regression_expr)
        parsed_meta_regression = meta_py_r.parse_out_results(meta_reg_result)
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
        named_weights = meta_py_r.parse_out_results(named_weights_result)["texts"]["Weights"]
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


_HSROC_SUMMARY_DRIVER = textwrap.dedent(
    """
    import os
    import sys

    repo_root = __REPO_ROOT__
    os.environ.pop("OMA_STUB_BACKEND", None)
    os.environ["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    sys.path.insert(0, os.path.join(repo_root, "src"))

    import modern_compat
    modern_compat.install()
    try:
        import meta_py_r
    except Exception as exc:
        sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
        sys.exit(42)

    ro = meta_py_r.ro
    r_result = ro.r(
        '''
        list(
          images = list(),
          `Between-study parameters` = structure(
            c(0.624, 1.110, 0.817, 1.907, 1.493, 1.356),
            dim = c(2, 3),
            dimnames = list(
              c("THETA", "LAMBDA"),
              c("Median estimate", "HPD.low", "HPD.high")
            )
          ),
          `Within-study parameters` = structure(
            1:27,
            dim = c(3, 3, 3),
            dimnames = list(
              c("1", "2", "3"),
              c("Median estimate", "HPD lower", "HPD upper"),
              c("theta", "alpha", "pi")
            )
          )
        )
        '''
    )

    parsed = meta_py_r.parse_out_results(r_result)
    texts = parsed["texts"]
    assert "Summary" not in texts, texts
    assert "Between-study parameters" in texts, texts
    assert "Within-study parameters - theta" in texts, texts
    assert "Within-study parameters - alpha" in texts, texts
    assert "Within-study parameters - pi" in texts, texts

    combined = "\\n".join(texts.values())
    assert "$`Between-study parameters`" not in combined, combined
    assert "$`Within-study parameters`" not in combined, combined
    assert ", , theta" not in combined, combined
    assert ", , alpha" not in combined, combined
    assert ", , pi" not in combined, combined
    assert not texts["Between-study parameters"].startswith(
        "Between-study parameters\\n"
    ), texts
    assert not texts["Within-study parameters - theta"].startswith(
        "Within-study parameters - theta\\n"
    ), texts
    assert "Lower bound" in texts["Between-study parameters"], texts
    assert "Upper bound" in texts["Between-study parameters"], texts
    assert "HPD.low" not in texts["Between-study parameters"], texts
    assert "HPD lower" not in texts["Within-study parameters - theta"], texts
    assert "THETA" in texts["Between-study parameters"], texts
    assert "Median estimate" in texts["Within-study parameters - theta"], texts
    assert "3" in texts["Within-study parameters - alpha"], texts

    direct_summary = ro.r(
        '''
        list(
          Summary = list(
            `Bivariate Summary` = paste(
              "Bivariate Summary",
              "Estimate HPD.low HPD.high",
              "Fallback ci.lb ci.ub lower.bound upper.bound Lower Bound Upper Bound",
              sep="\\n"
            ),
            `Other Summary` = "HPD lower HPD upper"
          ),
          `Raw Text Summary` = "ci.lb ci.ub"
        )
        '''
    )
    parsed_direct = meta_py_r.parse_out_results(direct_summary)
    direct_text = "\\n".join(parsed_direct["texts"].values())
    for raw_header in (
        "HPD.low",
        "HPD.high",
        "HPD lower",
        "HPD upper",
        "ci.lb",
        "ci.ub",
        "lower.bound",
        "upper.bound",
        "Lower Bound",
        "Upper Bound",
    ):
        assert raw_header not in direct_text, parsed_direct
    assert "Estimate Lower bound Upper bound" in direct_text, parsed_direct
    assert "Fallback Lower bound Upper bound Lower bound Upper bound Lower bound Upper bound" in direct_text, parsed_direct
    assert parsed_direct["texts"]["Other Summary"] == "Lower bound Upper bound", parsed_direct
    assert parsed_direct["texts"]["Raw Text Summary"] == "Lower bound Upper bound", parsed_direct

    classes_path = os.path.join(repo_root, "src", "R", "OpenMetaR", "R", "classes.r")
    ro.r("source(%r)" % classes_path.replace(os.sep, "/"))
    context_summary = ro.r(
        '''
        list(
          input_data = new(
            "DiagnosticData",
            TP=c(19, 8),
            FN=c(10, 2),
            TN=c(81, 13),
            FP=c(1, 9),
            study.names=c("Lecart Lenfant", "Piver Barlow")
          ),
          Summary = list(
            `diagnostic.random` = structure(
              c(0.11, 0.22, 0.01, 0.02, 0.21, 0.32),
              dim = c(2, 3),
              dimnames = list(
                c("Study 1", "Study 2"),
                c("median estimate", "ci.lb", "ci.ub")
              )
            )
          )
        )
        '''
    )
    parsed_context = meta_py_r.parse_out_results(context_summary)
    assert "Diagnostic Random-Effects" in parsed_context["texts"], parsed_context
    context_text = parsed_context["texts"]["Diagnostic Random-Effects"]
    assert "Lecart Lenfant" in context_text, parsed_context
    assert "Piver Barlow" in context_text, parsed_context
    assert "Study 1" not in context_text, parsed_context
    assert "diagnostic.random" not in parsed_context["texts"], parsed_context
    assert "Lower bound" in context_text, parsed_context
    assert "ci.lb" not in context_text, parsed_context

    sys.stdout.write("OK\\n")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


_ADVANCED_OPENMETAR_DRIVER = textwrap.dedent(
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
            [r_exe, "CMD", "INSTALL", "--library=" + r_lib, os.path.join(repo_root, "src", "R", "OpenMetaR")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env,
        )
        if install.returncode != 0:
            sys.stdout.write("SKIP R CMD INSTALL OpenMetaR failed\\n%s\\n%s\\n" % (install.stdout[-2000:], install.stderr[-2000:]))
            sys.exit(42)

        env.pop("OMA_STUB_BACKEND", None)
        env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
        os.environ.update(env)
        sys.path.insert(0, os.path.join(repo_root, "src"))

        import modern_compat
        modern_compat.install()
        try:
            import meta_py_r
            meta_py_r.RlibLoader().load_OpenMetaR()
        except Exception as exc:
            sys.stdout.write("SKIP %s: %s\\n" % (exc.__class__.__name__, exc))
            sys.exit(42)

        ro = meta_py_r.ro
        ro.r(
            '''
            set.seed(113)
            dir.create("r_tmp", showWarnings=FALSE)
            openmetar.set.global.conf.level(95)
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
              fp_col1_str="Studies", fp_col2_str="[default]", fp_col3_str="Ev/Trt", fp_col4_str="Ev/Ctrl",
              fp_xlabel="[default]", fp_outpath="./r_tmp/issue113_forest.png",
              fp_plot_lb="[default]", fp_plot_ub="[default]", fp_show_col1=TRUE,
              fp_show_col2=TRUE, fp_show_col3=TRUE, fp_show_col4=TRUE,
              fp_show_summary_line=TRUE, fp_xticks="[default]",
              bootstrap.type="boot.ma", num.bootstrap.replicates=25,
              bootstrap.plot.path="./r_tmp/issue113_bootstrap.png",
              histogram.title="Bootstrap", histogram.xlab="Effect"
            )
            boot.result <- openmetar.run.analysis(
              advanced_data,
              list(method="binary.random", params=params, workflow="bootstrap")
            )
            stopifnot("Summary" %in% names(boot.result))
            stopifnot("Histogram" %in% names(boot.result$images))
            stopifnot(file.exists(boot.result$images[["Histogram"]]))

            params$bootstrap.type <- "boot.meta.reg"
            params$bootstrap.plot.path <- "./r_tmp/issue113_bootstrap_meta_reg.png"
            boot.reg.result <- openmetar.run.analysis(
              advanced_data,
              list(method="binary.random", params=params, workflow="bootstrap")
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
            perm.ma <- openmetar.run.permutation(perm.data, method="DL", iter=20, digits=3)
            stopifnot("Summary" %in% names(perm.ma))
            stopifnot(nchar(perm.ma$Summary) > 0)

            perm.reg <- openmetar.run.permutation(
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

        sys.stdout.write("OK\\n")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT))


def test_inprocess_rpy2_backend_python3_porting_fixes():
    # Force the real in-process backend: the surrounding test suite sets
    # OMA_STUB_BACKEND=1 (which selects the no-R stub), so clear it in the child
    # env and require the real rpy2 path instead.
    env = dict(os.environ)
    env.pop("OMA_STUB_BACKEND", None)
    env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )
    if result.returncode == 42:
        pytest.skip("in-process rpy2 backend unavailable: %s" % result.stdout.strip())
    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout
    combined_output = result.stdout + result.stderr
    assert "UnicodeDecodeError" not in combined_output
    assert "replacement element" not in combined_output


def test_rpy2_r_character_conversion_preserves_utf8_before_native_codepage():
    env = dict(os.environ)
    env.pop("OMA_STUB_BACKEND", None)
    env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c", _RCHAR_UTF8_DRIVER],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )
    if result.returncode == 42:
        pytest.skip("in-process rpy2 backend unavailable: %s" % result.stdout.strip())
    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout


def test_openmetar_summary_capture_uses_formatted_print_methods():
    env = dict(os.environ)
    env.pop("OMA_STUB_BACKEND", None)
    env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", _SUMMARY_PRINT_DRIVER],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )
    if result.returncode == 42:
        pytest.skip(
            "OpenMetaR summary print regression unavailable: %s" % result.stdout.strip()
        )
    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout


def test_hsroc_direct_table_summaries_expand_to_formatted_sections():
    env = dict(os.environ)
    env.pop("OMA_STUB_BACKEND", None)
    env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", _HSROC_SUMMARY_DRIVER],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )
    if result.returncode == 42:
        pytest.skip(
            "HSROC summary formatting regression unavailable: %s"
            % result.stdout.strip()
        )
    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout


def test_openmetar_advanced_bootstrap_and_permutation_paths_execute():
    env = dict(os.environ)
    env.pop("OMA_STUB_BACKEND", None)
    env["OMA_REQUIRE_IN_PROCESS_RPY2"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", _ADVANCED_OPENMETAR_DRIVER],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )
    if result.returncode == 42:
        pytest.skip(
            "advanced OpenMetaR workflow regression unavailable: %s"
            % result.stdout.strip()
        )
    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout
