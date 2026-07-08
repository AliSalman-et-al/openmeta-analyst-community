dir.create("r_tmp", showWarnings = FALSE)

bubble_binary_params <- function(style = "default") {
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
    fp_outpath = file.path("r_tmp", "bubble_forest.png"),
    rm.method = "DL",
    adjust = 0.5,
    fp_plot_ub = "[default]",
    fp_col1_str = "Study or Subgroup",
    measure = "OR",
    fp_xlabel = "[default]",
    fp_show_summary_line = TRUE,
    create.plot = TRUE,
    write.to.file = FALSE
  )
}

bubble_binary_fixture <- function(style = "default", long.labels = FALSE) {
  labels <- c("Aaronson", "Ferguson", "Rosenthal", "Hart", "Frimodt-Moller", "Stein", "Vandiviere", "TPT Madras")
  if (long.labels) {
    labels <- paste(labels, "extended multicentre tuberculosis prevention cohort")
  }
  params <- bubble_binary_params(style)
  params$cov_name <- "latitude"
  data <- new(
    "BinaryData",
    g1O1 = c(4, 6, 3, 62, 33, 180, 8, 505),
    g1O2 = c(119, 300, 228, 13536, 5036, 1361, 2537, 87886),
    g2O1 = c(11, 29, 11, 248, 47, 372, 10, 499),
    g2O2 = c(128, 274, 209, 12619, 5761, 1079, 619, 87892),
    study.names = labels,
    years = as.integer(1991:1998),
    covariates = list(
      new("CovariateValues", cov.name = "latitude", cov.vals = c(44, 55, 42, 52, 13, 44, 19, 13), cov.type = "continuous", ref.var = "44")
    )
  )
  data <- rcmetar.prepare.analysis.data(data, params)
  list(data = data, params = params)
}

bubble_png_dimensions <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con))
  bytes <- readBin(con, "integer", n = 24, size = 1, signed = FALSE, endian = "big")
  c(
    width = sum(bytes[17:20] * 256^(3:0)),
    height = sum(bytes[21:24] * 256^(3:0))
  )
}

bubble_load_saved_plot_data <- function(path) {
  env <- new.env(parent = emptyenv())
  load(paste0(path, ".plotdata"), envir = env)
  env$plot.data
}

test_that("meta-regression stores a self-contained metafor bubble plot bundle", {
  fixture <- bubble_binary_fixture("default")

  result <- rcmetar.run.analysis(
    fixture$data,
    list(method = "meta.regression", params = fixture$params, workflow = "meta-regression")
  )
  bundle <- bubble_load_saved_plot_data(unname(result$plot_params_paths[["Regression Plot"]]))

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$plot_type, "meta_regression_bubble")
  expect_equal(bundle$bp_style, "default")
  expect_equal(bundle$moderator$name, "latitude")
  expect_true(inherits(bundle$res, "rma"))
  expect_equal(length(bundle$effects$ES), length(fixture$data@study.names))
  expect_equal(bundle$slab, fixture$data@study.names)
})

test_that("meta-regression bubble plot redraws reject legacy non-metafor payloads", {
  fixture <- bubble_binary_fixture("default")
  legacy.plot.data <- list(
    fitted.line = list(intercept = 0, slope = 1),
    types = rep(0, length(fixture$data@study.names)),
    effects = list(ES = fixture$data@y, se = fixture$data@SE),
    covariate = list(varname = "latitude", values = fixture$data@covariates[[1]]@cov.vals),
    xlabel = "latitude",
    ylabel = "Odds Ratio"
  )

  expect_error(
    create.plot.data.reg(fixture$data, fixture$params, list(intercept = 0, slope = 1)),
    "metafor rma result"
  )
  expect_error(
    rcmetar.draw.regression.plot(legacy.plot.data, tempfile(fileext = ".png")),
    "metafor-backed plot bundle"
  )
})

test_that("metafor bubble plot renderer supports Default, RevMan, and BMJ styles", {
  for (style in c("default", "revman", "bmj")) {
    fixture <- bubble_binary_fixture(style, long.labels = TRUE)
    fixture$params$bp_show_prediction_interval <- TRUE

    result <- rcmetar.run.analysis(
      fixture$data,
      list(method = "meta.regression", params = fixture$params, workflow = "meta-regression")
    )
    bundle <- bubble_load_saved_plot_data(unname(result$plot_params_paths[["Regression Plot"]]))

    expect_equal(bundle$bp_style, style)
    png_path <- tempfile(fileext = ".png")
    pdf_path <- tempfile(fileext = ".pdf")
    rcmetar.draw.regression.plot(bundle, png_path)
    rcmetar.draw.regression.plot(bundle, pdf_path)

    dims <- bubble_png_dimensions(png_path)
    expect_gt(file.info(png_path)$size, 1000)
    expect_gt(file.info(pdf_path)$size, 1000)
    expect_gte(unname(dims[["width"]]), 2000)
    expect_gte(unname(dims[["height"]]), 1400)
  }
})
