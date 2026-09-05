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
  fixture$params$bp_outpath <- tempfile(fileext = ".png")
  fixture$params$bp_display_path <- tempfile(pattern = "bubble-display-", fileext = ".svg")

  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "meta.regression", params = fixture$params, workflow = "meta-regression")
  )
  plot.path <- unname(result$plot_params_paths[["Regression Plot"]])
  bundle <- bubble_load_saved_plot_data(plot.path)

  expect_true(result$plot_capabilities[["Regression Plot"]]$editable)
  expect_equal(
    unname(result$display_images[["Regression Plot"]]),
    fixture$params$bp_display_path
  )
  expect_true(file.exists(fixture$params$bp_outpath))
  expect_true(file.exists(fixture$params$bp_display_path))
  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$plot_type, "meta_regression_bubble")
  expect_equal(bundle$bp_style, "default")
  expect_equal(bundle$moderator$name, "latitude")
  expect_true(inherits(bundle$res, "rma"))
  expect_equal(length(bundle$effects$ES), length(fixture$data@study.names))
  expect_equal(bundle$slab, fixture$data@study.names)
  expect_true(all(file.exists(paste0(plot.path, c(".data", ".params", ".res")))))
})

test_that("bubble plot interval legend follows the configured confidence level", {
  bundle <- list(
    params = list(conf.level = 90, bp_show_prediction_interval = TRUE)
  )

  expect_equal(
    RCMetaR:::rcmetar.bubble.legend.labels(bundle),
    c("Studies", "Regression line", "90% CI", "90% PI")
  )
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

test_that("bubble plot text ceilings do not mutate source labels or effects", {
  fixture <- bubble_binary_fixture("default")
  original.name <- paste(rep("Long bubble study identity", 6), collapse=" ")
  fixture$data@study.names[[1]] <- original.name
  original.y <- fixture$data@y
  fixture$params$bp_xlabel <- paste(rep("Long moderator axis", 8), collapse=" ")
  res <- rma.uni(yi=fixture$data@y, sei=fixture$data@SE, mods=~fixture$data@covariates[[1]]@cov.vals)

  bundle <- rcmetar.create.metafor.bubble.bundle(fixture$data, fixture$params, res)

  expect_identical(fixture$data@study.names[[1]], original.name)
  expect_identical(fixture$data@y, original.y)
  expect_identical(bundle$slab[[1]], original.name)
  expect_equal(nchar(bundle$xlabel), 80)

  fixture$params$bp_xlabel <- "[default]"
  fixture$data@covariates[[1]]@cov.name <- paste(rep("Long moderator name", 8), collapse=" ")
  default.bundle <- rcmetar.create.metafor.bubble.bundle(fixture$data, fixture$params, res)
  expect_equal(nchar(default.bundle$xlabel), 80)
  expect_gt(nchar(default.bundle$moderator$name), 80)
})

test_that("metafor bubble plot renderer supports Default, RevMan, and BMJ styles", {
  for (style in c("default", "revman", "bmj")) {
    fixture <- bubble_binary_fixture(style, long.labels = TRUE)
    fixture$params$bp_show_prediction_interval <- TRUE

    result <- rcmetar.run.analysis(
      fixture$data,
      list(version=1, method= "meta.regression", params = fixture$params, workflow = "meta-regression")
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
    expect_false(file.exists(rcmetar.plot.canonical_svg_path(png_path)))
    expect_false(file.exists(rcmetar.plot.canonical_svg_path(pdf_path)))
    expect_gte(unname(dims[["width"]]), 2000)
    expect_gte(unname(dims[["height"]]), 1400)
  }
})

test_that("editable bubble options survive bundle regeneration", {
  fixture <- bubble_binary_fixture("default")
  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "meta.regression", params = fixture$params, workflow = "meta-regression")
  )
  params <- fixture$params
  params$bp_style <- "bmj"
  params$bp_accent_color <- "#123456"
  params$bp_point_size_multiplier <- 1.5
  params$bp_xlabel <- "Latitude (degrees)"
  params$bp_plot_lb <- "10"
  params$bp_plot_ub <- "60"
  params$bp_xticks <- "10, 30, 50"
  params$bp_show_confidence_band <- FALSE

  bundle <- rcmetar.regenerate.regression.plot.data(fixture$data, result$res, params)
  style.args <- rcmetar.bubble.style.args(bundle)

  expect_equal(bundle$bp_style, "bmj")
  expect_equal(bundle$xlabel, "Latitude (degrees)")
  expect_equal(style.args$plim, c(0.75, 4.5))
  expect_equal(rcmetar.bubble.xlim(bundle), c(10, 60))
  expect_equal(rcmetar.bubble.x.ticks(bundle), c(10, 30, 50))
  expect_false(rcmetar.bubble.param.is.true(bundle, "bp_show_confidence_band", TRUE))
})

test_that("Bubble Plot moderator ticks adapt to observed values and honor overrides", {
  fixture <- bubble_binary_fixture("default")
  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "meta.regression", params = fixture$params, workflow = "meta-regression")
  )
  bundle <- rcmetar.regenerate.regression.plot.data(fixture$data, result$res, fixture$params)
  limits <- rcmetar.bubble.xlim(bundle)
  ticks <- rcmetar.bubble.x.ticks(bundle)

  expect_gte(length(ticks), 3)
  expect_lte(length(ticks), 7)
  expect_true(all(ticks >= limits[[1]] & ticks <= limits[[2]]))

  bundle$params$bp_xticks <- c(12, 24, 48)
  expect_equal(rcmetar.bubble.x.ticks(bundle), c(12, 24, 48))
})
