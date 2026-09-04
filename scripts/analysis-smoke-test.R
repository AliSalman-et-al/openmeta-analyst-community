options(warn = 1)

analysis_scratch_dir <- Sys.getenv(
  "RCMS_ANALYSIS_SCRATCH_DIR",
  unset = file.path(tempdir(), "rc-metastudio-analysis")
)
dir.create(analysis_scratch_dir, recursive = TRUE, showWarnings = FALSE)
suppressPackageStartupMessages(library(RCMetaR))
rcmetar.set.global.conf.level(95)

failures <- list()
passes <- character()

record <- function(name, expr) {
  cat("RUN", name, "\n")
  result <- try(force(expr), silent = TRUE)
  if (inherits(result, "try-error")) {
    failures[[name]] <<- as.character(result)
    cat("FAIL", name, "\n")
    rcmetar.graphics.off()
    return(invisible(NULL))
  }
  if (!is.list(result) || length(result) == 0) {
    failures[[name]] <<- "Returned an empty or non-list result."
    cat("FAIL", name, "\n")
    return(invisible(NULL))
  }
  expected <- intersect(names(result), c("Summary", "images", "res", "res.info"))
  if (length(expected) == 0) {
    failures[[name]] <<- paste("Unexpected result names:", paste(names(result), collapse = ", "))
    cat("FAIL", name, "\n")
    rcmetar.graphics.off()
    return(invisible(NULL))
  }
  passes <<- c(passes, name)
  cat("PASS", name, "\n")
  invisible(result)
}

base_params <- function(measure) {
  list(
    "conf.level" = 95,
    "digits" = 3,
    "fp_col2_str" = "[default]",
    "fp_show_col4" = FALSE,
    "to" = "only0",
    "fp_col4_str" = "Ev/Ctrl",
    "fp_xticks" = "[default]",
    "fp_col3_str" = "[default]",
    "fp_show_col3" = TRUE,
    "fp_show_col2" = TRUE,
    "fp_show_col1" = TRUE,
    "fp_plot_lb" = "[default]",
    "fp_outpath" = file.path(analysis_scratch_dir, "forest.png"),
    "rm.method" = "DL",
    "adjust" = 0.5,
    "fp_plot_ub" = "[default]",
    "fp_col1_str" = "Study or Subgroup",
    "measure" = measure,
    "fp_xlabel" = "[default]",
    "fp_show_summary_line" = TRUE,
    "create.plot" = TRUE,
    "write.to.file" = FALSE
  )
}

binary_params <- base_params("OR")
binary_params$cov_name <- "groups"
binary_data <- new(
  "BinaryData",
  g1O1 = c(4, 6, 3, 62, 33, 180, 8, 505),
  g1O2 = c(119, 300, 228, 13536, 5036, 1361, 2537, 87886),
  g2O1 = c(11, 29, 11, 248, 47, 372, 10, 499),
  g2O2 = c(128, 274, 209, 12619, 5761, 1079, 619, 87892),
  study.names = c("Aaronson", "Ferguson", "Rosenthal", "Hart", "Frimodt-Moller", "Stein", "Vandiviere", "TPT Madras"),
  years = as.integer(1991:1998),
  covariates = list(
    new("CovariateValues", cov.name = "latitude", cov.vals = c(44, 55, 42, 52, 13, 44, 19, 13), cov.type = "continuous", ref.var = "44"),
    new("CovariateValues", cov.name = "groups", cov.vals = c("1", "1", "2", "2", "1", "2", "2", "1"), cov.type = "factor", ref.var = "1")
  )
)
binary_data <- rcmetar.prepare.analysis.data(binary_data, binary_params)

