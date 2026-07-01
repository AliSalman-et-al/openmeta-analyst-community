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
    if (!all(c("Between-study parameters", "Within-study parameters") %in% names(result$Summary))) {
      stop("diagnostic.hsroc did not preserve the stock HSROC summary sections")
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
    specificity.new <- result$Summary$`Between-study parameters`["Specificity (new)", ]
    if (specificity.new[["HPD.high"]] <= specificity.new[["median estimate"]]) {
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
