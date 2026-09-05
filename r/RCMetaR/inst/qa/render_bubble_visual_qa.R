#!/usr/bin/env Rscript

qa_find_repo_root <- function(start = getwd()) {
  current <- normalizePath(start, winslash = "/", mustWork = TRUE)
  repeat {
    if (file.exists(file.path(current, "pyproject.toml")) &&
        dir.exists(file.path(current, "r", "RCMetaR"))) {
      return(current)
    }
    parent <- dirname(current)
    if (identical(parent, current)) {
      stop("Could not locate repository root.", call. = FALSE)
    }
    current <- parent
  }
}

qa_load_rcmetar <- function(repo.root) {
  package.dir <- file.path(repo.root, "r", "RCMetaR")
  if (requireNamespace("devtools", quietly = TRUE) && dir.exists(package.dir)) {
    devtools::load_all(package.dir, quiet = TRUE)
    return(invisible(NULL))
  }
  suppressPackageStartupMessages(library(RCMetaR))
  attach(asNamespace("RCMetaR"), name = "RCMetaR:qa")
  invisible(NULL)
}

qa_root <- function(repo.root = qa_find_repo_root()) {
  root <- Sys.getenv("RCMETASTUDIO_BUBBLE_QA_ROOT", unset = "")
  if (!nzchar(root)) {
    root <- file.path(repo.root, "artifacts", "bubble-visual-qa")
  }
  dir.create(root, recursive = TRUE, showWarnings = FALSE)
  normalizePath(root, winslash = "/", mustWork = TRUE)
}

qa_params <- function(measure, style, scenario) {
  list(
    conf.level = 95,
    digits = 3,
    fp_style = style,
    fp_col2_str = "[default]",
    fp_show_col4 = TRUE,
    to = "only0",
    fp_col4_str = "Control",
    fp_xticks = "[default]",
    fp_col3_str = "Experimental",
    fp_show_col3 = TRUE,
    fp_show_col2 = TRUE,
    fp_show_col1 = TRUE,
    fp_plot_lb = "[default]",
    fp_outpath = tempfile(fileext = ".png"),
    rm.method = "DL",
    adjust = 0.5,
    fp_plot_ub = "[default]",
    fp_col1_str = "Study or Subgroup",
    measure = measure,
    fp_xlabel = "[default]",
    fp_show_summary_line = TRUE,
    create.plot = TRUE,
    write.to.file = FALSE,
    bp_show_prediction_interval = scenario %in% c("prediction", "stress"),
    bp_label_studies = FALSE,
    bp_show_legend = scenario %in% c("prediction", "stress")
  )
}

qa_labels <- function(prefix, n, stress) {
  labels <- paste(prefix, seq_len(n))
  if (stress) {
    labels <- paste(labels, "extended multicentre moderator cohort with long citation label")
  }
  labels
}

qa_make_binary <- function(style, scenario) {
  stress <- scenario == "stress"
  params <- qa_params("OR", style, scenario)
  params$cov_name <- "latitude"
  data <- new(
    "BinaryData",
    g1O1 = c(4, 6, 3, 62, 33, 180, 8, 505, 13, 21, 9, 38),
    g1O2 = c(119, 300, 228, 13536, 5036, 1361, 2537, 87886, 240, 520, 210, 980),
    g2O1 = c(11, 29, 11, 248, 47, 372, 10, 499, 19, 28, 12, 50),
    g2O2 = c(128, 274, 209, 12619, 5761, 1079, 619, 87892, 228, 500, 207, 950),
    study.names = qa_labels("Binary", 12, stress),
    years = as.integer(1991:2002),
    covariates = list(
      new("CovariateValues", cov.name = "latitude", cov.vals = c(44, 55, 42, 52, 13, 44, 19, 13, 35, 48, 28, 61), cov.type = "continuous", ref.var = "44")
    )
  )
  rcmetar.prepare.analysis.data(data, params)
}

