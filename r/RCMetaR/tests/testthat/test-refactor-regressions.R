test_that("continuous study exports retain the second arm standard deviation", {
  data <- new(
    "ContinuousData",
    N1 = 20,
    mean1 = 10,
    sd1 = 2,
    N2 = 22,
    mean2 = 8,
    sd2 = 5,
    y = 2,
    SE = 0.8,
    study.names = "Study 1",
    years = as.integer(2020),
    covariates = list()
  )
  params <- list(measure = "MD", conf.level = 95, digits = 2)
  result <- list(study.weights = 1)
  output_path <- tempfile(fileext = ".csv")

  write.cont.study.data.to.file(data, params, result, output_path)

  expect_equal(read.csv(output_path)$sd2, 5)
})

test_that("diagnostic negative likelihood ratio uses negative-case counts", {
  data <- new(
    "DiagnosticData",
    TP = 10,
    FN = 20,
    TN = 30,
    FP = 40,
    y = numeric(),
    SE = numeric(),
    g1.name = "Test",
    study.names = "Study 1",
    years = as.integer(2020),
    covariates = list()
  )

  result <- compute.diag.point.estimates(data, list(measure = "NLR"))
  expected <- sqrt((1 / 20) - (1 / 30) + (1 / 30) - (1 / 70))

  expect_equal(result@SE, expected)
})

test_that("subgroup plot data reads covariates from grouped data", {
  data <- new(
    "BinaryData",
    g1O1 = 1,
    g1O2 = 9,
    g2O1 = 2,
    g2O2 = 8,
    y = log(0.5),
    SE = 0.1,
    study.names = "Study",
    years = as.integer(2020),
    covariates = list(new(
      "CovariateValues",
      cov.name = "group",
      cov.vals = "A",
      cov.type = "factor",
      ref.var = "A"
    ))
  )
  params <- list(
    measure = "OR",
    conf.level = 95,
    digits = 2,
    fp_col1_str = "Study",
    fp_show_col1 = TRUE,
    fp_col2_str = "[default]",
    fp_show_col2 = TRUE,
    fp_col3_str = "[default]",
    fp_show_col3 = TRUE,
    fp_show_col4 = FALSE,
    fp_col4_str = "",
    fp_xlabel = "[default]",
    fp_show_summary_line = TRUE,
    fp_xticks = "[default]",
    fp_plot_lb = "[default]",
    fp_plot_ub = "[default]",
    fp.title = NULL
  )
  subgroup_data <- list(
    grouped.data = list(data),
    subgroup.list = "A",
    results = list(
      list(b = 0, ci.lb = -0.1, ci.ub = 0.1, I2 = NA, QEp = NA),
      list(b = 0, ci.lb = -0.1, ci.ub = 0.1, I2 = NA, QEp = NA)
    )
  )

  plot_data <- create.subgroup.plot.data.generic(
    subgroup_data,
    params,
    data.type = "binary",
    selected.cov = "group"
  )

  expect_identical(plot_data$covariate$varname, "group")
  expect_identical(as.character(plot_data$covariate$values), "A")
})