continuous_params <- base_params("MD")
continuous_params$cov_name <- "groups"
continuous_data <- new(
  "ContinuousData",
  N1 = c(60, 65, 40, 200, 50, 85),
  mean1 = c(94, 98, 98, 94, 98, 96),
  sd1 = c(22, 21, 28, 19, 21, 21),
  N2 = c(60, 65, 40, 200, 45, 85),
  mean2 = c(92, 92, 88, 82, 88, 92),
  sd2 = c(20, 22, 26, 17, 22, 22),
  study.names = c("Carroll", "Grant", "Peck", "Donat", "Stewart", "Young"),
  years = as.integer(2001:2006),
  covariates = list(
    new("CovariateValues", cov.name = "dose", cov.vals = c(10, 20, 15, 35, 25, 30), cov.type = "continuous", ref.var = "10"),
    new("CovariateValues", cov.name = "groups", cov.vals = c("1", "1", "2", "1", "2", "2"), cov.type = "factor", ref.var = "1")
  )
)
continuous_data <- rcmetar.prepare.analysis.data(continuous_data, continuous_params)

diagnostic_base <- new(
  "DiagnosticData",
  TP = c(19, 8, 41, 5, 45, 8, 5, 15, 16, 4, 8, 10, 2, 7, 44, 8, 4),
  FN = c(10, 2, 12, 2, 32, 2, 1, 11, 8, 2, 10, 4, 6, 7, 12, 1, 0),
  TN = c(81, 13, 49, 18, 165, 32, 7, 52, 24, 25, 70, 55, 23, 30, 135, 37, 14),
  FP = c(1, 9, 1, 1, 58, 6, 8, 17, 11, 8, 12, 4, 5, 10, 50, 3, 3),
  study.names = c("Kinderman", "Lecart Lenfant", "Piver", "Piver Barlow", "Kolbenstvedt", "Lehman", "Brown", "Lagasse", "Kjorstad", "Ashraf", "De Muylder", "Smales", "Feigen", "Swart", "Heller", "La Fianza", "Stellato"),
  years = as.integer(1970:1986),
  covariates = list(
    new("CovariateValues", cov.name = "quality", cov.vals = c("A", "A", "B", "B", "A", "B", "A", "A", "B", "A", "B", "B", "A", "B", "A", "B", "A"), cov.type = "factor", ref.var = "A"),
    new("CovariateValues", cov.name = "threshold", cov.vals = c(1.1, 1.3, 2.1, 2.5, 1.7, 2.8, 1.2, 1.4, 2.3, 1.6, 2.6, 2.2, 1.5, 2.4, 1.8, 2.7, 1.9), cov.type = "continuous", ref.var = "1.1")
  )
)

diag_with_measure <- function(measure) {
  data <- diagnostic_base
  params <- base_params(measure)
  params$cov_name <- "quality"
  data <- rcmetar.prepare.analysis.data(data, params)
  list(data = data, params = params)
}

binary_methods <- c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random")
for (method in binary_methods) {
  record(paste("binary standard", method), rcmetar.run.analysis(binary_data, list(version=1, method= method, params = binary_params)))
  record(paste("binary cumulative", method), rcmetar.run.analysis(binary_data, list(version=1, method= method, params = binary_params, workflow = "cumulative")))
  record(paste("binary leave-one-out", method), rcmetar.run.analysis(binary_data, list(version=1, method= method, params = binary_params, workflow = "leave-one-out")))
  record(paste("binary subgroup", method), rcmetar.run.analysis(binary_data, list(version=1, method= method, params = binary_params, workflow = "subgroup")))
}
record("binary meta-regression continuous covariate", rcmetar.run.analysis(binary_data, list(version=1, method= "meta.regression", params = binary_params, workflow = "meta-regression")))

