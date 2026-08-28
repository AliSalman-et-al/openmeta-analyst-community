import textwrap

from ._r_driver_support import build_r_driver, run_r_driver


_BIVARIATE_SUMMARY_DRIVER = textwrap.dedent(
    r"""
    __RCMETAR_BOOTSTRAP__
    required <- c("metafor", "HSROC", "boot")
    missing <- required[!vapply(required, requireNamespace, logical(1), quietly=TRUE)]
    if (length(missing) > 0) {
      cat("SKIP missing R packages:", paste(missing, collapse=", "), "\n")
      quit(status=42)
    }

    work <- tempfile("bivariate_summary_")
    dir.create(work)
    dir.create(file.path(work, "r_tmp"))
    setwd(work)

    bivariate.dx.test <- function(TP, FP, FN, TN) {
      data.frame(
        logit_sens = qlogis(0.674),
        logist_spec = qlogis(0.8373),
        se_logit_sens = 0.180,
        se_logit_spec = 0.246,
        var_sens = 0.1,
        var_spec = 0.2,
        covar = 0.03,
        correlation = 0.2421
      )
    }
    plot.bivariate <- function(..., filepath="./r_tmp/bivariate") {
      png(file = paste(filepath, ".png", sep=""), height=240, width=240)
      plot.new()
      dev.off()
      pdf(file = paste(filepath, ".pdf", sep=""))
      plot.new()
      dev.off()
      invisible(NULL)
    }

    diagnostic.data <- new(
      "DiagnosticData",
      TP=c(19, 8, 41, 5, 45),
      FN=c(10, 2, 12, 2, 32),
      TN=c(81, 13, 49, 18, 165),
      FP=c(1, 9, 1, 1, 58)
    )
    params <- list(conf.level=95, adjust=.5, to="only0")

    result <- diagnostic.bivariate.ml(diagnostic.data, params)
    if (!is.list(result$Summary) || !"Bivariate Summary" %in% names(result$Summary)) {
      stop("bivariate result did not expose a named Bivariate Summary section")
    }
    if (!"ROC Plot" %in% names(result$images)) {
      stop("bivariate result did not expose a named ROC Plot artifact")
    }
    if (!grepl("\\.png$", result$images[["ROC Plot"]])) {
      stop(paste("ROC Plot should point to the generated PNG artifact, got:", result$images[["ROC Plot"]]))
    }
    if (!file.exists(result$images[["ROC Plot"]])) {
      stop(paste("ROC Plot artifact path does not exist:", result$images[["ROC Plot"]]))
    }

    rendered <- result$Summary[["Bivariate Summary"]]
    if (!is.character(rendered) || length(rendered) != 1) {
      stop("Bivariate Summary should be a single preformatted text section")
    }
    if (grepl("\\bV1\\b|\\bV2\\b|\\bV3\\b|\\bV4\\b", rendered)) {
      stop(paste("placeholder R column names leaked into Bivariate Summary:\n", rendered))
    }
    if (grepl("----", rendered)) {
      stop(paste("default matrix rule leaked into Bivariate Summary:\n", rendered))
    }
    for (expected in c("Estimate", "Lower bound", "Upper bound",
                       "Sensitivity", "Specificity", "Correlation",
                       "0.67", "0.84", "0.24")) {
      if (!grepl(expected, rendered, fixed=TRUE)) {
        stop(paste("missing expected text", expected, "in:\n", rendered))
      }
    }
    if (grepl("0.6740|0.8373|0.2421", rendered)) {
      stop(paste("Bivariate Summary should use the configured two-decimal precision:\n", rendered))
    }

    cat("OK\n")
    """
)
_BIVARIATE_SUMMARY_DRIVER = build_r_driver(_BIVARIATE_SUMMARY_DRIVER)


def test_bivariate_summary_is_preformatted_without_r_placeholder_headers():
    run_r_driver(_BIVARIATE_SUMMARY_DRIVER)
