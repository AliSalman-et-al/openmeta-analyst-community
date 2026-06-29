options(repos = c(CRAN = "https://cran.r-project.org"), timeout = 600)
lib <- Sys.getenv("R_LIBS_USER")

if (!nzchar(lib)) {
  stop("R_LIBS_USER must point at the target bundled R library")
}

dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))

install_archive <- function(package, version) {
  if (requireNamespace(package, quietly = TRUE)) {
    return(invisible(TRUE))
  }
  url <- sprintf(
    "https://cran.r-project.org/src/contrib/Archive/%s/%s_%s.tar.gz",
    package,
    package,
    version
  )
  tryCatch(
    install.packages(url, repos = NULL, type = "source", lib = lib),
    error = function(e) message(sprintf("Archived %s %s did not install: %s", package, version, conditionMessage(e)))
  )
}

install_archive("mcmc", "0.9-5")
install_archive("MCMCpack", "1.3-8")
install_archive("metafor", "1.9-9")
install_archive("mice", "2.30")
install_archive("igraph", "1.0.1")
install_archive("lme4", "1.1-12")
install_archive("quantreg", "5.29")
install_archive("boot", "1.3-18")
install_archive("survival", "2.40-1")
install_archive("ape", "4.0")
install_archive("Hmisc", "4.0-0")

remaining <- c(
  "Rcpp", "magrittr", "irlba", "minqa", "nloptr", "RcppEigen",
  "SparseM", "MatrixModels", "Formula", "latticeExtra", "acepack",
  "gridExtra", "data.table", "htmlTable", "viridis", "htmltools",
  "MCMCpack", "igraph", "lme4", "quantreg", "ape", "Hmisc", "mice",
  "metafor", "ggplot2", "RColorBrewer", "lattice", "coda", "MASS", "nlme"
)

install_missing <- function() {
  missing <- remaining[!vapply(remaining, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) {
    install.packages(missing, lib = lib)
  }
}

install_missing()

missing <- remaining[!vapply(remaining, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  for (package in missing) {
    for (attempt in seq_len(3)) {
      install.packages(package, lib = lib)
      if (requireNamespace(package, quietly = TRUE)) {
        break
      }
    }
  }
}

missing <- remaining[!vapply(remaining, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  stop(sprintf("R packages still missing after install attempts: %s", paste(missing, collapse = ", ")))
}