qa_make_continuous <- function(style, scenario) {
  stress <- scenario == "stress"
  params <- qa_params("MD", style, scenario)
  params$cov_name <- "dose"
  data <- new(
    "ContinuousData",
    N1 = c(60, 65, 40, 200, 50, 85, 72, 48, 130, 96),
    mean1 = c(94, 98, 98, 94, 98, 96, 91, 99, 93, 97),
    sd1 = c(22, 21, 28, 19, 21, 21, 24, 20, 18, 23),
    N2 = c(60, 65, 40, 200, 45, 85, 70, 52, 125, 94),
    mean2 = c(92, 92, 88, 82, 88, 92, 87, 91, 86, 90),
    sd2 = c(20, 22, 26, 17, 22, 22, 25, 19, 18, 21),
    study.names = qa_labels("Continuous", 10, stress),
    years = as.integer(2001:2010),
    covariates = list(
      new("CovariateValues", cov.name = "dose", cov.vals = c(10, 20, 15, 35, 25, 30, 12, 40, 28, 33), cov.type = "continuous", ref.var = "10")
    )
  )
  rcmetar.prepare.analysis.data(data, params)
}

qa_make_diagnostic <- function(style, scenario) {
  stress <- scenario == "stress"
  params <- qa_params("Sens", style, scenario)
  params$cov_name <- "threshold"
  data <- new(
    "DiagnosticData",
    TP = c(19, 8, 41, 5, 45, 8, 5, 15, 16, 4, 8, 10),
    FN = c(10, 2, 12, 2, 32, 2, 1, 11, 8, 2, 10, 4),
    TN = c(81, 13, 49, 18, 165, 32, 7, 52, 24, 25, 70, 55),
    FP = c(1, 9, 1, 1, 58, 6, 8, 17, 11, 8, 12, 4),
    study.names = qa_labels("Diagnostic", 12, stress),
    years = as.integer(1970:1981),
    covariates = list(
      new("CovariateValues", cov.name = "threshold", cov.vals = c(1.1, 1.3, 2.1, 2.5, 1.7, 2.8, 1.2, 1.4, 2.3, 1.6, 2.6, 2.2), cov.type = "continuous", ref.var = "1.1")
    )
  )
  rcmetar.prepare.analysis.data(data, params)
}

qa_fixture <- function(kind, style, scenario) {
  switch(
    kind,
    binary = qa_make_binary(style, scenario),
    continuous = qa_make_continuous(style, scenario),
    diagnostic = qa_make_diagnostic(style, scenario)
  )
}

qa_measure <- function(kind) {
  switch(kind, binary = "OR", continuous = "MD", diagnostic = "Sens")
}

qa_render_matrix <- function(output.root = qa_root()) {
  cases <- expand.grid(
    kind = c("binary", "continuous", "diagnostic"),
    workflow = "meta-regression",
    style = c("default", "revman", "bmj"),
    scenario = c("base", "prediction", "stress"),
    stringsAsFactors = FALSE
  )
  rows <- vector("list", nrow(cases))
  for (i in seq_len(nrow(cases))) {
    case <- cases[i, ]
    id <- paste(case$kind, case$workflow, case$style, case$scenario, sep = "__")
    image <- file.path(output.root, paste0(id, ".png"))
    err <- NA_character_
    bytes <- NA_real_
    tryCatch({
      data <- qa_fixture(case$kind, case$style, case$scenario)
      params <- qa_params(qa_measure(case$kind), case$style, case$scenario)
      params$cov_name <- data@covariates[[1]]@cov.name
      result <- rcmetar.run.analysis(
        data,
        list(version=1, method= "meta.regression", params = params, workflow = "meta-regression")
      )
      plot.data <- local({
        env <- new.env(parent = emptyenv())
        load(paste0(unname(result$plot_params_paths[["Regression Plot"]]), ".plotdata"), envir = env)
        env$plot.data
      })
      rcmetar.draw.regression.plot(plot.data, image)
      bytes <- file.info(image)$size
    }, error = function(e) {
      err <<- conditionMessage(e)
    })
    rows[[i]] <- data.frame(
      case = id,
      family = "regression",
      kind = case$kind,
      workflow = case$workflow,
      style = case$style,
      scenario = case$scenario,
      image = image,
      bytes = bytes,
      error = err,
      stringsAsFactors = FALSE
    )
  }
  manifest <- do.call(rbind, rows)
  utils::write.csv(manifest, file.path(output.root, "manifest.csv"), row.names = FALSE)
  manifest
}

if (identical(environment(), globalenv())) {
  repo.root <- qa_find_repo_root()
  qa_load_rcmetar(repo.root)
  output.root <- qa_root(repo.root)
  manifest <- qa_render_matrix(output.root)
  cat("Rendered", nrow(manifest), "bubble plot QA cases to", output.root, "\n")
  if (any(!is.na(manifest$error))) {
    print(manifest[!is.na(manifest$error), ])
    quit(status = 1)
  }
}
