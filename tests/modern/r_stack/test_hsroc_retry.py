import os
import shutil
import subprocess
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


_HSROC_RETRY_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/classes.r")))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/utilities.r")))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/diagnostic_methods.r")))

    work <- tempfile("hsroc_retry_")
    dir.create(work)
    dir.create(file.path(work, "r_tmp"))
    setwd(work)

    run.case <- function(mode) {
      calls <<- c()
      summary.chains <<- c()
      current.mode <<- mode

      write.valid.chain <- function(path) {
        for (file.name in hsroc.required.chain.files()) {
          write(c(0.1, 0.2, 0.3), file=file.path(path, file.name), ncolumns=1)
        }
      }

      fake.HSROC <- function(..., path) {
        calls <<- c(calls, path)
        if (mode == "fresh-init" && length(calls) == 1) {
          stop("simulated transient HSROC failure")
        }
        if (mode == "non-finite-init" && length(calls) == 1) {
          write.valid.chain(path)
          write(c(0.1, NaN, 0.3), file=file.path(path, "theta.txt"), ncolumns=1)
          return(invisible(NULL))
        }
        if (mode == "fatal") {
          stop("simulated unrecoverable validation failure")
        }
        write.valid.chain(path)
        invisible(NULL)
      }
      assign("HSROC", fake.HSROC, envir=.GlobalEnv)

      result <- diagnostic.hsroc(diagnostic.data, params)
      result
    }

    hsroc.rasterize.pdf <- function(pdf.path) {
      png.path <- sub("[.]pdf$", ".png", pdf.path)
      png(filename=png.path, width=120, height=120)
      par(mar=c(0, 0, 0, 0))
      plot.new()
      dev.off()
      png.path
    }

    HSROCSummary <- function(..., chain, summary.path) {
      summary.chains <<- chain
      file.create(file.path(summary.path, "Summary ROC curve.pdf"))
      file.create(file.path(summary.path, "Density plots for N = 9 .pdf"))
      file.create(file.path(summary.path, "Trace plots for N = 9 .pdf"))
      between.study <- matrix(
        c(0.8, 0.7,
          0.5, 0.4,
          0.9, 0.8),
        nrow=2
      )
      rownames(between.study) <- c("Sensitivity (new)", "Specificity (new)")
      colnames(between.study) <- c("median estimate", "HPD.low", "HPD.high")
      if (identical(current.mode, "bad-summary")) {
        between.study["Specificity (new)", "median estimate"] <- 0.8
        between.study["Specificity (new)", "HPD.low"] <- 0.5
        between.study["Specificity (new)", "HPD.high"] <- 0
      }
      if (identical(current.mode, "bad-other-summary")) {
        between.study["Sensitivity (new)", "median estimate"] <- 0.8
        between.study["Sensitivity (new)", "HPD.low"] <- 0.5
        between.study["Sensitivity (new)", "HPD.high"] <- 0
      }
      list(
        `Between-study parameters` = between.study,
        `Within-study parameters` = array(1:8, dim=c(2, 2, 2)),
        "See summary directory for complete results"
      )
    }

    diagnostic.data <- new(
      "DiagnosticData",
      TP=c(19, 8, 41, 5, 45),
      FN=c(10, 2, 12, 2, 32),
      TN=c(81, 13, 49, 18, 165),
      FP=c(1, 9, 1, 1, 58)
    )
    params <- list(
      num.chains=1,
      num.iters=10,
      burn.in=1,
      thin=1,
      lambda.lower=-2,
      lambda.upper=2,
      theta.lower=-2,
      theta.upper=2
    )

    result <- run.case("fresh-init")

    if (!is.list(result) || !"Summary" %in% names(result)) {
      stop("diagnostic.hsroc did not return a result list after clean retry")
    }
    if (length(calls) != 2) {
      stop(paste("unexpected clean retry call count:", length(calls)))
    }
    if (!grepl("chain_1_retry_1$", calls[[2]])) {
      stop(paste("clean retry did not use retry directory:", calls[[2]]))
    }
    if (!identical(summary.chains, calls[[2]])) {
      stop("HSROCSummary did not use the successful retry directory")
    }
    expected.images <- c("Summary ROC", "Density plots", "Trace plots")
    if (!identical(names(result$images), expected.images)) {
      stop(paste("diagnostic.hsroc did not expose the expected HSROC plots:", paste(names(result$images), collapse=", ")))
    }
    if (!identical(result$image_order, expected.images)) {
      stop(paste("diagnostic.hsroc image_order did not match available images:", paste(result$image_order, collapse=", ")))
    }
    if (any(grepl("[.]pdf$", unlist(result$images)))) {
      stop(paste("diagnostic.hsroc should expose rasterized plot paths, got:", paste(unlist(result$images), collapse=", ")))
    }
    if (!all(file.exists(unlist(result$images)))) {
      stop(paste("diagnostic.hsroc exposed missing plot paths:", paste(unlist(result$images), collapse=", ")))
    }
    if (!"Clinical Accuracy Summary" %in% names(result$Summary)) {
      stop("diagnostic.hsroc did not expose a clinically labelled HSROC summary")
    }
    clinical.summary <- result$Summary[["Clinical Accuracy Summary"]]
    expected.labels <- c(
      "Predicted Sensitivity (new study)",
      "Predicted Specificity (new study)",
      "Positive Likelihood Ratio",
      "Negative Likelihood Ratio",
      "Diagnostic Odds Ratio",
      "Summary ROC point"
    )
    missing.labels <- expected.labels[!vapply(expected.labels, grepl, logical(1), clinical.summary, fixed=TRUE)]
    if (length(missing.labels) > 0) {
      stop(paste("diagnostic.hsroc clinical summary is missing:", paste(missing.labels, collapse=", ")))
    }
    if (grepl("Between-study parameters|Within-study parameters|THETA|LAMBDA|theta|alpha", clinical.summary)) {
      stop(paste("diagnostic.hsroc clinical summary leaked raw sampler parameters:\n", clinical.summary))
    }

    result <- run.case("non-finite-init")

    if (!is.list(result) || !"Summary" %in% names(result)) {
      stop("diagnostic.hsroc did not return a result list after non-finite retry")
    }
    if (length(calls) != 2) {
      stop(paste("unexpected non-finite retry call count:", length(calls)))
    }
    if (!grepl("chain_1_retry_1$", calls[[2]])) {
      stop(paste("non-finite retry did not use retry directory:", calls[[2]]))
    }
    if (!identical(summary.chains, calls[[2]])) {
      stop("HSROCSummary did not use the clean retry after non-finite output")
    }

    result <- run.case("bad-summary")
    clinical.summary <- result$Summary[["Clinical Accuracy Summary"]]
    specificity.line <- grep("Predicted Specificity (new study)", strsplit(clinical.summary, "\n", fixed=TRUE)[[1]], value=TRUE, fixed=TRUE)
    if (length(specificity.line) != 1 || !grepl("0.200", specificity.line, fixed=TRUE)) {
      stop("diagnostic.hsroc did not repair the known HSROC Specificity (new) HPD.high summary bug")
    }

    result <- try(run.case("bad-other-summary"), silent=TRUE)
    if (!inherits(result, "try-error")) {
      stop("HSROC summary with other impossible interval bounds unexpectedly succeeded")
    }
    if (!grepl("inconsistent interval bounds", as.character(result))) {
      stop(paste("unexpected bad-other-summary error:", as.character(result)))
    }

    result <- try(run.case("fatal"), silent=TRUE)
    if (!inherits(result, "try-error")) {
      stop("unrecoverable HSROC failure unexpectedly succeeded")
    }
    if (length(calls) != 2) {
      stop(paste("unexpected fatal retry call count:", length(calls)))
    }

    if (normalizePath(getwd(), winslash="/") != normalizePath(work, winslash="/")) {
      stop("diagnostic.hsroc did not restore the R working directory")
    }

    cat("OK\n")
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/"))


