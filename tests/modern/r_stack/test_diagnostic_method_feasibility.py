import os
import shutil
import subprocess
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


_DIAGNOSTIC_FEASIBILITY_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    required <- c("metafor", "HSROC")
    missing <- required[!vapply(required, requireNamespace, logical(1), quietly=TRUE)]
    if (length(missing) > 0) {
      cat("SKIP missing R packages:", paste(missing, collapse=", "), "\n")
      quit(status=42)
    }

    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/classes.r")))
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/utilities.r")))
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/diagnostic_methods.r")))

    entered.effects <- new(
      "DiagnosticData",
      y=c(qlogis(0.65), qlogis(0.80), qlogis(0.77), qlogis(0.71), qlogis(0.58)),
      SE=c(0.14, 0.18, 0.09, 0.26, 0.08),
      study.names=c("a", "b", "c", "d", "e")
    )

    count.data <- new(
      "DiagnosticData",
      TP=c(19, 8, 41, 5, 45),
      FN=c(10, 2, 12, 2, 32),
      TN=c(81, 13, 49, 18, 165),
      FP=c(1, 9, 1, 1, 58)
    )

    if (diagnostic.hsroc.is.feasible(entered.effects, "Sens")) {
      stop("HSROC should not be feasible for entered diagnostic effects")
    }
    if (diagnostic.bivariate.ml.is.feasible(entered.effects, "Sens")) {
      stop("bivariate ML should not be feasible for entered diagnostic effects")
    }
    if (!diagnostic.hsroc.is.feasible(count.data, "Sens")) {
      stop("HSROC should be feasible for count-based diagnostic data with at least five studies")
    }
    if (!identical(diagnostic.hsroc.ml.is.feasible, diagnostic.hsroc.is.feasible)) {
      stop("legacy HSROC feasibility alias should delegate to the method-discovery hook")
    }

    cat("OK\n")
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/"))


def test_count_based_diagnostic_methods_require_counts():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript executable not found")

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=_DIAGNOSTIC_FEASIBILITY_DRIVER,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    if result.returncode == 42:
        pytest.skip(result.stdout.strip())

    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout
