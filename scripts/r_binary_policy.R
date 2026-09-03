split_policy_field <- function(value) {
  if (!nzchar(value)) character() else strsplit(value, ",", fixed = TRUE)[[1]]
}

load_rcms_r_binary_policy <- function(repo_root, python = Sys.getenv("RCMS_POLICY_PYTHON", "python")) {
  manifest <- file.path(repo_root, "config", "r-dependencies.json")
  helper <- file.path(repo_root, "scripts", "r_dependency_policy.py")
  output <- system2(
    python,
    c(shQuote(helper), "--manifest", shQuote(manifest), "--emit-dcf"),
    stdout = TRUE,
    stderr = TRUE
  )
  status <- attr(output, "status")
  if (!is.null(status) && status != 0L) {
    stop("Could not load manifest-owned R binary policy: ", paste(output, collapse = "\n"))
  }
  record <- as.list(read.dcf(textConnection(output), all = TRUE)[1, ])
  list(
    repository = record$Repository,
    provider = record$Provider,
    snapshot = record$Snapshot,
    r_version = record$`R-Version`,
    normal_packages = split_policy_field(record$`Normal-Packages`),
    runtime_packages = split_policy_field(record$`Runtime-Packages`),
    platforms = list(
      `windows-x64` = list(
        system = record[["windows_x64-System"]],
        arch = record[["windows_x64-R-Arch"]],
        pkg_type = record[["windows_x64-Pkg-Type"]],
        contrib_path = record[["windows_x64-Contrib-Path"]]
      ),
      `macos-x64` = list(
        system = record[["macos_x64-System"]],
        arch = record[["macos_x64-R-Arch"]],
        pkg_type = record[["macos_x64-Pkg-Type"]],
        contrib_path = record[["macos_x64-Contrib-Path"]]
      ),
      `macos-arm64` = list(
        system = record[["macos_arm64-System"]],
        arch = record[["macos_arm64-R-Arch"]],
        pkg_type = record[["macos_arm64-Pkg-Type"]],
        contrib_path = record[["macos_arm64-Contrib-Path"]]
      )
    ),
    python = python,
    helper = helper
  )
}

policy_sha256 <- function(policy, path) {
  output <- system2(
    policy$python,
    c(shQuote(policy$helper), "--sha256", shQuote(path)),
    stdout = TRUE,
    stderr = TRUE
  )
  status <- attr(output, "status")
  if (!is.null(status) && status != 0L) {
    stop("Could not calculate retained binary archive SHA256: ", paste(output, collapse = "\n"))
  }
  digest <- trimws(output)
  if (length(digest) != 1L || !grepl("^[0-9a-f]{64}$", digest)) {
    stop("Could not calculate retained binary archive SHA256")
  }
  digest
}

rcms_policy_platform <- function(policy, sysname = Sys.info()[["sysname"]], arch = R.version$arch) {
  matches <- Filter(
    function(record) identical(record$system, sysname) && identical(record$arch, arch),
    policy$platforms
  )
  if (length(matches) != 1L) {
    stop("Unsupported R binary target: system=", sysname, ", architecture=", arch)
  }
  matches[[1]]
}

assert_rcms_binary_runtime <- function(
  policy,
  sysname = Sys.info()[["sysname"]],
  arch = R.version$arch,
  pkg_type = .Platform$pkgType,
  r_version = as.character(getRversion())
) {
  if (!identical(r_version, policy$r_version)) {
    stop("Native binary policy requires R ", policy$r_version, ", found ", r_version)
  }
  platform <- rcms_policy_platform(policy, sysname, arch)
  if (!identical(pkg_type, platform$pkg_type)) {
    stop(
      "Unexpected native R binary type for ", sysname, "/", arch,
      ": expected ", platform$pkg_type, ", found ", pkg_type
    )
  }
  configured <- Sys.getenv("RCMS_CRAN_REPO", "")
  if (nzchar(configured) && !identical(configured, policy$repository)) {
    stop("RCMS_CRAN_REPO must match the manifest snapshot: ", policy$repository)
  }
  platform
}