_HSROC_NAMESPACE_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    required <- c("coda", "MCMCpack")
    missing <- required[!vapply(required, requireNamespace, logical(1), quietly=TRUE)]
    if (length(missing) > 0) {
      cat("SKIP missing R packages:", paste(missing, collapse=", "), "\n")
      quit(status=42)
    }

    missing <- c("HSROC")[!vapply(c("HSROC"), requireNamespace, logical(1), quietly=TRUE)]
    if (length(missing) > 0) {
      cat("SKIP missing R packages:", paste(missing, collapse=", "), "\n")
      quit(status=42)
    }
    if (as.character(utils::packageVersion("HSROC")) != "2.1.9") {
      cat("SKIP HSROC 2.1.9 is not installed\n")
      quit(status=42)
    }
    if (!exists("as.mcmc", envir=asNamespace("HSROC"), inherits=TRUE)) {
      stop("HSROC namespace did not import coda::as.mcmc")
    }

    work <- tempfile("hsroc_ns_")
    dir.create(work)
    data <- data.frame(
      TP=c(19, 8, 41, 5, 45),
      FP=c(1, 9, 1, 1, 58),
      FN=c(10, 2, 12, 2, 32),
      TN=c(81, 13, 49, 18, 165)
    )
    chain <- file.path(work, "chain_1")
    dir.create(chain)

    old <- getwd()
    setwd(chain)
    set.seed(113)
    HSROC::HSROC(
      data=data,
      iter.num=120,
      prior_LAMBDA=c(-2, 2),
      prior_THETA=c(-2, 2),
      path=chain
    )
    setwd(old)

    summary.args <- list(
      data=data,
      burn_in=1,
      Thin=1,
      print_plot=FALSE,
      chain=c(chain)
    )
    if ("path" %in% names(formals(HSROC::HSROCSummary))) {
      summary.args$path <- work
    } else {
      summary.args$summary.path <- work
    }
    result <- do.call(HSROC::HSROCSummary, summary.args)
    if (!is.list(result) || !"Between-study parameters" %in% names(result)) {
      stop("HSROCSummary did not return the expected summary sections")
    }

    cat("OK\n")
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/"))


