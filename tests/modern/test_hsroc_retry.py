import os
import shutil
import subprocess
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


_HSROC_RETRY_DRIVER = textwrap.dedent(
    r"""
    repo <- normalizePath(__REPO_ROOT__, winslash = "/")
    required <- c("OpenMetaR", "metafor", "HSROC")
    missing <- required[!vapply(required, requireNamespace, logical(1), quietly=TRUE)]
    if (length(missing) > 0) {
      cat("SKIP missing R packages:", paste(missing, collapse=", "), "\n")
      quit(status=42)
    }

    suppressPackageStartupMessages(library(OpenMetaR))
    suppressPackageStartupMessages(source(file.path(repo, "src/R/OpenMetaR/R/diagnostic_methods.r")))

    work <- tempfile("hsroc_retry_")
    dir.create(work)
    dir.create(file.path(work, "r_tmp"))
    setwd(work)

    run.case <- function(mode) {
      calls <<- c()
      summary.chains <<- c()

      fake.HSROC <- function(..., path) {
        calls <<- c(calls, path)
        if (mode == "fresh-init" && length(calls) == 1) {
          stop("simulated transient HSROC failure")
        }
        if (mode == "fatal") {
          stop("simulated unrecoverable validation failure")
        }
        invisible(NULL)
      }
      assign("HSROC", fake.HSROC, envir=.GlobalEnv)

      result <- diagnostic.hsroc(diagnostic.data, params)
      result
    }

    HSROCSummary <- function(..., chain) {
      summary.chains <<- chain
      list(
        `Between-study parameters` = matrix(1:4, nrow=2),
        `Within-study parameters` = array(1:8, dim=c(2, 2, 2)),
        image.list = list("Summary ROC" = "roc.png")
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

    r.lib <- tempfile("hsroc_lib_")
    dir.create(r.lib)
    install <- system2(
      file.path(R.home("bin"), "R"),
      c("CMD", "INSTALL", paste0("--library=", r.lib), file.path(repo, "src/R/HSROC")),
      stdout=TRUE,
      stderr=TRUE
    )
    status <- attr(install, "status")
    if (!is.null(status) && status != 0) {
      cat("SKIP R CMD INSTALL HSROC failed\n", paste(tail(install, 40), collapse="\n"), "\n")
      quit(status=42)
    }

    .libPaths(c(r.lib, .libPaths()))
    requireNamespace("HSROC")
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

    result <- HSROC::HSROCSummary(
      data=data,
      burn_in=1,
      Thin=1,
      print_plot=FALSE,
      path=work,
      chain=c(chain)
    )
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

    assert result.returncode == 0, (
        "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s"
        % (result.returncode, result.stdout[-2000:], result.stderr[-2000:])
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

    assert result.returncode == 0, (
        "driver failed (rc=%s)\nSTDOUT:\n%s\nSTDERR:\n%s"
        % (result.returncode, result.stdout[-2000:], result.stderr[-2000:])
    )
    assert "OK" in result.stdout
