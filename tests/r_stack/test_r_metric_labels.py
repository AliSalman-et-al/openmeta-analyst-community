import textwrap

from _r_driver_support import REPO_ROOT, run_r_driver


_METRIC_LABEL_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    suppressPackageStartupMessages(source(file.path(repo, "r/RCMetaR/R/plotting.R")))

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
    run_r_driver(_METRIC_LABEL_DRIVER)
