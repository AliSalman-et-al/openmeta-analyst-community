dir.create("r_tmp", showWarnings = FALSE)

metafor_binary_params <- function(outpath) {
  list(
    conf.level = 95,
    digits = 3,
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
    fp_outpath = outpath,
    rm.method = "DL",
    adjust = 0.5,
    fp_plot_ub = "[default]",
    fp_col1_str = "Studies",
    measure = "OR",
    fp_xlabel = "[default]",
    fp_show_summary_line = TRUE,
    fp_style = "default",
    create.plot = FALSE,
    write.to.file = FALSE
  )
}

metafor_binary_fixture <- function(studies = 6) {
  data <- new(
    "BinaryData",
    g1O1 = c(4, 6, 3, 62, 33, 180)[seq_len(studies)],
    g1O2 = c(119, 300, 228, 13536, 5036, 1361)[seq_len(studies)],
    g2O1 = c(11, 29, 11, 248, 47, 372)[seq_len(studies)],
    g2O2 = c(128, 274, 209, 12619, 5761, 1079)[seq_len(studies)],
    study.names = c("Aaronson", "Ferguson", "Rosenthal", "Hart", "Frimodt-Moller", "Stein")[seq_len(studies)],
    years = as.integer(1991:(1990 + studies))
  )
  params <- metafor_binary_params(file.path("r_tmp", paste0("forest_metafor_", studies, ".png")))
  effects <- compute.for.one.bin.study(data, params)
  data@y <- effects$yi
  data@SE <- sqrt(effects$vi)
  list(data = data, params = params)
}

metafor_continuous_params <- function(outpath) {
  params <- metafor_binary_params(outpath)
  params$measure <- "MD"
  params$fp_col3_str <- "Treatment"
  params$fp_col4_str <- "Control"
  params$create.plot <- TRUE
  params
}

metafor_continuous_fixture <- function(studies = 5) {
  data <- new(
    "ContinuousData",
    N1 = c(22, 35, 18, 41, 29)[seq_len(studies)],
    mean1 = c(8.2, 7.6, 9.1, 6.8, 7.4)[seq_len(studies)],
    sd1 = c(1.5, 1.8, 1.2, 2.1, 1.7)[seq_len(studies)],
    N2 = c(20, 32, 21, 38, 31)[seq_len(studies)],
    mean2 = c(9.0, 8.5, 9.7, 7.9, 8.1)[seq_len(studies)],
    sd2 = c(1.6, 1.7, 1.4, 2.0, 1.5)[seq_len(studies)],
    study.names = c("Allen", "Baker", "Cole", "Diaz", "Evans")[seq_len(studies)],
    years = as.integer(2001:(2000 + studies))
  )
  params <- metafor_continuous_params(file.path("r_tmp", paste0("forest_metafor_cont_", studies, ".png")))
  effects <- compute.for.one.cont.study(data, params)
  data@y <- effects$yi
  data@SE <- sqrt(effects$vi)
  list(data = data, params = params)
}

metafor_diagnostic_params <- function(outpath, measure = "Sens") {
  params <- metafor_binary_params(outpath)
  params$measure <- measure
  params$create.plot <- TRUE
  params
}

metafor_diagnostic_fixture <- function(studies = 5, measure = "Sens") {
  data <- new(
    "DiagnosticData",
    TP = c(42, 51, 37, 66, 49)[seq_len(studies)],
    FN = c(8, 11, 13, 9, 15)[seq_len(studies)],
    TN = c(88, 73, 96, 81, 77)[seq_len(studies)],
    FP = c(12, 16, 10, 14, 18)[seq_len(studies)],
    study.names = c("Ibrahim", "Jones", "Khan", "Lopez", "Miller")[seq_len(studies)],
    years = as.integer(2011:(2010 + studies))
  )
  params <- metafor_diagnostic_params(file.path("r_tmp", paste0("forest_metafor_diag_", measure, "_", studies, ".png")), measure)
  data <- compute.diag.point.estimates(data, params)
  list(data = data, params = params)
}

read_png_dimensions <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con))
  bytes <- readBin(con, "integer", n = 24, size = 1, signed = FALSE, endian = "big")
  c(
    width = sum(bytes[17:20] * 256^(3:0)),
    height = sum(bytes[21:24] * 256^(3:0))
  )
}

load_saved_plot_data <- function(path) {
  env <- new.env(parent = emptyenv())
  load(paste0(path, ".plotdata"), envir = env)
  env$plot.data
}

test_that("binary Default Forest Style builds a self-contained metafor render bundle", {
  fixture <- metafor_binary_fixture()
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits,
    add = c(fixture$params$adjust, fixture$params$adjust),
    to = as.character(fixture$params$to)
  )

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$data_type, "binary")
  expect_equal(bundle$fp_style, "default")
  expect_equal(bundle$ilab$headers, c("Events", "Non-events", "Events", "Non-events"))
  expect_equal(unname(bundle$ilab$matrix[1, ]), c("4", "119", "11", "128"))
  expect_equal(bundle$ilab$groups, c("Experimental", "Control"))
  expect_equal(nrow(bundle$ilab$matrix), length(fixture$data@study.names))
  expect_true(inherits(bundle$res, "rma"))

  png_path <- tempfile(fileext = ".png")
  pdf_path <- tempfile(fileext = ".pdf")

  rcmetar.draw.forest.plot(bundle, png_path)
  rcmetar.draw.forest.plot(bundle, pdf_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
  png_size <- read_png_dimensions(png_path)
  expect_gte(png_size[["width"]], 900)
  expect_gte(png_size[["height"]], 500)

  expect_true(file.exists(pdf_path))
  expect_gt(file.info(pdf_path)$size, 1000)
  expect_equal(pdftools::pdf_info(pdf_path)$pages, 1)

  saved_path <- tempfile()
  rcmetar.save.plot.data(bundle, saved_path)
  rm(bundle, fixture, res)
  load(paste0(saved_path, ".plotdata"))
  redrawn_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(plot.data, redrawn_path)
  expect_true(file.exists(redrawn_path))
  expect_gt(file.info(redrawn_path)$size, 5000)
})