_HSROC_HEADER_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/classes.r")))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/utilities.r")))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/diagnostic_methods.r")))

    between.study <- matrix(
      c(0.624, 1.110, 0.817, 1.907, 1.493, 1.356),
      nrow=2
    )
    rownames(between.study) <- c("THETA", "LAMBDA")
    colnames(between.study) <- c("Median estimate", "HPD.low", "HPD.high")

    within.study <- array(
      1:27,
      dim=c(3, 3, 3),
      dimnames=list(
        c("1", "2", "3"),
        c("Median estimate", "HPD lower", "HPD upper"),
        c("theta", "alpha", "pi")
      )
    )

    summary <- hsroc.display.summary(
      list(
        `Between-study parameters`=between.study,
        `Within-study parameters`=within.study,
        `Reference standard`=structure(
          c(0.1, 0.2, 0.3),
          dim=c(1, 3),
          dimnames=list("Gold standard", c("estimate", "ci.lb", "ci.ub"))
        )
      ),
      list(digits=3),
      character()
    )

    if (!identical(colnames(summary[["Between-study parameters"]]), c("Median estimate", "Lower bound", "Upper bound"))) {
      stop(paste("between-study HPD headers were not normalized:", paste(colnames(summary[["Between-study parameters"]]), collapse=", ")))
    }

    within.headers <- dimnames(summary[["Within-study parameters"]])[[2]]
    if (!identical(within.headers, c("Median estimate", "Lower bound", "Upper bound"))) {
      stop(paste("within-study HPD headers were not normalized:", paste(within.headers, collapse=", ")))
    }

    reference.headers <- colnames(summary[["Reference standard"]])
    if (!identical(reference.headers, c("estimate", "Lower bound", "Upper bound"))) {
      stop(paste("reference interval headers were not normalized:", paste(reference.headers, collapse=", ")))
    }

    combined.headers <- paste(
      c(colnames(summary[["Between-study parameters"]]), within.headers, reference.headers),
      collapse=" "
    )
    if (grepl("HPD[.]low|HPD[.]high|HPD lower|HPD upper|ci[.]lb|ci[.]ub", combined.headers)) {
      stop(paste("raw interval headers leaked:", combined.headers))
    }

    cat("OK\n")
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/"))