continuous_methods <- c("continuous.fixed", "continuous.random")
for (method in continuous_methods) {
  record(paste("continuous standard", method), rcmetar.run.analysis(continuous_data, list(version=1, method= method, params = continuous_params)))
  record(paste("continuous cumulative", method), rcmetar.run.analysis(continuous_data, list(version=1, method= method, params = continuous_params, workflow = "cumulative")))
  record(paste("continuous leave-one-out", method), rcmetar.run.analysis(continuous_data, list(version=1, method= method, params = continuous_params, workflow = "leave-one-out")))
  record(paste("continuous subgroup", method), rcmetar.run.analysis(continuous_data, list(version=1, method= method, params = continuous_params, workflow = "subgroup")))
}
record("continuous meta-regression continuous covariate", rcmetar.run.analysis(continuous_data, list(version=1, method= "meta.regression", params = continuous_params, workflow = "meta-regression")))

diagnostic_metric_methods <- list(
  Sens = c("diagnostic.fixed.inv.var", "diagnostic.random"),
  Spec = c("diagnostic.fixed.inv.var", "diagnostic.random"),
  DOR = c("diagnostic.fixed.inv.var", "diagnostic.fixed.peto", "diagnostic.random"),
  NLR = c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.random"),
  PLR = c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.random")
)

for (metric in names(diagnostic_metric_methods)) {
  fixture <- diag_with_measure(metric)
  for (method in diagnostic_metric_methods[[metric]]) {
    record(paste("diagnostic standard", metric, method), rcmetar.run.analysis(fixture$data, list(version=1, method= method, params = fixture$params)))
    record(paste("diagnostic cumulative", metric, method), rcmetar.run.analysis(fixture$data, list(version=1, method= method, params = fixture$params, workflow = "cumulative")))
    record(paste("diagnostic leave-one-out", metric, method), rcmetar.run.analysis(fixture$data, list(version=1, method= method, params = fixture$params, workflow = "leave-one-out")))
    record(paste("diagnostic subgroup", metric, method), rcmetar.run.analysis(fixture$data, list(version=1, method= method, params = fixture$params, workflow = "subgroup")))
  }
}

multi_fixture <- diag_with_measure("Sens")
multi_sens_params <- base_params("Sens")
multi_sens_params$cov_name <- "quality"
multi_spec_params <- base_params("Spec")
multi_spec_params$cov_name <- "quality"
record(
  "diagnostic multiple standard sens/spec",
  rcmetar.run.diagnostic.analyses(
    multi_fixture$data,
    c("diagnostic.random", "diagnostic.random"),
    list(multi_sens_params, multi_spec_params), version=1
  )
)
record(
  "diagnostic multiple cumulative sens/spec",
  rcmetar.run.diagnostic.analyses(
    multi_fixture$data,
    c("diagnostic.random", "diagnostic.random"),
    list(multi_sens_params, multi_spec_params), version=1,
    workflow = "cumulative"
  )
)
record(
  "diagnostic multiple leave-one-out sens/spec",
  rcmetar.run.diagnostic.analyses(
    multi_fixture$data,
    c("diagnostic.random", "diagnostic.random"),
    list(multi_sens_params, multi_spec_params), version=1,
    workflow = "leave-one-out"
  )
)
record(
  "diagnostic multiple subgroup sens/spec",
  rcmetar.run.diagnostic.analyses(
    multi_fixture$data,
    c("diagnostic.random", "diagnostic.random"),
    list(multi_sens_params, multi_spec_params), version=1,
    workflow = "subgroup"
  )
)
diagnostic_meta_regression_params <- base_params("Sens")
diagnostic_meta_regression_params$cov_name <- "quality"
diagnostic_meta_regression_params$estimator <- "REML"
record("diagnostic meta-regression factor covariate", rcmetar.run.analysis(multi_fixture$data, list(version=1, method= "diagnostic.reitsma", params = diagnostic_meta_regression_params, workflow = "meta-regression")))

cat("\nSUMMARY\n")
cat("Passed:", length(passes), "\n")
cat("Failed:", length(failures), "\n")
if (length(failures) > 0) {
  for (name in names(failures)) {
    cat("\n---", name, "---\n")
    cat(failures[[name]], "\n")
  }
  quit(status = 1)
}

quit(status = 0)
