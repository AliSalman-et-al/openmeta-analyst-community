import os
import shutil
import subprocess
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


_METRIC_LABEL_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    suppressPackageStartupMessages(source(file.path(repo, "src/R/RCMetaR/R/plotting.r")))

    expected <- list(
      OR = "Odds Ratio",
      MD = "Mean Difference",
      GEN = "Generic Effect",
      TXMean = "TX Mean",
      "TX Mean" = "TX Mean",
      "TX.Mean" = "TX Mean",
      " TX Mean " = "TX Mean"
    )

    for (metric in names(expected)) {
      actual <- pretty.metric.name(metric)
      if (!identical(actual, expected[[metric]])) {
        stop(sprintf(
          "pretty.metric.name(%s) returned %s; expected %s",
          sQuote(metric),
          if (is.null(actual)) "<NULL>" else sQuote(actual),
          sQuote(expected[[metric]])
        ))
      }
    }

    cat("OK\n")
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/"))


def test_pretty_metric_name_handles_tx_mean_separator_variants():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript executable not found")

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=_METRIC_LABEL_DRIVER,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    assert result.returncode == 0, "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s" % (
        result.returncode,
        result.stdout[-2000:],
        result.stderr[-2000:],
    )
    assert "OK" in result.stdout