_HSROC_CLINICAL_SUMMARY_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/classes.r")))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/utilities.r")))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/diagnostic_methods.r")))

    between.study <- matrix(
      c(
        0.148, 1.368, 0.293, 0.650, 0.287, 0.677, 0.830, 0.698, 0.793,
       -0.086, 0.964, -0.177, 0.354, 0.126, 0.584, 0.755, 0.378, 0.522,
        0.388, 1.763, 0.746, 1.060, 0.486, 0.767, 0.898, 1.000, 1.000
      ),
      nrow=9
    )
    rownames(between.study) <- c(
      "THETA", "LAMBDA", "beta", "sigma.alpha", "sigma.theta",
      "S Overall", "C Overall", "S1_new", "C1_new"
    )
    colnames(between.study) <- c("Median estimate", "HPD.low", "HPD.high")

    within.study <- array(
      1:18,
      dim=c(2, 3, 3),
      dimnames=list(
        c("Study 1", "Study 2"),
        c("Median estimate", "HPD lower", "HPD upper"),
        c("theta", "alpha", "pi")
      )
    )

    diagnostic.data <- new(
      "DiagnosticData",
      TP=c(19, 8),
      FN=c(10, 2),
      TN=c(81, 13),
      FP=c(1, 9),
      study.names=c("Lecart Lenfant", "Piver Barlow")
    )

    summary <- hsroc.display.summary(
      list(
        `Between-study parameters`=between.study,
        `Within-study parameters`=within.study
      ),
      list(digits=3),
      character(),
      diagnostic.data
    )

    if (!"Clinical Accuracy Summary" %in% names(summary)) {
      stop("clinical accuracy summary is missing")
    }
    clinical.summary <- summary[["Clinical Accuracy Summary"]]
    expected.labels <- c(
      "Summary Sensitivity",
      "Summary Specificity",
      "Predicted Sensitivity (new study)",
      "Predicted Specificity (new study)",
      "Positive Likelihood Ratio",
      "Negative Likelihood Ratio",
      "Diagnostic Odds Ratio"
    )
    missing.labels <- expected.labels[!vapply(expected.labels, grepl, logical(1), clinical.summary, fixed=TRUE)]
    if (length(missing.labels) > 0) {
      stop(paste("clinical summary is missing:", paste(missing.labels, collapse=", ")))
    }
    leaked.labels <- c("S Overall", "C Overall", "S1_new", "C1_new")
    leaked <- leaked.labels[vapply(leaked.labels, grepl, logical(1), clinical.summary, fixed=TRUE)]
    if (length(leaked) > 0) {
      stop(paste("clinical summary leaked raw row labels:", paste(leaked, collapse=", ")))
    }

    if (!"HSROC Model Parameters" %in% names(summary)) {
      stop("model parameter summary is missing")
    }
    model.summary <- summary[["HSROC Model Parameters"]]
    expected.model.labels <- c(
      "Accuracy parameter",
      "Threshold parameter",
      "Shape parameter",
      "Between-study accuracy SD",
      "Between-study threshold SD",
      "Higher values increase diagnostic accuracy",
      "Higher values reflect a stricter positivity threshold"
    )
    missing.model.labels <- expected.model.labels[!vapply(expected.model.labels, grepl, logical(1), model.summary, fixed=TRUE)]
    if (length(missing.model.labels) > 0) {
      stop(paste("model summary is missing:", paste(missing.model.labels, collapse=", ")))
    }

    within.names <- dimnames(summary[["Within-study parameters"]])[[1]]
    if (!identical(within.names, c("Lecart Lenfant", "Piver Barlow"))) {
      stop(paste("within-study row names were not replaced:", paste(within.names, collapse=", ")))
    }

    cat("OK\n")
    """
).replace("__REPO_ROOT__", repr(REPO_ROOT).replace("\\", "/"))


def test_hsroc_retries_failed_chain_once_in_clean_directory():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript executable not found")

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=_HSROC_RETRY_DRIVER,
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


def test_hsroc_summary_namespace_imports_as_mcmc():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript executable not found")

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=_HSROC_NAMESPACE_DRIVER,
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


def test_hsroc_fallback_summary_uses_canonical_hpd_interval_headers():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript executable not found")

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=_HSROC_HEADER_DRIVER,
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


def test_hsroc_summary_uses_clinical_labels_and_study_names():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript executable not found")

    result = subprocess.run(
        [rscript, "-"],
        cwd=REPO_ROOT,
        input=_HSROC_CLINICAL_SUMMARY_DRIVER,
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
