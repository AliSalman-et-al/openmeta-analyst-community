options(
  repos = c(CRAN = Sys.getenv("RCMS_CRAN_REPO", "https://cloud.r-project.org")),
  timeout = 600,
  install.packages.check.source = "no"
)
lib <- Sys.getenv("R_LIBS_USER")

if (!nzchar(lib)) {
  stop("R_LIBS_USER must point at the target bundled R library")
}

dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))

RCMetaR_cran_packages <- c(
  "metafor", "lme4", "pdftools", "rsvg", "svglite", "tiff", "roxygen2", "testthat"
)

RCMetaR_archive_packages <- list(
  HSROC = "https://cran.r-project.org/src/contrib/Archive/HSROC/HSROC_2.1.9.tar.gz"
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
  RCMetaR_cran_packages,
  app_cran_bundle_packages,
  recommended_bundle_packages
))

cran_package_install_types <- function() {
  if (.Platform$pkgType != "source") {
    return(c("binary", "source"))
  }
  "source"
}

package_install_types <- cran_package_install_types()

is_installed_in_target_library <- function(package) {
  package %in% rownames(utils::installed.packages(lib.loc = lib))
}

install_cran_packages <- function(packages) {
  missing <- packages[!vapply(packages, is_installed_in_target_library, logical(1))]
  for (package_install_type in package_install_types) {
    if (!length(missing)) {
      break
    }
    message(sprintf(
      "Installing %d CRAN package(s) with type=%s",
      length(missing),
      package_install_type
    ))
    tryCatch(
      install.packages(missing, lib = lib, dependencies = NA, type = package_install_type),
      error = function(error) {
        if (identical(package_install_type, tail(package_install_types, 1))) {
          stop(error)
        }
        message(sprintf(
          "CRAN package install with type=%s did not complete: %s",
          package_install_type,
          conditionMessage(error)
        ))
      }
    )
    missing <- packages[!vapply(packages, is_installed_in_target_library, logical(1))]
  }
}

install_cran_packages(required_packages)

missing <- required_packages[!vapply(required_packages, is_installed_in_target_library, logical(1))]
if (length(missing)) {
  for (package in missing) {
    for (attempt in seq_len(3)) {
      install_cran_packages(package)
      if (is_installed_in_target_library(package)) {
        break
      }
    }
  }
}

missing <- required_packages[!vapply(required_packages, is_installed_in_target_library, logical(1))]
if (length(missing)) {
  stop(sprintf("R packages still missing after install attempts: %s", paste(missing, collapse = ", ")))
}

install_archive_package <- function(package, url, expected_version) {
  installed <- utils::installed.packages(lib.loc = lib)
  if (!package %in% rownames(installed) || installed[package, "Version"] != expected_version) {
    install.packages(url, lib = lib, repos = NULL, type = "source")
  }
  installed <- utils::installed.packages(lib.loc = lib)
  if (!package %in% rownames(installed)) {
    stop(sprintf("%s was not installed from %s", package, url))
  }
  installed_version <- installed[package, "Version"]
  if (installed_version != expected_version) {
    stop(sprintf(
      "%s installed at version %s, expected %s",
      package,
      installed_version,
      expected_version
    ))
  }
}

install_archive_package("HSROC", RCMetaR_archive_packages$HSROC, "2.1.9")