test_that("single-study binary Default Forest Style uses normalized vectors", {
  fixture <- metafor_binary_fixture(studies = 1)
  res <- get.res.for.one.binary.study(fixture$data, fixture$params)

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bundle$render_engine, "metafor")
  expect_true(bundle$single_study)
  expect_equal(unname(bundle$effect$yi), unname(as.numeric(fixture$data@y)))
  expect_equal(unname(bundle$effect$sei), unname(as.numeric(fixture$data@SE)))
  expect_equal(bundle$ilab$headers, c("Events", "Non-events", "Events", "Non-events"))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 3000)
})

test_that("continuous Default Forest Style builds and renders mean SD N columns", {
  fixture <- metafor_continuous_fixture()
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$data_type, "continuous")
  expect_equal(bundle$ilab$headers, c("Mean", "SD", "N", "Mean", "SD", "N"))
  expect_equal(bundle$ilab$groups, c("Treatment", "Control"))
  expect_equal(nrow(bundle$ilab$matrix), length(fixture$data@study.names))
  expect_true(inherits(bundle$res, "rma"))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
  png_size <- read_png_dimensions(png_path)
  expect_gte(png_size[["width"]], 900)
  expect_gte(png_size[["height"]], 500)
})

test_that("diagnostic Default Forest Style builds and renders count columns on transformed axes", {
  fixture <- metafor_diagnostic_fixture(measure = "Sens")
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$data_type, "diagnostic")
  expect_equal(bundle$ilab$headers, c("TP", "FP", "FN", "TN"))
  expect_equal(bundle$ilab$groups, "Counts")
  expect_identical(rcmetar.metafor.atransf(bundle), invlogit)
  expect_true(inherits(bundle$res, "rma"))

  log_fixture <- metafor_diagnostic_fixture(measure = "PLR")
  log_res <- rma.uni(
    yi = log_fixture$data@y,
    sei = log_fixture$data@SE,
    slab = log_fixture$data@study.names,
    method = log_fixture$params$rm.method,
    level = log_fixture$params$conf.level,
    digits = log_fixture$params$digits
  )
  log_bundle <- rcmetar.regenerate.plot.data(log_fixture$data, log_res, log_fixture$params)
  expect_identical(rcmetar.metafor.atransf(log_bundle), exp)

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
  png_size <- read_png_dimensions(png_path)
  expect_gte(png_size[["width"]], 900)
  expect_gte(png_size[["height"]], 500)
})

test_that("single-study entered diagnostic Default Forest Style omits count ilab and uses normalized vectors", {
  data <- new(
    "DiagnosticData",
    y = logit(0.81),
    SE = 0.18,
    study.names = "Entered",
    years = 0L
  )
  params <- metafor_diagnostic_params(tempfile(fileext = ".png"), "Sens")
  res <- get.res.for.one.diag.study(data, params)

  bundle <- rcmetar.regenerate.plot.data(data, res, params)

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$data_type, "diagnostic")
  expect_true(bundle$single_study)
  expect_equal(ncol(bundle$ilab$matrix), 0)
  expect_equal(unname(bundle$effect$yi), unname(as.numeric(data@y)))
  expect_equal(unname(bundle$effect$sei), unname(as.numeric(data@SE)))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 3000)
})

test_that("cumulative workflow saves and renders a Default metafor bundle", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_outpath <- tempfile(fileext = ".png")

  result <- cum.ma.binary("binary.random", fixture$data, fixture$params)
  bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$forest_variant, "cumulative")
  expect_equal(bundle$fp_style, "default")
  expect_equal(bundle$slab, c("Aaronson", "+ Ferguson", "+ Rosenthal", "+ Hart", "+ Frimodt-Moller", "+ Stein"))
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})

test_that("leave-one-out workflow saves and renders a Default metafor bundle", {
  fixture <- metafor_continuous_fixture()
  fixture$params$fp_outpath <- tempfile(fileext = ".png")

  result <- loo.ma.continuous("continuous.random", fixture$data, fixture$params)
  bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$forest_variant, "leave-one-out")
  expect_equal(bundle$fp_style, "default")
  expect_equal(bundle$slab[[1]], "Overall")
  expect_true(all(grepl("^- ", bundle$slab[-1])))
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})

test_that("subgroup workflow saves and renders Default metafor subtotal diamonds", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_outpath <- tempfile(fileext = ".png")
  fixture$params$cov_name <- "Era"
  fixture$data@covariates <- list(new(
    "CovariateValues",
    cov.name = "Era",
    cov.vals = c("Early", "Early", "Early", "Late", "Late", "Late"),
    cov.type = "factor",
    ref.var = "Early"
  ))

  result <- subgroup.ma.binary("binary.random", fixture$data, fixture$params)
  bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$forest_variant, "subgroup")
  expect_equal(bundle$fp_style, "default")
  expect_equal(bundle$slab[[1]], "Aaronson, 1991")
  expect_equal(bundle$subgroups$names, c("Early", "Late"))
  expect_length(bundle$subgroups$polygon_rows, 2)
  expect_false(is.null(bundle$subgroups$difference_test))
  expect_true(is.finite(bundle$subgroups$difference_test$QM))
  expect_equal(bundle$subgroups$difference_test$df, 1)
  expect_true(inherits(bundle$subgroups$overall, "rma"))
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})
