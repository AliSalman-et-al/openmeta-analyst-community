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
    fp_col1_str = "Study or Subgroup",
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

metafor_entered_binary_fixture <- function(studies = 5) {
  yi <- log(c(0.72, 0.90, 1.12, 0.83, 0.65, 1.05)[seq_len(studies)])
  sei <- c(0.18, 0.22, 0.16, 0.20, 0.25, 0.19)[seq_len(studies)]
  data <- rcmetar.create.binary.data(
    y = yi,
    SE = sei,
    study.names = paste("Entered Binary", seq_len(studies))
  )
  list(data = data, params = metafor_binary_params(file.path("r_tmp", paste0("forest_entered_binary_", studies, ".png"))))
}

metafor_mixed_binary_fixture <- function(studies = 5) {
  fixture <- metafor_entered_binary_fixture(studies)
  fixture$data@g1O1 <- c(12, NA, 20, NA, 18, 22)[seq_len(studies)]
  fixture$data@g1O2 <- c(90, NA, 110, NA, 100, 130)[seq_len(studies)]
  fixture$data@g2O1 <- c(18, NA, 22, NA, 25, 27)[seq_len(studies)]
  fixture$data@g2O2 <- c(88, NA, 108, NA, 96, 125)[seq_len(studies)]
  fixture$data@study.names <- paste("Mixed Binary", seq_len(studies))
  fixture
}

metafor_entered_continuous_fixture <- function(studies = 5) {
  data <- rcmetar.create.continuous.data(
    y = c(-0.5, 0.1, 0.3, -0.2, 0.0, 0.25)[seq_len(studies)],
    SE = c(0.20, 0.25, 0.22, 0.18, 0.21, 0.24)[seq_len(studies)],
    study.names = paste("Entered Continuous", seq_len(studies))
  )
  list(data = data, params = metafor_continuous_params(file.path("r_tmp", paste0("forest_entered_cont_", studies, ".png"))))
}

metafor_entered_diagnostic_fixture <- function(studies = 5, measure = "Sens") {
  data <- rcmetar.create.diagnostic.data(
    y = logit(c(0.70, 0.75, 0.80, 0.77, 0.73, 0.79)[seq_len(studies)]),
    SE = c(0.22, 0.18, 0.17, 0.20, 0.19, 0.21)[seq_len(studies)],
    study.names = paste("Entered Diagnostic", seq_len(studies))
  )
  list(data = data, params = metafor_diagnostic_params(file.path("r_tmp", paste0("forest_entered_diag_", studies, ".png")), measure))
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
  svg_path <- tempfile(fileext = ".svg")
  svgz_path <- tempfile(fileext = ".svgz")
  tiff_path <- tempfile(fileext = ".tiff")
  contains_png_pdf_path <- tempfile(pattern = "contains_png_", fileext = ".pdf")

  rcmetar.draw.forest.plot(bundle, png_path)
  rcmetar.draw.forest.plot(bundle, pdf_path)
  rcmetar.draw.forest.plot(bundle, svg_path)
  rcmetar.draw.forest.plot(bundle, svgz_path)
  rcmetar.draw.forest.plot(bundle, tiff_path)
  rcmetar.draw.forest.plot(bundle, contains_png_pdf_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
  png_size <- read_png_dimensions(png_path)
  expect_gte(png_size[["width"]], 900)
  expect_gte(png_size[["height"]], 500)

  expect_true(file.exists(pdf_path))
  expect_gt(file.info(pdf_path)$size, 1000)
  expect_equal(pdftools::pdf_info(pdf_path)$pages, 1)

  expect_true(file.exists(svg_path))
  expect_gt(file.info(svg_path)$size, 1000)
  expect_match(readLines(svg_path, n = 1), "xml|svg")

  expect_true(file.exists(svgz_path))
  expect_gt(file.info(svgz_path)$size, 1000)
  expect_match(readLines(gzfile(svgz_path), n = 1), "xml|svg")

  expect_true(file.exists(tiff_path))
  expect_gt(file.info(tiff_path)$size, 1000)
  expect_equal(rcmetar.plot.file.extension(tiff_path), "tiff")
  expect_length(dim(tiff::readTIFF(tiff_path)), 3)

  expect_equal(rcmetar.plot.file.extension(contains_png_pdf_path), "pdf")
  expect_equal(rcmetar.plot.file.extension("journal-forest.svg.gz"), "svgz")
  expect_true(file.exists(contains_png_pdf_path))
  expect_gt(file.info(contains_png_pdf_path)$size, 1000)
  expect_equal(pdftools::pdf_info(contains_png_pdf_path)$pages, 1)

  saved_path <- tempfile()
  rcmetar.save.plot.data(bundle, saved_path)
  rm(bundle, fixture, res)
  load(paste0(saved_path, ".plotdata"))
  redrawn_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(plot.data, redrawn_path)
  expect_true(file.exists(redrawn_path))
  expect_gt(file.info(redrawn_path)$size, 5000)
})

