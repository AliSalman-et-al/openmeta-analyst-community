#!/usr/bin/env Rscript

qa_visual_coverage_inventory <- function() {
  data.frame(
    family = c(
      "standard_forest",
      "cumulative_forest",
      "leave_one_out_forest",
      "subgroup_forest",
      "regression",
      "coefficient_forest",
      "bootstrap_histogram",
      "roc",
      "sroc",
      "hsroc_diagnostics"
    ),
    plot_kind = c(
      "forest",
      "cumulative_forest",
      "leave_one_out_forest",
      "subgroup_forest",
      "regression",
      rep("other", 2),
      "roc",
      "sroc",
      "other"
    ),
    status = c(rep("covered", 5), rep("excluded", 5)),
    harness = c(rep("forest", 4), "bubble", rep("", 5)),
    reason = c(
      rep("", 5),
      "The optional coefficient plot does not yet have an independent Plot Capability Descriptor or maintained renderer contract.",
      "Bootstrap plots depend on stochastic resampling and remain in Full R Stack Evidence rather than the deterministic visual matrix.",
      "The legacy ROC renderer is tracked for journal-grade migration before visual baselines are accepted.",
      "The legacy SROC renderer is tracked for journal-grade migration before visual baselines are accepted.",
      "HSROC diagnostic figures require the external sampler and are exercised only by Full R Stack Evidence."
    ),
    evidence = c(
      rep("generated manifest", 5),
      "Plot Capability Descriptor contract",
      "Full R Stack Evidence",
      "GitHub issue #271",
      "GitHub issue #271",
      "Full R Stack Evidence"
    ),
    stringsAsFactors = FALSE
  )
}

qa_supported_plot_kinds <- function() {
  if (!exists(".rcmetar.plot.kind.capabilities", mode = "function")) {
    stop("RCMetaR Plot Capability Descriptor registry is not loaded.", call. = FALSE)
  }
  names(.rcmetar.plot.kind.capabilities())
}

qa_validate_visual_coverage <- function(inventory, produced.families,
                                        supported.plot.kinds = qa_supported_plot_kinds()) {
  duplicate.families <- unique(inventory$family[duplicated(inventory$family)])
  if (length(duplicate.families) > 0) {
    stop(
      "Visual QA inventory contains duplicate plot families: ",
      paste(duplicate.families, collapse = ", "),
      call. = FALSE
    )
  }
  invalid.status <- setdiff(unique(inventory$status), c("covered", "excluded"))
  if (length(invalid.status) > 0) {
    stop("Visual QA inventory contains invalid status values.", call. = FALSE)
  }
  missing.contract.kinds <- setdiff(supported.plot.kinds, unique(inventory$plot_kind))
  unknown.inventory.kinds <- setdiff(unique(inventory$plot_kind), supported.plot.kinds)
  if (length(missing.contract.kinds) > 0 || length(unknown.inventory.kinds) > 0) {
    stop(
      "Visual QA inventory and Plot Capability Descriptor registry disagree. Missing: ",
      paste(missing.contract.kinds, collapse = ", "),
      "; unknown: ", paste(unknown.inventory.kinds, collapse = ", "),
      call. = FALSE
    )
  }
  excluded <- inventory$status == "excluded"
  if (any(!nzchar(inventory$reason[excluded])) ||
      any(!nzchar(inventory$evidence[excluded]))) {
    stop("Every excluded plot family requires a reason and evidence.", call. = FALSE)
  }
  expected <- inventory$family[inventory$status == "covered"]
  missing <- setdiff(expected, unique(produced.families))
  if (length(missing) > 0) {
    stop(
      "Visual QA manifests are missing covered plot families: ",
      paste(missing, collapse = ", "),
      call. = FALSE
    )
  }
  invisible(TRUE)
}

qa_find_visual_script_root <- function(start = getwd()) {
  current <- normalizePath(start, winslash = "/", mustWork = TRUE)
  repeat {
    script <- file.path(current, "r", "RCMetaR", "inst", "qa", "render_forest_visual_qa.R")
    if (file.exists(script)) {
      return(current)
    }
    parent <- dirname(current)
    if (identical(parent, current)) {
      stop("Could not locate the RCMetaR visual QA scripts.", call. = FALSE)
    }
    current <- parent
  }
}

