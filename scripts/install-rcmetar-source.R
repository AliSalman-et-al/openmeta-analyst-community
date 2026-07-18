args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  stop("install-rcmetar-source.R requires exactly SOURCE and LIBRARY arguments")
}

source <- normalizePath(args[[1L]], mustWork = TRUE)
library <- normalizePath(args[[2L]], mustWork = TRUE)
source_description <- file.path(source, "DESCRIPTION")
if (!file.exists(source_description)) {
  stop("RCMetaR source is missing DESCRIPTION: ", source)
}
source_fields <- read.dcf(source_description, fields = c("Package", "Version"))[1L, ]
if (!identical(unname(source_fields[["Package"]]), "RCMetaR")) {
  stop("source DESCRIPTION is not the RCMetaR package")
}

install.packages(
  source,
  lib = library,
  repos = NULL,
  type = "source",
  dependencies = FALSE
)

installed_description <- file.path(library, "RCMetaR", "DESCRIPTION")
if (!file.exists(installed_description)) {
  stop("RCMetaR source install did not produce the target package")
}
installed_fields <- read.dcf(installed_description, fields = c("Package", "Version"))[1L, ]
if (!identical(unname(installed_fields), unname(source_fields))) {
  stop("installed RCMetaR identity differs from its source DESCRIPTION")
}
namespace <- loadNamespace("RCMetaR", lib.loc = library)
namespace_path <- normalizePath(
  getNamespaceInfo(namespace, "path"),
  winslash = "/",
  mustWork = TRUE
)
target_library <- normalizePath(library, winslash = "/", mustWork = TRUE)
if (!startsWith(namespace_path, paste0(target_library, "/"))) {
  stop("installed RCMetaR namespace did not load from the target library")
}