test_that("forest style and universal appearance params persist in metafor bundles", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "bmj"
  fixture$params$fp_accent_color <- "#6b58a6"
  fixture$params$fp_point_size_multiplier <- 1.8
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
  expect_equal(bundle$fp_style, "bmj")
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#6b58a6")
  expect_equal(rcmetar.point.size.multiplier(bundle$params), 1.8)

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("binary RevMan Forest Style builds faithful count, weight, and block spec", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "revman"
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

  expect_equal(bundle$fp_style, "revman")
  expect_equal(bundle$ilab$headers, c("Events", "Total", "Events", "Total", "Weight"))
  expect_equal(bundle$ilab$groups, c("Experimental", "Control"))
  expect_equal(unname(bundle$ilab$matrix[1, ]), c("4", "123", "11", "139", paste0(round.display(weights(res)[[1]], 1), "%")))
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²")
  expect_match(bundle$style_blocks$heterogeneity, "Chi²")
  expect_match(bundle$style_blocks$heterogeneity, "I²")
  expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z =")
  expect_equal(bundle$style_blocks$favours_left, "Favours Experimental")
  expect_equal(bundle$style_blocks$favours_right, "Favours Control")
  expect_equal(rcmetar.revman.study.header(bundle), "Study or Subgroup")
  expect_false(any(grepl("bias|rob", c(names(bundle$style_blocks), unlist(bundle$style_blocks)), ignore.case = TRUE)))
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#000000")

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("Forest Layout Preflight produces deterministic layout plans for Default and RevMan styles", {
  fixture <- metafor_binary_fixture()
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  default.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  default.plan <- rcmetar.forest.layout.preflight(default.bundle)

  expect_s3_class(default.plan, "rcmetar_forest_layout_plan")
  expect_equal(default.plan$style$name, "default")
  expect_equal(default.plan$style$template, "default")
  expect_gt(default.plan$device$width, 0)
  expect_gt(default.plan$device$height, 0)
  expect_gte(default.plan$typography$cex, 0.78)
  expect_equal(default.plan$rows$study_rows, nrow(default.bundle$ilab$matrix):1)
  expect_equal(default.plan$x$alim, rcmetar.metafor.alim(default.bundle))
  expect_equal(default.plan$columns$ilab.xpos, rcmetar.metafor.layout(default.bundle, default.plan$device, default.plan$x$alim)$ilab.xpos)

  fixture$params$fp_style <- "revman"
  revman.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  revman.plan <- rcmetar.forest.layout.preflight(revman.bundle)

  expect_s3_class(revman.plan, "rcmetar_forest_layout_plan")
  expect_equal(revman.plan$style$name, "revman")
  expect_equal(revman.plan$style$template, "standard")
  expect_equal(revman.plan$headers$study, "Study or Subgroup")
  expect_equal(revman.plan$rows$study_rows, length(revman.bundle$slab):1)
  expect_equal(revman.plan$x$at, rcmetar.revman.axis.ticks(revman.bundle, revman.plan$x$alim))
  expect_equal(revman.plan$footer$axis$axis.x, mean(revman.plan$x$alim), tolerance = 1e-8)
})

test_that("Forest Layout Preflight records sparse and compact RevMan templates without persisting plans", {
  fixture <- metafor_entered_binary_fixture()
  fixture$params$fp_style <- "revman"
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  sparse.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  sparse.plan <- rcmetar.forest.layout.preflight(sparse.bundle)

  expect_equal(sparse.plan$style$name, "revman")
  expect_equal(sparse.plan$style$template, "sparse")
  expect_equal(sparse.bundle$ilab$headers, "Weight")
  expect_equal(length(sparse.plan$columns$ilab.xpos), 1)
  expect_false("layout_plan" %in% names(sparse.bundle))

  sequential.bundle <- rcmetar.build.sequential.metafor.bundle(
    fixture$data,
    fixture$params,
    list(
      list(b = fixture$data@y[[1]], ci.lb = fixture$data@y[[1]] - fixture$data@SE[[1]], ci.ub = fixture$data@y[[1]] + fixture$data@SE[[1]], se = fixture$data@SE[[1]]),
      list(b = fixture$data@y[[2]], ci.lb = fixture$data@y[[2]] - fixture$data@SE[[2]], ci.ub = fixture$data@y[[2]] + fixture$data@SE[[2]], se = fixture$data@SE[[2]])
    ),
    "cumulative",
    labels = c("Entered Binary 1", "+ Entered Binary 2"),
    legacy.plot.data = list(plot.range = NULL, changed.params = fixture$params)
  )
  compact.plan <- rcmetar.forest.layout.preflight(sequential.bundle, style = "revman")

  expect_equal(compact.plan$style$name, "revman")
  expect_equal(compact.plan$style$template, "compact")
  expect_true(compact.plan$rows$manual_sequential_labels)
  expect_equal(compact.plan$rows$study_rows, 2:1)
})

test_that("RevMan study heading uses reference default and respects custom labels", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "revman"
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  expect_equal(rcmetar.revman.study.header(bundle), "Study or Subgroup")

  fixture$params$fp_col1_str <- "Trial"
  custom.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  expect_equal(rcmetar.revman.study.header(custom.bundle), "Trial")

  fixture$params$fp_show_col1 <- FALSE
  hidden.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  expect_equal(rcmetar.revman.study.header(hidden.bundle), "")
})

test_that("RevMan X-axis footer labels align to the plotted effect axis", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "revman"
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )
  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  layout <- rcmetar.revman.layout(bundle)
  footer <- rcmetar.revman.axis.footer.layout(bundle, layout)

  expect_equal(footer$left.x, mean(c(layout$alim[[1]], 0)), tolerance = 1e-8)
  expect_equal(footer$right.x, mean(c(0, layout$alim[[2]])), tolerance = 1e-8)
  expect_equal(footer$axis.x, mean(layout$alim), tolerance = 1e-8)
  expect_gt(footer$left.max.width, 0)
  expect_gt(footer$right.max.width, 0)
  expect_equal(bundle$style_blocks$favours_left, "Favours Experimental")
  expect_equal(bundle$style_blocks$favours_right, "Favours Control")

  diagnostic.fixture <- metafor_diagnostic_fixture(measure = "Sens")
  diagnostic.fixture$params$fp_style <- "revman"
  diagnostic.res <- rma.uni(
    yi = diagnostic.fixture$data@y,
    sei = diagnostic.fixture$data@SE,
    slab = diagnostic.fixture$data@study.names,
    method = diagnostic.fixture$params$rm.method,
    level = diagnostic.fixture$params$conf.level,
    digits = diagnostic.fixture$params$digits
  )
  diagnostic.bundle <- rcmetar.regenerate.plot.data(diagnostic.fixture$data, diagnostic.res, diagnostic.fixture$params)
  diagnostic.layout <- rcmetar.revman.layout(diagnostic.bundle)
  diagnostic.footer <- rcmetar.revman.axis.footer.layout(diagnostic.bundle, diagnostic.layout)

  expect_equal(diagnostic.footer$axis.x, mean(diagnostic.layout$alim), tolerance = 1e-8)
  expect_equal(diagnostic.bundle$style_blocks$axis_label, "Sensitivity")
  expect_equal(diagnostic.bundle$style_blocks$favours_left, "")
  expect_equal(diagnostic.bundle$style_blocks$favours_right, "")
})

