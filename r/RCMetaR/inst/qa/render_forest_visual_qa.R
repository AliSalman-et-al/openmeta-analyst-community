#!/usr/bin/env Rscript

qa_find_repo_root <- function() {
  cwd <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
  parts <- strsplit(cwd, "/", fixed = TRUE)[[1]]
  for (i in seq_along(parts)) {
    candidate <- file.path(paste(parts[seq_len(length(parts) - i + 1)], collapse = "/"))
    if (file.exists(file.path(candidate, "r", "RCMetaR", "DESCRIPTION"))) {
      return(candidate)
    }
  }
  stop("Run this script from the rc-metastudio repository root or a child directory.", call. = FALSE)
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

qa_root <- function(repo.root) {
  root <- Sys.getenv("RCMETASTUDIO_QA_ROOT")
  if (!nzchar(root)) {
    root <- file.path(tempdir(), "rcmetastudio-forest-visual-qa")
  }
  dir.create(root, recursive = TRUE, showWarnings = FALSE)
  normalizePath(root, winslash = "/", mustWork = TRUE)
}

qa_scenario_settings <- function() {
  list(
    base = list(n = 7, stress = FALSE, sparse = FALSE, accent = NA_character_, headers = TRUE, annotation = TRUE, point = 1.0, digits = 2),
    stress = list(n = 16, stress = TRUE, sparse = FALSE, accent = "#008a5e", headers = TRUE, annotation = TRUE, point = 1.18, digits = 2),
    compact = list(n = 4, stress = FALSE, sparse = FALSE, accent = "#7c3f98", headers = FALSE, annotation = TRUE, point = 0.85, digits = 3),
    sparse = list(n = 6, stress = FALSE, sparse = TRUE, direct = FALSE, accent = "#2f5597", headers = TRUE, annotation = TRUE, point = 1.0, digits = 2),
    direct = list(n = 6, stress = FALSE, sparse = TRUE, direct = TRUE, accent = "#2f5597", headers = TRUE, annotation = TRUE, point = 1.0, digits = 2)
  )
}

qa_base_params <- function(measure, outpath, style, scenario) {
  default.accent <- if (identical(style, "revman")) "#000000" else "#2f5597"
  accent <- if (is.na(scenario$accent)) default.accent else scenario$accent
  list(
    conf.level = 95,
    digits = scenario$digits,
    fp_col2_str = "[default]",
    fp_show_col4 = !isTRUE(scenario$sparse),
    to = "only0",
    fp_col4_str = if (scenario$stress) "Comparator With Very Long Header" else "Control",
    fp_xticks = "[default]",
    fp_col3_str = if (scenario$stress) "Intervention With Very Long Header" else "Experimental",
    fp_show_col3 = !isTRUE(scenario$sparse),
    fp_show_col2 = !isTRUE(scenario$sparse),
    fp_show_col1 = TRUE,
    fp_plot_lb = "[default]",
    fp_outpath = outpath,
    rm.method = "DL",
    adjust = 0.5,
    fp_plot_ub = "[default]",
    fp_col1_str = if (scenario$stress) "Study or Subgroup With Long Header" else "Study or Subgroup",
    measure = measure,
    fp_xlabel = "[default]",
    fp_show_summary_line = TRUE,
    fp_show_headers = scenario$headers,
    fp_show_annotation = scenario$annotation,
    fp_style = style,
    fp_accent_color = accent,
    fp_point_size_multiplier = scenario$point,
    create.plot = NULL,
    write.to.file = FALSE
  )
}

qa_long_labels <- function(prefix, n, stress) {
  variants <- c("North Trial", "Central Evidence Cohort", "Long Named Study Arm", "Multi-site Follow-up")
  labels <- paste(prefix, sprintf("%02d", seq_len(n)), variants[((seq_len(n) - 1) %% length(variants)) + 1])
  if (isTRUE(stress)) {
    return(paste(labels, "with extended publication label", 1990 + seq_len(n), 2010 + seq_len(n)))
  }
  paste(prefix, seq_len(n))
}

qa_make_binary <- function(n, stress) {
  set.seed(if (stress) 104 else 101)
  g1O1 <- pmax(0, round(seq(2, 190, length.out = n) + rnorm(n, 0, 4)))
  g1O2 <- round(seq(30, 5400, length.out = n) + runif(n, 20, 210))
  g2O1 <- pmax(0, round(seq(5, 250, length.out = n) + rnorm(n, 0, 5)))
  g2O2 <- round(seq(35, 5600, length.out = n) + runif(n, 30, 240))
  if (stress && n >= 4) {
    g1O1[3] <- 0
    g1O2[3] <- 0
    g2O1[3] <- 0
    g2O2[3] <- 0
  }
  data <- new(
    "BinaryData",
    g1O1 = g1O1,
    g1O2 = g1O2,
    g2O1 = g2O1,
    g2O2 = g2O2,
    study.names = qa_long_labels("Binary", n, stress),
    years = as.integer(2000 + seq_len(n))
  )
  params <- qa_base_params("OR", tempfile(fileext = ".png"), "default", qa_scenario_settings()$base)
  effect <- compute.for.one.bin.study(data, params)
  data@y <- effect$yi
  data@SE <- sqrt(effect$vi)
  data
}

qa_make_binary_one_arm <- function(n, stress) {
  set.seed(if (stress) 154 else 151)
  events <- pmax(0, round(seq(2, 72, length.out = n) + rnorm(n, 0, 3)))
  nonevents <- round(seq(38, 720, length.out = n) + runif(n, 10, 90))
  if (stress && n >= 4) {
    events[3] <- 0
  }
  data <- new(
    "BinaryData",
    g1O1 = events,
    g1O2 = nonevents,
    study.names = qa_long_labels("One-arm Binary", n, stress),
    years = as.integer(2000 + seq_len(n))
  )
  params <- qa_base_params("PLO", tempfile(fileext = ".png"), "default", qa_scenario_settings()$base)
  effect <- compute.for.one.bin.study(data, params)
  data@y <- effect$yi
  data@SE <- sqrt(effect$vi)
  data
}

qa_make_continuous <- function(n, stress) {
  set.seed(if (stress) 204 else 201)
  data <- new(
    "ContinuousData",
    N1 = round(seq(18, 240, length.out = n)),
    mean1 = round(seq(8.2, 15.4, length.out = n) + rnorm(n, 0, .8), 2),
    sd1 = round(runif(n, 1.1, 3.8), 2),
    N2 = round(seq(20, 250, length.out = n)),
    mean2 = round(seq(8.9, 13.8, length.out = n) + rnorm(n, 0, .8), 2),
    sd2 = round(runif(n, 1.2, 4.0), 2),
    study.names = qa_long_labels("Continuous", n, stress),
    years = as.integer(2010 + seq_len(n))
  )
  params <- qa_base_params("MD", tempfile(fileext = ".png"), "default", qa_scenario_settings()$base)
  effect <- compute.for.one.cont.study(data, params)
  data@y <- effect$yi
  data@SE <- sqrt(effect$vi)
  data
}

qa_make_continuous_one_arm <- function(n, stress) {
  set.seed(if (stress) 254 else 251)
  data <- new(
    "ContinuousData",
    N1 = round(seq(18, 260, length.out = n)),
    mean1 = round(seq(8.2, 16.4, length.out = n) + rnorm(n, 0, .9), 2),
    sd1 = round(runif(n, 1.1, 4.4), 2),
    study.names = qa_long_labels("One-arm Continuous", n, stress),
    years = as.integer(2010 + seq_len(n))
  )
  params <- qa_base_params("TXMean", tempfile(fileext = ".png"), "default", qa_scenario_settings()$base)
  effect <- compute.for.one.cont.study(data, params)
  data@y <- effect$yi
  data@SE <- sqrt(effect$vi)
  data
}

qa_make_diagnostic <- function(n, stress) {
  set.seed(if (stress) 304 else 301)
  data <- new(
    "DiagnosticData",
    TP = round(seq(8, 130, length.out = n) + runif(n, 0, 8)),
    FN = round(seq(2, 38, length.out = n) + runif(n, 0, 5)),
    TN = round(seq(25, 210, length.out = n) + runif(n, 0, 10)),
    FP = round(seq(1, 52, length.out = n) + runif(n, 0, 5)),
    study.names = qa_long_labels("Diagnostic", n, stress),
    years = as.integer(2020 + seq_len(n))
  )
  params <- qa_base_params("Sens", tempfile(fileext = ".png"), "default", qa_scenario_settings()$base)
  compute.diag.point.estimates(data, params)
}

qa_make_entered_binary <- function(n, stress) {
  yi <- log(seq(0.68, 1.18, length.out = n))
  sei <- seq(0.16, 0.28, length.out = n)
  rcmetar.create.binary.data(
    y = yi,
    SE = sei,
    study.names = qa_long_labels("Entered Binary", n, stress),
    years = as.integer(2000 + seq_len(n))
  )
}

qa_make_entered_binary_one_arm <- function(n, stress) {
  yi <- logit(seq(0.06, 0.22, length.out = n))
  sei <- seq(0.14, 0.26, length.out = n)
  rcmetar.create.binary.data(
    y = yi,
    SE = sei,
    study.names = qa_long_labels("Entered One-arm Binary", n, stress),
    years = as.integer(2000 + seq_len(n))
  )
}

qa_make_entered_continuous <- function(n, stress) {
  rcmetar.create.continuous.data(
    y = seq(-0.45, 0.35, length.out = n),
    SE = seq(0.18, 0.30, length.out = n),
    study.names = qa_long_labels("Entered Continuous", n, stress),
    years = as.integer(2010 + seq_len(n))
  )
}

qa_make_entered_continuous_one_arm <- function(n, stress) {
  rcmetar.create.continuous.data(
    y = seq(7.5, 13.5, length.out = n),
    SE = seq(0.18, 0.32, length.out = n),
    study.names = qa_long_labels("Entered One-arm Continuous", n, stress),
    years = as.integer(2010 + seq_len(n))
  )
}

qa_make_entered_diagnostic <- function(n, stress) {
  rcmetar.create.diagnostic.data(
    y = logit(seq(0.70, 0.82, length.out = n)),
    SE = seq(0.16, 0.26, length.out = n),
    study.names = qa_long_labels("Entered Diagnostic", n, stress),
    years = as.integer(2020 + seq_len(n))
  )
}

qa_method_for <- function(kind) {
  switch(
    kind,
    binary_two_arm = "binary.random",
    binary_one_arm = "binary.random",
    continuous_two_arm = "continuous.random",
    continuous_one_arm = "continuous.random",
    diagnostic = "diagnostic.random"
  )
}

qa_measure_for <- function(kind) {
  switch(
    kind,
    binary_two_arm = "OR",
    binary_one_arm = "PLO",
    continuous_two_arm = "MD",
    continuous_one_arm = "TXMean",
    diagnostic = "Sens"
  )
}

qa_fixture_for <- function(kind, n, stress, direct = FALSE) {
  if (isTRUE(direct)) {
    return(switch(
      kind,
      binary_two_arm = qa_make_entered_binary(n, stress),
      binary_one_arm = qa_make_entered_binary_one_arm(n, stress),
      continuous_two_arm = qa_make_entered_continuous(n, stress),
      continuous_one_arm = qa_make_entered_continuous_one_arm(n, stress),
      diagnostic = qa_make_entered_diagnostic(n, stress)
    ))
  }
  switch(
    kind,
    binary_two_arm = qa_make_binary(n, stress),
    binary_one_arm = qa_make_binary_one_arm(n, stress),
    continuous_two_arm = qa_make_continuous(n, stress),
    continuous_one_arm = qa_make_continuous_one_arm(n, stress),
    diagnostic = qa_make_diagnostic(n, stress)
  )
}

qa_render_case <- function(kind, workflow, style, scenario.name, scenarios, output.root, format) {
  scenario <- scenarios[[scenario.name]]
  data <- qa_fixture_for(kind, scenario$n, scenario$stress, isTRUE(scenario$direct))
  case.name <- paste(kind, workflow, style, scenario.name, sep = "__")
  out <- file.path(output.root, paste0(case.name, ".", format))
  params <- qa_base_params(qa_measure_for(kind), out, style, scenario)
  result <- rcmetar.run.analysis(data, list(method = qa_method_for(kind), params = params, workflow = workflow))
  image.path <- unname(result$images[[1]])
  if (is.null(image.path) || !file.exists(image.path)) {
    stop("Missing image for ", case.name, call. = FALSE)
  }
  info <- file.info(image.path)
  cat(case.name, "|", image.path, "|", info$size, "bytes\n")
  data.frame(
    case = case.name,
    kind = kind,
    workflow = workflow,
    style = style,
    scenario = scenario.name,
    image = normalizePath(image.path, winslash = "\\", mustWork = TRUE),
    bytes = info$size,
    stringsAsFactors = FALSE
  )
}

qa_render_matrix <- function(output.root = qa_root(qa_find_repo_root()), format = "png") {
  dir.create(output.root, recursive = TRUE, showWarnings = FALSE)
  output.root <- normalizePath(output.root, winslash = "/", mustWork = TRUE)
  scenarios <- qa_scenario_settings()
  cases <- expand.grid(
    kind = c("binary_two_arm", "binary_one_arm", "continuous_two_arm", "continuous_one_arm", "diagnostic"),
    workflow = c("standard", "cumulative", "leave-one-out"),
    style = c("default", "revman", "bmj"),
    scenario = names(scenarios),
    stringsAsFactors = FALSE
  )
  rows <- lapply(seq_len(nrow(cases)), function(i) {
    tryCatch(
      qa_render_case(cases$kind[i], cases$workflow[i], cases$style[i], cases$scenario[i], scenarios, output.root, format),
      error = function(error) {
        case.name <- paste(cases[i, ], collapse = "__")
        cat("ERROR", case.name, conditionMessage(error), "\n")
        data.frame(
          case = case.name,
          kind = cases$kind[i],
          workflow = cases$workflow[i],
          style = cases$style[i],
          scenario = cases$scenario[i],
          image = NA_character_,
          bytes = NA_real_,
          error = conditionMessage(error),
          stringsAsFactors = FALSE
        )
      }
    )
  })
  manifest <- do.call(rbind, rows)
  manifest.path <- file.path(output.root, "manifest.csv")
  write.csv(manifest, manifest.path, row.names = FALSE)
  cat("MANIFEST", manifest.path, "\n")
  invisible(manifest)
}

if (sys.nframe() == 0) {
  repo.root <- qa_find_repo_root()
  qa_load_rcmetar(repo.root)
  format <- Sys.getenv("RCMETASTUDIO_QA_FORMAT", "png")
  qa_render_matrix(qa_root(repo.root), format)
}