dependency_names <- function(value) {
  if (is.na(value) || !nzchar(value)) return(character())
  entries <- trimws(strsplit(value, ",", fixed = TRUE)[[1]])
  names <- trimws(sub("\\s*\\(.*$", "", entries))
  setdiff(names[nzchar(names)], "R")
}

runtime_priority_packages <- function() {
  installed <- utils::installed.packages()
  priority <- installed[, "Priority"]
  rownames(installed)[!is.na(priority) & priority %in% c("base", "recommended")]
}

preflight_rcms_binary_closure <- function(
  policy,
  database = utils::available.packages(repos = policy$repository, type = "binary"),
  runtime_packages = runtime_priority_packages()
) {
  queue <- policy$normal_packages
  visited <- character()
  binary_packages <- character()
  unavailable <- character()
  while (length(queue)) {
    package <- queue[[1]]
    queue <- queue[-1]
    if (package %in% visited) next
    visited <- c(visited, package)
    if (package %in% runtime_packages) {
      if (!requireNamespace(package, quietly = TRUE)) {
        unavailable <- c(unavailable, package)
      }
      next
    }
    if (!package %in% rownames(database)) {
      unavailable <- c(unavailable, package)
      next
    }
    binary_packages <- c(binary_packages, package)
    fields <- intersect(c("Depends", "Imports", "LinkingTo"), colnames(database))
    dependencies <- unique(unlist(lapply(database[package, fields, drop = TRUE], dependency_names)))
    queue <- unique(c(queue, setdiff(dependencies, visited)))
  }
  contrib <- utils::contrib.url(policy$repository, type = "binary")
  if (length(unavailable)) {
    stop(
      "Required native R binaries unavailable from ", contrib, ": ",
      paste(sort(unique(unavailable)), collapse = ", ")
    )
  }
  list(
    packages = sort(unique(visited)),
    binary_packages = sort(unique(binary_packages)),
    contrib_url = contrib
  )
}

emit_rcms_binary_evidence <- function(label, values) {
  line <- paste0("RCMS_R_BINARY_EVIDENCE ", label, " ", paste(values, collapse = " | "))
  message(line)
  evidence <- Sys.getenv("RCMS_R_BINARY_EVIDENCE", "")
  if (nzchar(evidence)) cat(line, "\n", file = evidence, append = TRUE)
}

target_package_loadable <- function(package, lib) {
  old_paths <- .libPaths()
  on.exit(.libPaths(old_paths), add = TRUE)
  target <- normalizePath(lib, winslash = "/", mustWork = TRUE)
  runtime <- normalizePath(.Library, winslash = "/", mustWork = TRUE)
  .libPaths(unique(c(target, runtime)))
  namespace <- tryCatch(loadNamespace(package, lib.loc = target), error = function(error) NULL)
  if (is.null(namespace)) return(FALSE)
  namespace_path <- normalizePath(getNamespaceInfo(namespace, "path"), winslash = "/", mustWork = TRUE)
  startsWith(namespace_path, paste0(target, "/"))
}

rcms_binary_archive_extension <- function(platform) {
  if (identical(platform$system, "Windows")) return("zip")
  if (identical(platform$system, "Darwin")) return("tgz")
  stop("Unsupported retained R binary archive system: ", platform$system)
}