test_that("continuous RevMan Forest Style builds mean SD total columns", {
  fixture <- metafor_continuous_fixture()
  fixture$params$fp_style <- "revman"
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bundle$fp_style, "revman")
  expect_equal(bundle$ilab$headers, c("Mean", "SD", "Total", "Mean", "SD", "Total", "Weight"))
  expect_equal(bundle$ilab$groups, c("Treatment", "Control"))
  expect_equal(bundle$style_blocks$favours_left, "Favours Treatment")
  expect_equal(bundle$style_blocks$favours_right, "Favours Control")
  expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z =")

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("diagnostic RevMan Forest Style uses DTA columns and a plain metric axis", {
  fixture <- metafor_diagnostic_fixture(measure = "Sens")
  fixture$params$fp_style <- "revman"
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bundle$fp_style, "revman")
  expect_equal(bundle$ilab$headers, c("TP", "FP", "FN", "TN", "Weight"))
  expect_equal(bundle$ilab$groups, "DTA")
  expect_equal(bundle$style_blocks$favours_left, "")
  expect_equal(bundle$style_blocks$favours_right, "")
  expect_equal(bundle$style_blocks$axis_label, "Sensitivity")
  expect_equal(rcmetar.metafor.xlab(bundle), "Sensitivity")
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²")

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("BMJ Forest Style builds faithful family columns and renders smoke cases", {
  fixtures <- list(
    binary = list(
      fixture = metafor_binary_fixture(),
      expected_headers = c("", "", "Weight"),
      expected_groups = c("Experimental", "Control"),
      axis_label = "",
      favours_left = "Favors control",
      favours_right = "Favors experimental"
    ),
    continuous = list(
      fixture = metafor_continuous_fixture(),
      expected_headers = c("Mean", "SD", "Total", "Mean", "SD", "Total", "Weight"),
      expected_groups = c("Treatment", "Control"),
      axis_label = "",
      favours_left = "Favors control",
      favours_right = "Favors treatment"
    ),
    diagnostic = list(
      fixture = metafor_diagnostic_fixture(measure = "Sens"),
      expected_headers = c("TP", "FP", "FN", "TN", "Weight"),
      expected_groups = "DTA",
      axis_label = "Sensitivity",
      favours_left = "",
      favours_right = ""
    )
  )

  for (case in fixtures) {
    fixture <- case$fixture
    fixture$params$fp_style <- "bmj"
    res <- rma.uni(
      yi = fixture$data@y,
      sei = fixture$data@SE,
      slab = fixture$data@study.names,
      method = fixture$params$rm.method,
      level = fixture$params$conf.level,
      digits = fixture$params$digits
    )

    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

    expect_equal(bundle$fp_style, "bmj")
    expect_equal(bundle$ilab$headers, case$expected_headers)
    expect_equal(bundle$ilab$groups, case$expected_groups)
    expect_equal(bundle$style_blocks$favours_left, case$favours_left)
    expect_equal(bundle$style_blocks$favours_right, case$favours_right)
    expect_equal(bundle$style_blocks$axis_label, case$axis_label)
    expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau")
    expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z =")
    expect_equal(rcmetar.forest.accent.color(bundle$params), "#6b58a6")

    png_path <- tempfile(fileext = ".png")
    rcmetar.draw.forest.plot(bundle, png_path)
    expect_true(file.exists(png_path))
    expect_gt(file.info(png_path)$size, 5000)
  }
})

test_that("older forest plot params default to Default style and visible controls", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- NULL
  fixture$params$fp_accent_color <- NULL
  fixture$params$fp_point_size_multiplier <- NULL
  fixture$params$fp_show_raw_counts <- NULL
  fixture$params$fp_show_headers <- NULL
  fixture$params$fp_show_annotation <- NULL
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

  expect_equal(bundle$fp_style, "default")
  expect_equal(bundle$ilab$headers, c("Events", "Non-events", "Events", "Non-events"))
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#2f5597")
  expect_equal(rcmetar.metafor.study.header(bundle), "Study or Subgroup")
  expect_true(rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE))
  expect_true(rcmetar.param.is.true(bundle$params, "fp_show_annotation", TRUE))

  bundle$params$fp_col1_str <- "Studies"
  expect_equal(rcmetar.metafor.study.header(bundle), "Study or Subgroup")
  bundle$params$fp_col1_str <- "Author(s) and Year"
  expect_equal(rcmetar.metafor.study.header(bundle), "Study or Subgroup")
  bundle$params$fp_col1_str <- "Trial"
  expect_equal(rcmetar.metafor.study.header(bundle), "Trial")
})

