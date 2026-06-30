dir.create("r_tmp", showWarnings = FALSE)

base_plot_params <- function(measure) {
  list(
    conf.level = 95,
    digits = 3,
    fp_col2_str = "[default]",
    fp_show_col4 = FALSE,
    to = "only0",
    fp_col4_str = "Ev/Ctrl",
    fp_xticks = "[default]",
    fp_col3_str = "[default]",
    fp_show_col3 = TRUE,
    fp_show_col2 = TRUE,
    fp_show_col1 = TRUE,
    fp_plot_lb = "[default]",
    fp_outpath = file.path("r_tmp", paste0("forest_", measure, ".png")),
    rm.method = "DL",
    adjust = 0.5,
    fp_plot_ub = "[default]",
    fp_col1_str = "Studies",
    measure = measure,
    fp_xlabel = "[default]",
    fp_show_summary_line = TRUE,
    create.plot = FALSE,
    write.to.file = FALSE
  )
}

binary_fixture <- function() {
  params <- base_plot_params("OR")
  params$cov_name <- "groups"
  data <- new(
    "BinaryData",
    g1O1 = c(4, 6, 3, 62, 33, 180),
    g1O2 = c(119, 300, 228, 13536, 5036, 1361),
    g2O1 = c(11, 29, 11, 248, 47, 372),
    g2O2 = c(128, 274, 209, 12619, 5761, 1079),
    study.names = c("Aaronson", "Ferguson", "Rosenthal", "Hart", "Frimodt-Moller", "Stein"),
    years = as.integer(1991:1996),
    covariates = list(
      new("CovariateValues", cov.name = "groups", cov.vals = c("1", "1", "2", "2", "1", "2"), cov.type = "factor", ref.var = "1")
    )
  )
  effects <- compute.for.one.bin.study(data, params)
  data@y <- effects$yi
  data@SE <- sqrt(effects$vi)
  list(data = data, params = params)
}

continuous_fixture <- function() {
  params <- base_plot_params("MD")
  params$cov_name <- "groups"
  data <- new(
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
      new("CovariateValues", cov.name = "groups", cov.vals = c("1", "1", "2", "1", "2", "2"), cov.type = "factor", ref.var = "1")
    )
  )
  effects <- compute.for.one.cont.study(data, params)
  data@y <- effects$yi
  data@SE <- sqrt(effects$vi)
  list(data = data, params = params)
}

diagnostic_fixture <- function(measure = "Sens") {
  params <- base_plot_params(measure)
  params$cov_name <- "quality"
  data <- new(
    "DiagnosticData",
    TP = c(19, 8, 41, 5, 45, 8),
    FN = c(10, 2, 12, 2, 32, 2),
    TN = c(81, 13, 49, 18, 165, 32),
    FP = c(1, 9, 1, 1, 58, 6),
    study.names = c("Kinderman", "Lecart Lenfant", "Piver", "Piver Barlow", "Kolbenstvedt", "Lehman"),
    years = as.integer(1970:1975),
    covariates = list(
      new("CovariateValues", cov.name = "quality", cov.vals = c("A", "A", "B", "B", "A", "B"), cov.type = "factor", ref.var = "A")
    )
  )
  effects <- get.res.for.one.diag.study(data, params)
  data@y <- effects$b
  data@SE <- effects$se
  list(data = data, params = params)
}

expect_analysis_result <- function(result) {
  expect_type(result, "list")
  expect_true(any(c("Summary", "images", "res", "res.info") %in% names(result)))
}

test_that("representative binary analysis paths execute", {
  fixture <- binary_fixture()
  expect_analysis_result(binary.random(fixture$data, fixture$params))
  expect_analysis_result(cum.ma.binary("binary.random", fixture$data, fixture$params))
  expect_analysis_result(loo.ma.binary("binary.random", fixture$data, fixture$params))
  expect_analysis_result(subgroup.ma.binary("binary.random", fixture$data, fixture$params))
})

test_that("representative continuous analysis paths execute", {
  fixture <- continuous_fixture()
  expect_analysis_result(continuous.random(fixture$data, fixture$params))
  expect_analysis_result(cum.ma.continuous("continuous.random", fixture$data, fixture$params))
  expect_analysis_result(loo.ma.continuous("continuous.random", fixture$data, fixture$params))
  expect_analysis_result(subgroup.ma.continuous("continuous.random", fixture$data, fixture$params))
})

test_that("representative diagnostic analysis paths execute", {
  fixture <- diagnostic_fixture("Sens")
  expect_analysis_result(diagnostic.random(fixture$data, fixture$params))
  expect_analysis_result(cum.ma.diagnostic("diagnostic.random", fixture$data, fixture$params))
  expect_analysis_result(loo.ma.diagnostic("diagnostic.random", fixture$data, fixture$params))
  expect_analysis_result(subgroup.ma.diagnostic("diagnostic.random", fixture$data, fixture$params, get.cov(fixture$data, "quality")))
})

test_that("HSROC feasibility requires count-based diagnostic data", {
  entered.effects <- new(
    "DiagnosticData",
    y = c(qlogis(0.65), qlogis(0.80), qlogis(0.77), qlogis(0.71), qlogis(0.58)),
    SE = c(0.14, 0.18, 0.09, 0.26, 0.08),
    study.names = c("a", "b", "c", "d", "e")
  )
  count.data <- diagnostic_fixture("Sens")$data

  expect_false(diagnostic.hsroc.is.feasible(entered.effects, "Sens"))
  expect_true(diagnostic.hsroc.is.feasible(count.data, "Sens"))
  expect_identical(diagnostic.hsroc.ml.is.feasible, diagnostic.hsroc.is.feasible)
})