qa_write_visual_qa_reports <- function(output.root, forest.manifest, bubble.manifest) {
  inventory <- qa_visual_coverage_inventory()
  required <- c("case", "family", "kind", "workflow", "style", "scenario", "image", "bytes", "error")
  if (!all(required %in% names(forest.manifest)) ||
      !all(required %in% names(bubble.manifest))) {
    stop("Visual QA manifests do not share the required report columns.", call.=FALSE)
  }
  combined <- rbind(forest.manifest[required], bubble.manifest[required])
  failed <- !is.na(combined$error) & nzchar(combined$error)
  missing.image <- is.na(combined$image) | !file.exists(combined$image)
  empty.image <- is.na(combined$bytes) | combined$bytes <= 0
  successful <- !(failed | missing.image | empty.image)
  if (any(!successful)) {
    bad <- combined$case[!successful]
    stop(
      "Visual QA render failures: ", paste(bad, collapse = ", "),
      ". Inspect the preserved harness manifests for error details.",
      call. = FALSE
    )
  }
  qa_validate_visual_coverage(inventory, unique(combined$family[successful]))
  utils::write.csv(inventory, file.path(output.root, "coverage.csv"), row.names = FALSE)
  utils::write.csv(combined, file.path(output.root, "manifest.csv"), row.names = FALSE)
  invisible(inventory)
}

qa_write_visual_qa_matrix <- function(repo.root, output.root) {
  python <- Sys.which(c("python", "python3"))
  python <- unname(python[nzchar(python)])
  if (length(python) == 0) {
    stop("Python is required to generate the high-resolution visual QA matrix.", call. = FALSE)
  }
  python <- python[[1]]
  script <- file.path(repo.root, "r", "RCMetaR", "inst", "qa", "forest_contact_sheets.py")
  matrix.root <- file.path(output.root, "matrix")
  dir.create(matrix.root, recursive = TRUE, showWarnings = FALSE)
  status <- system2(
    python,
    c(script, file.path(output.root, "manifest.csv"), "--out-dir", matrix.root),
    stdout = TRUE,
    stderr = TRUE
  )
  if (!identical(attr(status, "status"), NULL) && attr(status, "status") != 0) {
    stop("High-resolution visual QA matrix generation failed: ", paste(status, collapse = "\n"), call. = FALSE)
  }
  expected <- file.path(matrix.root, "contact_all.png")
  if (!file.exists(expected) || file.info(expected)$size <= 0) {
    stop("High-resolution visual QA matrix was not produced.", call. = FALSE)
  }
  invisible(expected)
}

qa_run_comprehensive_visual_qa <- function(repo.root = qa_find_visual_script_root()) {
  output.root <- Sys.getenv(
    "RCMETASTUDIO_PLOT_QA_ROOT",
    file.path(repo.root, "artifacts", "plot-visual-qa")
  )
  dir.create(output.root, recursive = TRUE, showWarnings = FALSE)
  output.root <- normalizePath(output.root, winslash = "/", mustWork = TRUE)

  forest <- new.env(parent = globalenv())
  bubble <- new.env(parent = globalenv())
  sys.source(
    file.path(repo.root, "r", "RCMetaR", "inst", "qa", "render_forest_visual_qa.R"),
    envir = forest
  )
  sys.source(
    file.path(repo.root, "r", "RCMetaR", "inst", "qa", "render_bubble_visual_qa.R"),
    envir = bubble
  )
  forest$qa_load_rcmetar(repo.root)

  forest.root <- file.path(output.root, "forest")
  bubble.root <- file.path(output.root, "bubble")
  dir.create(forest.root, recursive = TRUE, showWarnings = FALSE)
  dir.create(bubble.root, recursive = TRUE, showWarnings = FALSE)
  forest.manifest <- forest$qa_render_matrix(forest.root)
  bubble.manifest <- bubble$qa_render_matrix(bubble.root)
  inventory <- qa_write_visual_qa_reports(
    output.root,
    forest.manifest,
    bubble.manifest
  )
  qa_write_visual_qa_matrix(repo.root, output.root)
  cat(
    "Rendered", nrow(forest.manifest) + nrow(bubble.manifest),
    "covered plot QA cases to", output.root, "\n"
  )
  invisible(list(inventory = inventory, forest = forest.manifest, bubble = bubble.manifest))
}

if (sys.nframe() == 0) {
  qa_run_comprehensive_visual_qa()
}