test_that("Default Forest Style panel toggles raw counts headers and annotation", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_show_raw_counts <- FALSE
  fixture$params$fp_show_headers <- FALSE
  fixture$params$fp_show_annotation <- FALSE
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

  expect_equal(ncol(bundle$ilab$matrix), 0)
  expect_equal(rcmetar.metafor.effect.header(bundle), "")
  size <- rcmetar.measure.metafor.forest.device(bundle)
  expect_gt(size$left_width, size$study_width + size$block_gap)

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("entered-effect-only standard plots render without raw arm columns", {
  fixtures <- list(
    binary = metafor_entered_binary_fixture(),
    continuous = metafor_entered_continuous_fixture(),
    diagnostic = metafor_entered_diagnostic_fixture()
  )

  for (fixture in fixtures) {
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
    expect_equal(ncol(bundle$ilab$matrix), 0)
    expect_equal(bundle$slab, fixture$data@study.names)

    png_path <- tempfile(fileext = ".png")
    rcmetar.draw.forest.plot(bundle, png_path)
    expect_true(file.exists(png_path))
    expect_gt(file.info(png_path)$size, 5000)
  }
})

test_that("entered-effect-only RevMan plots degrade to weight columns", {
  fixtures <- list(
    binary = metafor_entered_binary_fixture(),
    continuous = metafor_entered_continuous_fixture(),
    diagnostic = metafor_entered_diagnostic_fixture()
  )

  for (fixture in fixtures) {
    fixture$params$fp_style <- "revman"
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
    expect_equal(bundle$fp_style, "revman")
    expect_equal(bundle$ilab$headers, "Weight")
    expect_equal(bundle$ilab$groups, character(0))
    expect_equal(bundle$style_blocks$totals$weight, "100.0%")
    layout <- rcmetar.revman.layout(bundle)
    expect_gt(as.numeric(layout$ilab.xpos[[1]]), layout$xlim[[1]] + 0.45 * (layout$annotation.xpos - layout$xlim[[1]]))

    png_path <- tempfile(fileext = ".png")
    rcmetar.draw.forest.plot(bundle, png_path)
    expect_true(file.exists(png_path))
    expect_gt(file.info(png_path)$size, 5000)
  }
})

test_that("mixed raw and entered-effect rows render blanks for unavailable raw data", {
  fixture <- metafor_mixed_binary_fixture()
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
  expect_equal(bundle$ilab$headers, c("Events", "Non-events", "Events", "Non-events"))
  expect_equal(unname(bundle$ilab$matrix[2, ]), rep("", 4))

  fixture$params$fp_style <- "revman"
  revman.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(revman.bundle$ilab$headers, c("Events", "Total", "Events", "Total", "Weight"))
  expect_equal(unname(revman.bundle$ilab$matrix[2, 1:4]), rep("", 4))
  expect_null(revman.bundle$style_blocks$totals$experimental_total)
  expect_null(revman.bundle$style_blocks$totals$control_total)
  expect_equal(revman.bundle$style_blocks$totals$weight, "100.0%")

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(revman.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("Default Forest Style sizing reserves space for long group headers", {
  fixture <- metafor_binary_fixture()
  fixture$data@study.names <- paste(fixture$data@study.names, "Collaborative Trial With Long Label")
  fixture$params$fp_col1_str <- "Long Study Label"
  fixture$params$fp_col3_str <- "Intervention With Long Header"
  fixture$params$fp_col4_str <- "Comparator With Long Header"
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
  size <- rcmetar.measure.metafor.forest.device(bundle)
  experimental.columns <- vapply(bundle$ilab$columns, function(column) column$group, character(1)) ==
    "Intervention With Long Header"
  experimental.width <- sum(size$column_widths[experimental.columns]) +
    size$column_gap * (sum(experimental.columns) - 1)

  expect_gte(experimental.width, unname(size$group_widths[["Intervention With Long Header"]]))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("RevMan raw-column layouts reserve space for long study labels", {
  short.fixture <- metafor_continuous_fixture()
  short.fixture$params$fp_style <- "revman"
  short.res <- rma.uni(
    yi = short.fixture$data@y,
    sei = short.fixture$data@SE,
    slab = short.fixture$data@study.names,
    method = short.fixture$params$rm.method,
    level = short.fixture$params$conf.level,
    digits = short.fixture$params$digits
  )
  short.bundle <- rcmetar.regenerate.plot.data(short.fixture$data, short.res, short.fixture$params)
  short.layout <- rcmetar.revman.layout(short.bundle)

  long.fixture <- metafor_continuous_fixture()
  long.fixture$data@study.names <- paste(
    "International multicenter trial with protocol-defined responder analysis",
    seq_along(long.fixture$data@study.names)
  )
  long.fixture$params$fp_style <- "revman"
  long.res <- rma.uni(
    yi = long.fixture$data@y,
    sei = long.fixture$data@SE,
    slab = long.fixture$data@study.names,
    method = long.fixture$params$rm.method,
    level = long.fixture$params$conf.level,
    digits = long.fixture$params$digits
  )
  long.bundle <- rcmetar.regenerate.plot.data(long.fixture$data, long.res, long.fixture$params)
  long.layout <- rcmetar.revman.layout(long.bundle)

  short.gap <- as.numeric(short.layout$ilab.xpos[[1]]) - short.layout$xlim[[1]]
  long.gap <- as.numeric(long.layout$ilab.xpos[[1]]) - long.layout$xlim[[1]]
  span <- max(diff(long.layout$alim), 1)

  expect_gt(long.gap, short.gap + 1.5 * span)

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(long.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
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

test_that("cumulative workflow saves and renders a RevMan metafor bundle", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "revman"
  fixture$params$fp_outpath <- tempfile(fileext = ".png")

  result <- cum.ma.binary("binary.random", fixture$data, fixture$params)
  bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$forest_variant, "cumulative")
  expect_equal(bundle$fp_style, "revman")
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#000000")
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})

test_that("cumulative workflow handles entered-effect-only data in Default and RevMan styles", {
  fixtures <- list(
    binary = list(fixture_fn = metafor_entered_binary_fixture, method = "binary.random", runner = cum.ma.binary),
    continuous = list(fixture_fn = metafor_entered_continuous_fixture, method = "continuous.random", runner = cum.ma.continuous),
    diagnostic = list(fixture_fn = metafor_entered_diagnostic_fixture, method = "diagnostic.random", runner = cum.ma.diagnostic)
  )

  for (entry in fixtures) {
    for (style in c("default", "revman")) {
      fixture <- entry$fixture_fn()
      fixture$params$fp_style <- style
      fixture$params$fp_outpath <- tempfile(fileext = ".png")

      result <- entry$runner(entry$method, fixture$data, fixture$params)
      bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

      expect_equal(bundle$render_engine, "metafor")
      expect_equal(bundle$forest_variant, "cumulative")
      expect_equal(bundle$fp_style, style)
      expect_true(file.exists(unname(result$images[[1]])))
      expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
    }
  }
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

test_that("leave-one-out workflow handles entered-effect-only data in Default and RevMan styles", {
  fixtures <- list(
    binary = list(fixture_fn = metafor_entered_binary_fixture, method = "binary.random", runner = loo.ma.binary),
    continuous = list(fixture_fn = metafor_entered_continuous_fixture, method = "continuous.random", runner = loo.ma.continuous),
    diagnostic = list(fixture_fn = metafor_entered_diagnostic_fixture, method = "diagnostic.random", runner = loo.ma.diagnostic)
  )

  for (entry in fixtures) {
    for (style in c("default", "revman")) {
      fixture <- entry$fixture_fn()
      fixture$params$fp_style <- style
      fixture$params$fp_outpath <- tempfile(fileext = ".png")

      result <- entry$runner(entry$method, fixture$data, fixture$params)
      bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

      expect_equal(bundle$render_engine, "metafor")
      expect_equal(bundle$forest_variant, "leave-one-out")
      expect_equal(bundle$fp_style, style)
      expect_equal(bundle$slab[[1]], "Overall")
      expect_true(file.exists(unname(result$images[[1]])))
      expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
    }
  }
})

test_that("leave-one-out workflow saves and renders a RevMan metafor bundle", {
  fixture <- metafor_continuous_fixture()
  fixture$params$fp_style <- "revman"
  fixture$params$fp_outpath <- tempfile(fileext = ".png")

  result <- loo.ma.continuous("continuous.random", fixture$data, fixture$params)
  bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

  expect_equal(bundle$render_engine, "metafor")
  expect_equal(bundle$forest_variant, "leave-one-out")
  expect_equal(bundle$fp_style, "revman")
  expect_equal(bundle$slab[[1]], "Overall")
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

test_that("subgroup workflow saves and renders RevMan subtotal diamonds", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "revman"
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
  expect_equal(bundle$fp_style, "revman")
  expect_equal(bundle$ilab$headers, c("Events", "Total", "Events", "Total", "Weight"))
  expect_length(bundle$subgroups$polygon_rows, 2)
  expect_true(inherits(bundle$subgroups$overall, "rma"))
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²")
  expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z =")
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})

test_that("subgroup workflow saves and renders BMJ subtotal diamonds", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_style <- "bmj"
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
  expect_equal(bundle$fp_style, "bmj")
  expect_equal(bundle$ilab$headers, c("", "", "Weight"))
  expect_length(bundle$subgroups$polygon_rows, 2)
  expect_true(inherits(bundle$subgroups$overall, "rma"))
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau")
  expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z =")
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#6b58a6")
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})
