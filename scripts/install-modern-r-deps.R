options(repos = c(CRAN = "https://cran.r-project.org"), timeout = 600)
lib <- Sys.getenv("R_LIBS_USER")

if (!nzchar(lib)) {
  stop("R_LIBS_USER must point at the target bundled R library")
}

dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))

openmetar_cran_packages <- c(
  "metafor", "lme4", "roxygen2"
)

app_cran_bundle_packages <- c(
  "mcmc", "MCMCpack", "igraph", "quantreg", "ape", "Hmisc",
  "mice", "ggplot2", "RColorBrewer", "coda",
  "Rcpp", "magrittr", "irlba", "minqa", "nloptr", "RcppEigen",
  "SparseM", "MatrixModels", "Formula", "latticeExtra", "acepack",
  "gridExtra", "data.table", "htmlTable", "viridis", "htmltools",
  "viridisLite", "htmlwidgets", "rmarkdown", "knitr", "stringr",
  "stringi", "colorspace", "gtable", "scales", "vctrs", "rlang",
  "withr", "cli", "glue", "lifecycle", "isoband", "S7", "farver",
  "labeling"
)

recommended_bundle_packages <- c(
  "boot", "lattice", "MASS", "nlme", "survival"
)

required_packages <- unique(c(
  openmetar_cran_packages,
  app_cran_bundle_packages,
  recommended_bundle_packages
))

install_cran_packages <- function(packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) {
    install.packages(missing, lib = lib, dependencies = NA)
  }
}

install_cran_packages(required_packages)

missing <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  for (package in missing) {
    for (attempt in seq_len(3)) {
      install_cran_packages(package)
      if (requireNamespace(package, quietly = TRUE)) {
        break
      }
    }
  }
}

missing <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  stop(sprintf("R packages still missing after install attempts: %s", paste(missing, collapse = ", ")))
}