normalize_rcms_downloaded_archives <- function(downloaded, expected_count, platform) {
  if (NROW(downloaded) != expected_count) {
    stop("PPM did not provide one retained binary archive per missing package")
  }
  if (is.null(dim(downloaded))) {
    if (expected_count != 1L || length(downloaded) < 2L) {
      stop("PPM binary archive result does not have a usable destination column")
    }
    archives <- downloaded[[2L]]
  } else {
    if (NCOL(downloaded) < 2L) {
      stop("PPM binary archive result does not have a usable destination column")
    }
    archives <- downloaded[, 2L, drop = TRUE]
  }
  archives <- as.character(archives)
  if (length(archives) != expected_count || any(!nzchar(archives))) {
    stop("PPM binary archive result has an invalid destination count")
  }
  missing_archives <- archives[!file.exists(archives)]
  if (length(missing_archives)) {
    stop("PPM retained binary archive is missing: ", paste(missing_archives, collapse = ", "))
  }
  expected_extension <- rcms_binary_archive_extension(platform)
  if (any(tolower(tools::file_ext(archives)) != expected_extension)) {
    stop(
      "PPM ", platform$system, " binary acquisition returned a non-.",
      expected_extension, " archive"
    )
  }
  unname(archives)
}

install_rcms_binary_packages <- function(
  policy,
  lib,
  database = NULL,
  install_binary = utils::install.packages,
  download_binary = utils::download.packages,
  installed_in_target = function() rownames(utils::installed.packages(lib.loc = lib)),
  package_loadable = function(package) target_package_loadable(package, lib)
) {
  platform <- assert_rcms_binary_runtime(policy)
  options(
    repos = c(CRAN = policy$repository),
    timeout = 600,
    install.packages.check.source = "no",
    install.packages.compile.from.source = "never"
  )
  if (is.null(database)) {
    database <- utils::available.packages(repos = policy$repository, type = "binary")
  }
  closure <- preflight_rcms_binary_closure(policy, database = database)
  required_binary <- closure$binary_packages
  target <- installed_in_target()
  missing <- setdiff(required_binary, target)
  if (length(missing)) {
    message("Installing complete R dependency closure with type=binary only: ", paste(missing, collapse = ", "))
    archive_dir <- Sys.getenv("RCMS_R_PACKAGE_ARCHIVE_DIR", "")
    if (nzchar(archive_dir)) {
      dir.create(archive_dir, recursive = TRUE, showWarnings = FALSE)
      downloaded <- download_binary(
        missing, destdir = archive_dir, repos = policy$repository, type = "binary"
      )
      retained_archives <- normalize_rcms_downloaded_archives(
        downloaded, length(missing), platform
      )
      archive_hashes <- vapply(
        retained_archives, function(path) policy_sha256(policy, path), character(1)
      )
      if (any(!grepl("^[0-9a-f]{64}$", archive_hashes))) {
        stop("PPM binary archive pre-install SHA256 validation failed")
      }
      emit_rcms_binary_evidence(
        "binary-archives-preinstall",
        paste0(basename(retained_archives), "=sha256:", archive_hashes)
      )
      install_binary(
        retained_archives, lib = lib, repos = NULL,
        dependencies = FALSE, type = "binary"
      )
    } else {
      install_binary(missing, lib = lib, dependencies = FALSE, type = "binary")
    }
  }
  target_after <- installed_in_target()
  not_installed <- setdiff(required_binary, target_after)
  if (length(not_installed)) {
    stop("Complete binary closure missing from target library after install: ", paste(not_installed, collapse = ", "))
  }
  unresolved <- required_binary[!vapply(required_binary, package_loadable, logical(1))]
  if (length(unresolved)) {
    stop("Complete binary closure unloadable from isolated target library: ", paste(unresolved, collapse = ", "))
  }
  emit_rcms_binary_evidence(
    "policy",
    c(
      paste0("architecture=", R.version$arch),
      paste0("pkgType=", .Platform$pkgType),
      paste0("repository=", policy$repository),
      paste0("contrib=", closure$contrib_url),
      paste0("provider=", policy$provider),
      paste0("snapshot=", policy$snapshot)
    )
  )
  emit_rcms_binary_evidence(
    "binary-packages",
    c(paste0("count=", length(policy$normal_packages)), paste(policy$normal_packages, collapse = ","))
  )
  emit_rcms_binary_evidence(
    "binary-closure",
    c(
      paste0("count=", length(closure$binary_packages)),
      paste(closure$binary_packages, collapse = ",")
    )
  )
  invisible(platform)
}
