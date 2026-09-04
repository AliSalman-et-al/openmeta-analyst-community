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
    fp_col3_str = "[default]",
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

metafor_binary_one_arm_fixture <- function(studies = 5, measure = "PLO") {
  data <- new(
    "BinaryData",
    g1O1 = c(4, 8, 10, 15, 18, 22)[seq_len(studies)],
    g1O2 = c(96, 92, 90, 85, 82, 78)[seq_len(studies)],
    study.names = c("Ames", "Benton", "Cruz", "Dover", "Elia", "Frost")[seq_len(studies)],
    years = as.integer(2001:(2000 + studies))
  )
  params <- metafor_binary_params(file.path("r_tmp", paste0("forest_one_arm_binary_", measure, "_", studies, ".png")))
  params$measure <- measure
  params$fp_col3_str <- "Cohort"
  params$create.plot <- TRUE
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

metafor_continuous_one_arm_fixture <- function(studies = 5) {
  data <- new(
    "ContinuousData",
    N1 = c(22, 35, 18, 41, 29, 33)[seq_len(studies)],
    mean1 = c(8.2, 7.6, 9.1, 6.8, 7.4, 8.7)[seq_len(studies)],
    sd1 = c(1.5, 1.8, 1.2, 2.1, 1.7, 1.4)[seq_len(studies)],
    study.names = c("Allen", "Baker", "Cole", "Diaz", "Evans", "Fong")[seq_len(studies)],
    years = as.integer(2001:(2000 + studies))
  )
  params <- metafor_continuous_params(file.path("r_tmp", paste0("forest_one_arm_cont_", studies, ".png")))
  params$measure <- "TXMean"
  params$fp_col3_str <- "Cohort"
  params$fp_col4_str <- "[default]"
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

read_pdf_contract <- function(path) {
  raw <- readBin(path, what = "raw", n = 100000000L)
  bytes <- as.integer(raw)
  ascii <- bytes[(bytes %in% c(9L, 10L, 13L)) | (bytes >= 32L & bytes <= 126L)]
  text <- rawToChar(as.raw(ascii))
  page.tokens <- gregexpr("/Type[[:space:]]*/Page([^s]|$)", text, perl = TRUE)[[1L]]
  list(
    signature = rawToChar(raw[seq_len(min(length(raw), 5L))]),
    pages = if (identical(page.tokens, -1L)) 0L else length(page.tokens),
    has_xref = grepl("startxref", text, fixed = TRUE),
    has_eof = grepl("%%EOF", text, fixed = TRUE)
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
  expect_true("effect_display" %in% names(bundle))
  expect_false("legacy_plot_data" %in% names(bundle))
  expect_equal(bundle$ilab$headers, c("Events", "Non-events", "Events", "Non-events"))
  expect_equal(unname(bundle$ilab$matrix[1, ]), c("4", "119", "11", "128"))
  expect_equal(bundle$ilab$groups, c("Intervention", "Control"))
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
  expect_false(file.exists(rcmetar.plot.canonical_svg_path(png_path)))
  png_size <- read_png_dimensions(png_path)
  expect_gte(png_size[["width"]], 900)
  expect_gte(png_size[["height"]], 500)

  expect_true(file.exists(pdf_path))
  expect_gt(file.info(pdf_path)$size, 1000)
  expect_false(file.exists(rcmetar.plot.canonical_svg_path(pdf_path)))
  pdf.contract <- read_pdf_contract(pdf_path)
  expect_equal(pdf.contract$signature, "%PDF-")
  expect_equal(pdf.contract$pages, 1)
  expect_true(pdf.contract$has_xref)
  expect_true(pdf.contract$has_eof)

  expect_true(file.exists(svg_path))
  expect_gt(file.info(svg_path)$size, 1000)
  expect_match(readLines(svg_path, n = 1), "xml|svg")

  expect_true(file.exists(svgz_path))
  expect_gt(file.info(svgz_path)$size, 1000)
  expect_match(readLines(gzfile(svgz_path), n = 1), "xml|svg")

  expect_true(file.exists(tiff_path))
  expect_gt(file.info(tiff_path)$size, 1000)
  expect_equal(rcmetar.plot.file.extension(tiff_path), "tiff")
  expect_false(file.exists(rcmetar.plot.canonical_svg_path(tiff_path)))
  expect_length(dim(tiff::readTIFF(tiff_path)), 3)

  expect_equal(rcmetar.plot.file.extension(contains_png_pdf_path), "pdf")
  expect_equal(rcmetar.plot.file.extension("journal-forest.svg.gz"), "svgz")
  expect_true(file.exists(contains_png_pdf_path))
  expect_gt(file.info(contains_png_pdf_path)$size, 1000)
  contains.pdf.contract <- read_pdf_contract(contains_png_pdf_path)
  expect_equal(contains.pdf.contract$signature, "%PDF-")
  expect_equal(contains.pdf.contract$pages, 1)
  expect_true(contains.pdf.contract$has_xref)
  expect_true(contains.pdf.contract$has_eof)

  saved_path <- tempfile()
  rcmetar.save.plot.data(bundle, saved_path)
  rm(bundle, fixture, res)
  load(paste0(saved_path, ".plotdata"))
  redrawn_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(plot.data, redrawn_path)
  expect_true(file.exists(redrawn_path))
  expect_gt(file.info(redrawn_path)$size, 5000)
})

test_that("effect estimates and confidence limits never use probability thresholds", {
  values <- c(0, 0.07, 0.006, 0.00004, 0.0000004, -0.006, NA_real_)
  labels <- rcmetar.format.effect.number(values, 2)

  expect_equal(
    labels,
    c("0.00", "0.07", "0.0060", "0.000040", "4.00e-07", "-0.0060", "")
  )
  expect_false(any(grepl("<", labels, fixed=TRUE)))
  expect_equal(rcmetar.revman.format.effect.number(values, 2), labels)
  expect_equal(rcmetar.bmj.format.effect.number(values, 2), labels)
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
  expect_equal(bundle$ilab$groups, c("Intervention", "Control"))
  expect_equal(unname(bundle$ilab$matrix[1, ]), c("4", "123", "11", "139", paste0(round.display(weights(res)[[1]], 1), "%")))
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²")
  expect_match(bundle$style_blocks$heterogeneity, "Chi²")
  expect_match(bundle$style_blocks$heterogeneity, "I²")
  expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z =")
  expect_equal(bundle$style_blocks$favours_left, "Favours Intervention")
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
  expect_equal(default.plan$x$alim, rcmetar.forest.journal.ratio.alim(default.bundle))
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

  fixture$params$fp_style <- "bmj"
  bmj.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  bmj.plan <- rcmetar.forest.layout.preflight(bmj.bundle)

  expect_s3_class(bmj.plan, "rcmetar_forest_layout_plan")
  expect_equal(bmj.plan$style$name, "bmj")
  expect_equal(bmj.plan$style$template, "standard")
  expect_equal(bmj.plan$headers$study, "Study or Subgroup")
  expect_equal(bmj.plan$headers$effect, "Odds ratio")
  expect_equal(bmj.plan$rows$study_rows, length(bmj.bundle$slab):1)
  expect_equal(bmj.plan$footer$axis$axis.x, mean(bmj.plan$x$alim), tolerance = 1e-8)
})

test_that("RevMan SVG uses inline study CI strokes for QtSvg compatibility", {
  fixture <- metafor_continuous_fixture(5)
  fixture$params$fp_style <- "revman"
  fixture$params$fp_show_raw_counts <- FALSE
  fixture$params$fp_color <- "#000000"
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )
  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  svg.path <- tempfile(fileext = ".svg")

  rcmetar.draw.forest.plot(bundle, svg.path)

  svg <- readLines(svg.path, warn = FALSE)
  line.tags <- unlist(regmatches(svg, gregexpr("<(line|polyline)\\b[^>]*>", svg, perl = TRUE)))
  study.intervals <- line.tags[grepl("stroke-width: 0[.]86", line.tags, fixed = FALSE)]
  expect_gte(length(study.intervals), length(fixture$data@y))
  expect_true(all(grepl("stroke=\"#000000\"", study.intervals, fixed = TRUE)))
})

test_that("journal ratio axes adapt to observed effects across Forest Plot Styles", {
  fixture <- metafor_binary_fixture()
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  z <- stats::qnorm(0.975)
  for (style in c("default", "revman", "bmj")) {
    fixture$params$fp_style <- style
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
    plan <- rcmetar.forest.layout.preflight(bundle)
    interval.fractions <- (2 * z * fixture$data@SE) / diff(plan$x$alim)

    expect_lte(plan$x$alim[[1]], 0)
    expect_gte(plan$x$alim[[2]], 0)
    expect_gte(stats::median(interval.fractions, na.rm = TRUE), 0.08)
    expect_lt(diff(plan$x$alim), diff(log(c(0.01, 100))))
    expect_gte(length(plan$x$at), 3)
    expect_lte(length(plan$x$at), 5)
    expect_true(all(plan$x$at >= plan$x$alim[[1]] & plan$x$at <= plan$x$alim[[2]]))
  }
})

test_that("explicit Forest Plot axis ticks override adaptive defaults for every style", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_xticks <- c(0.1, 0.5, 1, 2)
  fixture$params$fp_plot_lb <- "0.25"
  fixture$params$fp_plot_ub <- "4"
  res <- rma.uni(yi=fixture$data@y, sei=fixture$data@SE, method="DL")

  for (style in c("default", "revman", "bmj")) {
    fixture$params$fp_style <- style
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
    plan <- rcmetar.forest.layout.preflight(bundle)
    expect_equal(plan$x$at, log(c(0.1, 0.5, 1, 2)))
    expect_equal(plan$x$alim, rcmetar.metafor.alim(bundle))
  }
})

test_that("one-sided axis bounds and BMJ risk-difference bounds remain authoritative", {
  fixture <- metafor_binary_fixture()
  res <- rma.uni(yi=fixture$data@y, sei=fixture$data@SE, method="DL")

  fixture$params$fp_plot_lb <- "0.25"
  fixture$params$fp_plot_ub <- "[default]"
  for (style in c("default", "revman", "bmj")) {
    fixture$params$fp_style <- style
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
    plan <- rcmetar.forest.layout.preflight(bundle)
    expect_equal(plan$x$alim[[1]], rcmetar.metafor.alim(bundle)[[1]])
  }

  fixture$params$measure <- "RD"
  fixture$params$fp_style <- "bmj"
  fixture$params$fp_plot_lb <- "-0.5"
  fixture$params$fp_plot_ub <- "0.75"
  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  expect_equal(rcmetar.forest.bmj.alim(bundle), rcmetar.metafor.alim(bundle))
})

test_that("narrow explicit axis bounds remain exact for every style", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_plot_lb <- "10"
  fixture$params$fp_plot_ub <- "11"
  res <- rma.uni(yi=fixture$data@y, sei=fixture$data@SE, method="DL")

  for (style in c("default", "revman", "bmj")) {
    fixture$params$fp_style <- style
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
    plan <- rcmetar.forest.layout.preflight(bundle)
    expect_equal(plan$x$alim, rcmetar.metafor.alim(bundle))
  }
})

test_that("one extreme study interval does not squeeze the remaining forest", {
  fixture <- metafor_entered_binary_fixture(6)
  fixture$data@SE[[1]] <- 1.8
  res <- rma.uni(
    yi=fixture$data@y,
    sei=fixture$data@SE,
    method="DL",
    level=fixture$params$conf.level
  )
  z <- stats::qnorm(0.975)
  full.lower <- res$yi - z * sqrt(res$vi)
  full.upper <- res$yi + z * sqrt(res$vi)

  for (style in c("default", "revman", "bmj")) {
    fixture$params$fp_style <- style
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
    plan <- rcmetar.forest.layout.preflight(bundle)

    expect_gt(plan$x$alim[[1]], min(full.lower))
    expect_lt(plan$x$alim[[2]], max(full.upper))
    expect_true(all(res$yi >= plan$x$alim[[1]] & res$yi <= plan$x$alim[[2]]))
    expect_true(res$ci.lb >= plan$x$alim[[1]] && res$ci.ub <= plan$x$alim[[2]])
  }
})

test_that("one extreme interval is clipped for sparse analyses", {
  fixture <- metafor_entered_binary_fixture(3)
  fixture$data@SE[[1]] <- 2.4
  res <- rma.uni(yi=fixture$data@y, sei=fixture$data@SE, method="DL")
  z <- stats::qnorm(0.975)
  full.lower <- res$yi - z * sqrt(res$vi)
  full.upper <- res$yi + z * sqrt(res$vi)

  for (style in c("default", "revman", "bmj")) {
    fixture$params$fp_style <- style
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
    plan <- rcmetar.forest.layout.preflight(bundle)
    expect_gt(plan$x$alim[[1]], min(full.lower))
    expect_lt(plan$x$alim[[2]], max(full.upper))
    expect_true(all(res$yi >= plan$x$alim[[1]] & res$yi <= plan$x$alim[[2]]))
  }
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
    labels = c("Entered Binary 1", "+ Entered Binary 2")
  )
  compact.plan <- rcmetar.forest.layout.preflight(sequential.bundle, style = "revman")

  expect_equal(compact.plan$style$name, "revman")
  expect_equal(compact.plan$style$template, "compact")
  expect_true(compact.plan$rows$manual_sequential_labels)
  expect_equal(compact.plan$rows$study_rows, 2:1)
  expect_lt(compact.plan$rows$top - max(compact.plan$rows$study_rows), 2)
  expect_true(compact.plan$rows$ylim[[1]] >= -2.5)
  expect_lt(compact.plan$device$height, 5)
  expect_equal(rcmetar.metafor.forest.line.types(compact.plan), c("solid", "blank"))

  sequential.bundle$params$fp_style <- "bmj"
  sequential.bundle$fp_style <- "bmj"
  bmj.compact.plan <- rcmetar.forest.layout.preflight(sequential.bundle, style = "bmj")

  expect_equal(bmj.compact.plan$style$name, "bmj")
  expect_equal(bmj.compact.plan$style$template, "compact")
  expect_true(bmj.compact.plan$rows$manual_sequential_labels)
  expect_lt(bmj.compact.plan$rows$top - max(bmj.compact.plan$rows$study_rows), 2)
  expect_lt(bmj.compact.plan$device$height, 5)
})

test_that("Forest Layout Preflight keeps hidden-header CI lines and readable moderate-row text", {
  fixture <- metafor_binary_fixture()
  fixture$params$fp_show_headers <- FALSE
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
  expect_equal(rcmetar.metafor.forest.line.types(default.plan), c("solid", "solid"))

  fixture$params$fp_style <- "revman"
  revman.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  revman.plan <- rcmetar.forest.layout.preflight(revman.bundle)
  expect_gte(revman.plan$metrics$text_floor, 0.78)

  fixture$params$fp_style <- "bmj"
  bmj.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  bmj.plan <- rcmetar.forest.layout.preflight(bmj.bundle)
  expect_gte(bmj.plan$metrics$text_floor, 0.82)
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
  expect_equal(bundle$style_blocks$favours_left, "Favours Intervention")
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

test_that("diagnostic RevMan Forest Style uses DTA columns and a probability-scale metric axis", {
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
  expect_equal(rcmetar.metafor.xlab(bundle), "Sensitivity (probability scale)")
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²")

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
})

test_that("plot axis default placeholders resolve to the metric label", {
  fixture <- metafor_binary_fixture()
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  for (placeholder in c(NA_character_, "[default]", "[Default]", "<default>", "default")) {
    params <- fixture$params
    if (is.na(placeholder)) {
      params$fp_xlabel <- NULL
    } else {
      params$fp_xlabel <- placeholder
    }
    bundle <- rcmetar.regenerate.plot.data(fixture$data, res, params)
    expect_identical(rcmetar.metafor.xlab(bundle), "Odds Ratio (log scale)")
  }

  params <- fixture$params
  params$fp_xlabel <- "Study-defined effect"
  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, params)
  expect_identical(rcmetar.metafor.xlab(bundle), "Study-defined effect")
})

test_that("BMJ Forest Style builds faithful family columns and renders smoke cases", {
  fixtures <- list(
    binary = list(
      fixture = metafor_binary_fixture(),
      expected_headers = c("", "", "Weight"),
      expected_groups = c("Intervention", "Control"),
      axis_label = "",
      favours_left = "Favors control",
      favours_right = "Favors intervention"
    ),
    continuous = list(
      fixture = metafor_continuous_fixture(),
      expected_headers = c("Total", "Mean", "SD", "Total", "Mean", "SD", "Weight"),
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
    expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²=")
    expect_match(bundle$style_blocks$heterogeneity, ", df=")
    expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z=")
    expect_equal(rcmetar.forest.accent.color(bundle$params), "#6b58a6")
    if (identical(bundle$data_type, "binary")) {
      summary <- rcmetar.bmj.summary.effect(bundle)
      expect_gte(min(summary$psize, na.rm = TRUE), 1.2)
      expect_gte(max(summary$psize, na.rm = TRUE), 2.0)
    }
    if (identical(bundle$data_type, "continuous")) {
      expect_equal(unname(bundle$ilab$matrix[1, 1:6]), c("22", "8.200", "1.500", "20", "9.000", "1.600"))
    }

    png_path <- tempfile(fileext = ".png")
    rcmetar.draw.forest.plot(bundle, png_path)
    expect_true(file.exists(png_path))
    expect_gt(file.info(png_path)$size, 5000)
  }
})

test_that("BMJ raw-column layouts measure long labels and wrapped headers", {
  make_bundle <- function(fixture) {
    res <- rma.uni(
      yi = fixture$data@y,
      sei = fixture$data@SE,
      slab = fixture$data@study.names,
      method = fixture$params$rm.method,
      level = fixture$params$conf.level,
      digits = fixture$params$digits
    )
    rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)
  }

  short.fixture <- metafor_binary_fixture()
  short.fixture$params$fp_style <- "bmj"
  short.bundle <- make_bundle(short.fixture)
  short.plan <- rcmetar.forest.layout.preflight(short.bundle)

  long.fixture <- metafor_binary_fixture()
  long.fixture$params$fp_style <- "bmj"
  long.fixture$params$fp_col3_str <- "Experimental intervention with long header"
  long.fixture$params$fp_col4_str <- "Control condition with long header"
  long.fixture$data@study.names <- paste(
    long.fixture$data@study.names,
    "International protocol-defined multicentre trial with extended label"
  )
  long.bundle <- make_bundle(long.fixture)
  long.plan <- rcmetar.forest.layout.preflight(long.bundle)

  continuous.fixture <- metafor_continuous_fixture()
  continuous.fixture$params$fp_style <- "bmj"
  continuous.bundle <- make_bundle(continuous.fixture)
  continuous.plan <- rcmetar.forest.layout.preflight(continuous.bundle)
  continuous.rules <- rcmetar.bmj.group.header.rules(continuous.bundle, continuous.plan$layout, continuous.bundle$ilab)

  expect_equal(long.plan$style$name, "bmj")
  expect_equal(long.plan$style$template, "standard")
  expect_gt(long.plan$device$width, short.plan$device$width)
  expect_gt(long.plan$device$height, short.plan$device$height)
  expect_gte(long.plan$device$header_lines, 3)
  expect_gte(long.plan$device$direction_lines, 3)
  expect_lt(max(as.numeric(long.plan$columns$ilab.xpos[1:2])), long.plan$x$alim[[1]])
  expect_gt(long.plan$columns$annotation.xpos, long.plan$x$alim[[2]])
  expect_gt(long.plan$footer$axis$left.max.width, 0)
  expect_gt(long.plan$footer$axis$right.max.width, 0)
  expect_match(rcmetar.bmj.wrap.header(long.bundle$ilab$groups[[1]]), "\n", fixed = TRUE)
  expect_match(rcmetar.bmj.wrap.direction(long.bundle$style_blocks$favours_right), "\n", fixed = TRUE)
  expect_false("layout_plan" %in% names(long.bundle))
  expect_equal(continuous.rules$group, c("Treatment", "Control"))
  expect_lt(continuous.rules$left[[1]], min(continuous.plan$layout$ilab.xpos[1:3]))
  expect_gt(continuous.rules$right[[1]], max(continuous.plan$layout$ilab.xpos[1:3]))
  expect_lt(continuous.rules$left[[2]], min(continuous.plan$layout$ilab.xpos[4:6]))
  expect_gt(continuous.rules$right[[2]], max(continuous.plan$layout$ilab.xpos[4:6]))
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

test_that("RevMan and BMJ styles honor hidden raw count columns", {
  styles <- c("revman", "bmj")
  fixtures <- list(
    binary = metafor_binary_fixture(),
    continuous = metafor_continuous_fixture(),
    diagnostic = metafor_diagnostic_fixture()
  )

  for (style in styles) {
    for (fixture in fixtures) {
      fixture$params$fp_style <- style
      fixture$params$fp_show_raw_counts <- FALSE
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
      expect_equal(bundle$fp_style, style)
      expect_equal(bundle$ilab$headers, "Weight")
      expect_equal(bundle$ilab$groups, character(0))
      expected.weight <- if (identical(style, "bmj")) "100.0" else "100.0%"
      expect_equal(bundle$style_blocks$totals$weight, expected.weight)

      png_path <- tempfile(fileext = ".png")
      rcmetar.draw.forest.plot(bundle, png_path)
      expect_true(file.exists(png_path))
      expect_gt(file.info(png_path)$size, 5000)
    }
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

test_that("plot text ceilings preserve source study names and numeric data", {
  fixture <- metafor_binary_fixture()
  original.name <- paste(rep("Very long identifying study name", 5), collapse = " ")
  fixture$data@study.names[[1]] <- original.name
  original.y <- fixture$data@y
  fixture$params$fp_col1_str <- paste(rep("Long heading", 12), collapse = " ")
  fixture$params$fp_xlabel <- paste(rep("Long axis label", 12), collapse = " ")
  res <- rma.uni(yi=fixture$data@y, sei=fixture$data@SE, method="DL")

  bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_identical(fixture$data@study.names[[1]], original.name)
  expect_identical(fixture$data@y, original.y)
  expect_lte(nchar(bundle$slab[[1]]), 72)
  expect_match(bundle$slab[[1]], "\\.\\.\\.")
  expect_true(endsWith(bundle$slab[[1]], as.character(fixture$data@years[[1]])))
  expect_equal(nchar(bundle$params$fp_col1_str), 80)
  expect_equal(nchar(bundle$params$fp_xlabel), 80)
  expect_identical(
    rcmetar.truncate.plot.display.text(c(NA_character_, "Study")),
    c(NA_character_, "Study")
  )
})

test_that("subgroup display headings truncate without changing grouping state", {
  fixture <- metafor_binary_fixture()
  long.group <- paste(rep("Long subgroup category", 6), collapse=" ")
  fixture$params$cov_name <- "Era"
  fixture$data@covariates <- list(new(
    "CovariateValues", cov.name="Era",
    cov.vals=c(rep(long.group, 3), rep("Short group", 3)),
    cov.type="factor", ref.var=long.group
  ))
  result <- subgroup.ma.binary("binary.random", fixture$data, fixture$params)
  bundle <- load_saved_plot_data(unname(result$plot_params_paths[[1]]))

  expect_lte(nchar(bundle$subgroups$names[[1]]), 72)
  expect_match(bundle$subgroups$names[[1]], "\\.\\.\\.")
  expect_identical(
    as.character(bundle$regeneration_state$subgroup_data$subgroup.list[[1]]),
    long.group
  )
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

test_that("journal display labels do not duplicate publication years", {
  fixture <- metafor_binary_fixture(studies = 2)
  fixture$data@study.names <- c("Alpha Trial 2024", "Beta Trial")
  fixture$data@years <- as.integer(c(2024, 2023))

  expect_equal(
    rcmetar.study.labels(fixture$data),
    c("Alpha Trial 2024", "Beta Trial, 2023")
  )
})

test_that("subgroup model labels preserve readable word spacing", {
  result <- list(QE=1.2, k=3, p=1, QEp=0.2, I2=30, tau2=0.1)
  label <- rcmetar.default.model.label("RE Model for Subgroup", result)

  expect_type(label, "character")
  expect_match(label, "Subgroup (Q =", fixed=TRUE)
  expect_match(label, "I² = 30.0%", fixed=TRUE)
  expect_match(label, "τ² = 0.10", fixed=TRUE)
})

test_that("raster plot exports default to publication-grade resolution", {
  expect_equal(rcmetar.plot.export.dpi(list()), 600)
  expect_equal(rcmetar.plot.export.dpi(list(dpi=900)), 900)
  expect_equal(
    unname(rcmetar.plot.pixel.size(list(width=3, height=2))),
    c(1800, 1200)
  )
})

test_that("single-arm binary metrics build and render Default metafor bundles", {
  metrics <- c("PR", "PLN", "PLO", "PAS", "PFT")

  for (metric in metrics) {
    fixture <- metafor_binary_one_arm_fixture(measure = metric)
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
    expect_equal(bundle$data_type, "binary")
    expect_equal(bundle$ilab$headers, c("Events", "Non-events"))
    expect_equal(bundle$ilab$groups, "Cohort")
    expect_equal(unname(bundle$ilab$matrix[1, ]), c("4", "96"))
    expect_equal(bundle$sample_sizes, fixture$data@g1O1 + fixture$data@g1O2)
    expect_true(inherits(bundle$res, "rma"))
    expect_equal(rcmetar.metafor.effect.header(bundle), paste0(pretty.metric.name(metric), " [95% CI]"))
    expect_true(all(is.finite(rcmetar.metafor.alim(bundle))))

    png_path <- tempfile(fileext = ".png")
    rcmetar.draw.forest.plot(bundle, png_path)

    expect_true(file.exists(png_path))
    expect_gt(file.info(png_path)$size, 5000)
  }
})

test_that("single-arm binary RevMan and BMJ styles use one-arm count columns and plain metric axes", {
  fixture <- metafor_binary_one_arm_fixture(measure = "PLO")
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  fixture$params$fp_style <- "revman"
  revman.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(revman.bundle$ilab$headers, c("Events", "Total", "Weight"))
  expect_equal(revman.bundle$ilab$groups, "Cohort")
  expect_equal(unname(revman.bundle$ilab$matrix[1, 1:2]), c("4", "100"))
  expect_equal(revman.bundle$style_blocks$favours_left, "")
  expect_equal(revman.bundle$style_blocks$favours_right, "")
  expect_equal(revman.bundle$style_blocks$axis_label, pretty.metric.name("PLO"))
  expect_equal(revman.bundle$style_blocks$totals$experimental_total, 500)
  expect_equal(revman.bundle$style_blocks$total_events$experimental_events, 55)

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(revman.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)

  fixture$params$fp_style <- "bmj"
  bmj.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bmj.bundle$ilab$headers, c("", "Weight"))
  expect_equal(bmj.bundle$ilab$groups, "Cohort")
  expect_equal(unname(bmj.bundle$ilab$matrix[1, 1]), "4 / 100")
  expect_equal(bmj.bundle$style_blocks$favours_left, "")
  expect_equal(bmj.bundle$style_blocks$favours_right, "")
  expect_equal(bmj.bundle$style_blocks$axis_label, pretty.metric.name("PLO"))
  expect_equal(bmj.bundle$style_blocks$totals$experimental_events_total, "55 / 500")

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bmj.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
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

test_that("single-arm continuous styles use one-arm mean SD N columns and plain metric axes", {
  fixture <- metafor_continuous_one_arm_fixture()
  res <- rma.uni(
    yi = fixture$data@y,
    sei = fixture$data@SE,
    slab = fixture$data@study.names,
    method = fixture$params$rm.method,
    level = fixture$params$conf.level,
    digits = fixture$params$digits
  )

  default.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(default.bundle$render_engine, "metafor")
  expect_equal(default.bundle$data_type, "continuous")
  expect_equal(default.bundle$ilab$headers, c("Mean", "SD", "N"))
  expect_equal(default.bundle$ilab$groups, "Cohort")
  expect_equal(unname(default.bundle$ilab$matrix[1, ]), c("8.200", "1.500", "22"))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(default.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)

  fixture$params$fp_style <- "revman"
  revman.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(revman.bundle$ilab$headers, c("Mean", "SD", "Total", "Weight"))
  expect_equal(revman.bundle$ilab$groups, "Cohort")
  expect_equal(revman.bundle$style_blocks$favours_left, "")
  expect_equal(revman.bundle$style_blocks$favours_right, "")
  expect_equal(revman.bundle$style_blocks$axis_label, pretty.metric.name("TXMean"))
  revman.layout <- rcmetar.revman.layout(revman.bundle)
  revman.span <- max(diff(revman.layout$alim), 1)
  expect_lte(revman.layout$annotation.xpos, revman.layout$alim[[1]] - 0.70 * revman.span)
  expect_gte(revman.layout$annotation.xpos - max(revman.layout$ilab.xpos), 1.00 * revman.span)

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(revman.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)

  fixture$params$fp_style <- "bmj"
  bmj.bundle <- rcmetar.regenerate.plot.data(fixture$data, res, fixture$params)

  expect_equal(bmj.bundle$ilab$headers, c("Total", "Mean", "SD", "Weight"))
  expect_equal(bmj.bundle$ilab$groups, "Cohort")
  expect_equal(bmj.bundle$style_blocks$favours_left, "")
  expect_equal(bmj.bundle$style_blocks$favours_right, "")
  expect_equal(bmj.bundle$style_blocks$axis_label, pretty.metric.name("TXMean"))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bmj.bundle, png_path)
  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 5000)
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

test_that("diagnostic extraction keeps image order aligned with semantic forest keys", {
  fit <- list(
    Summary = list(),
    images = c("forest.png" = "forest.png"),
    plot_params_paths = c("Forest Plot" = "forest.rds"),
    image_order = "Forest Plot"
  )

  extracted <- rcmetar.diagnostic.extract(fit, list(measure = "Sens"))

  expect_identical(names(extracted$images), "diagnostic.Sens.forest")
  expect_identical(names(extracted$plot.paths), "diagnostic.Sens.forest")
  expect_identical(extracted$image.order, "diagnostic.Sens.forest")
  expect_identical(extracted$sections[[2]]$title, "Sensitivity Forest Plot")
})

test_that("diagnostic multi-metric workflows save independent metafor forest plots", {
  fixture <- metafor_diagnostic_fixture(measure = "Sens")
  run_metrics <- function(measures) {
    params <- lapply(
      measures,
      function(measure) metafor_diagnostic_params(tempfile(fileext = ".png"), measure)
    )

    result <- rcmetar.run.diagnostic.analyses(
      fixture$data,
      rep("diagnostic.random", length(measures)),
      params,
      version=1
    )
    expected_titles <- paste(
      vapply(measures, pretty.metric.name, character(1)),
      "Forest Plot"
    )
    expected_keys <- paste0("diagnostic.", measures, ".forest")

    expect_identical(names(result$images), expected_keys)
    expect_identical(names(result$plot_params_paths), expected_keys)
    expect_identical(result$image_order, expected_keys)
    expect_false(any(grepl(" and ", names(result$images), fixed = TRUE)))

    image.sections <- Filter(function(section) identical(section$kind, "image"), result$sections)
    expect_identical(
      vapply(image.sections, function(section) section$source_key, character(1)),
      expected_keys
    )
    expect_identical(
      vapply(image.sections, function(section) section$title, character(1)),
      expected_titles
    )

    for (measure in measures) {
      key <- paste0("diagnostic.", measure, ".forest")
      image_path <- unname(result$images[[key]])
      plot_data <- load_saved_plot_data(
        unname(result$plot_params_paths[[key]])
      )

      expect_true(rcmetar.is.metafor.forest.bundle(plot_data))
      expect_equal(plot_data$render_engine, "metafor")
      expect_equal(plot_data$params$measure, measure)
      expect_true(file.exists(image_path))
      expect_gt(file.info(image_path)$size, 5000)
    }
  }

  run_metrics(c("Sens", "Spec", "NLR", "PLR"))
})

test_that("repeated diagnostic workflows keep metric forest plots independent", {
  for (workflow in c("leave-one-out", "subgroup")) {
    fixture <- metafor_diagnostic_fixture(measure = "NLR")
    measures <- c("NLR", "PLR")
    params <- lapply(
      measures,
      function(measure) metafor_diagnostic_params(tempfile(fileext = ".png"), measure)
    )

    if (workflow == "subgroup") {
      fixture$data@covariates <- list(new(
        "CovariateValues",
        cov.name = "Era",
        cov.vals = c("Early", "Early", "Early", "Late", "Late"),
        cov.type = "factor",
        ref.var = "Early"
      ))
      params <- lapply(params, function(metric_params) {
        metric_params$cov_name <- "Era"
        metric_params$create.plot <- NULL
        metric_params
      })
    }

    result <- rcmetar.run.diagnostic.analyses(
      fixture$data,
      rep("diagnostic.random", length(measures)),
      params,
      workflow = workflow,
      version=1
    )
    expected_names <- paste(
      vapply(measures, pretty.metric.name, character(1)),
      "Forest Plot"
    )

    expect_setequal(names(result$images), expected_names)
    expect_setequal(names(result$plot_params_paths), expected_names)
    expect_false(any(grepl(" and ", names(result$images), fixed = TRUE)))
    expect_true(all(file.exists(unname(result$images))))

    bundles <- lapply(unname(result$plot_params_paths), load_saved_plot_data)
    expect_true(all(vapply(bundles, rcmetar.is.metafor.forest.bundle, logical(1))))
    expect_setequal(
      vapply(bundles, function(bundle) bundle$params$measure, character(1)),
      measures
    )
  }
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

test_that("workflow forest artifacts regenerate through their saved public contract", {
  cases <- list(
    cumulative = function() {
      fixture <- metafor_binary_fixture()
      fixture$params$fp_outpath <- tempfile(fileext = ".png")
      list(fixture = fixture, result = cum.ma.binary("binary.random", fixture$data, fixture$params))
    },
    `leave-one-out` = function() {
      fixture <- metafor_continuous_fixture()
      fixture$params$fp_outpath <- tempfile(fileext = ".png")
      list(fixture = fixture, result = loo.ma.continuous("continuous.random", fixture$data, fixture$params))
    },
    subgroup = function() {
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
      list(fixture = fixture, result = subgroup.ma.binary("binary.random", fixture$data, fixture$params))
    }
  )

  for (variant in names(cases)) {
    case <- cases[[variant]]()
    params.path <- unname(case$result$plot_params_paths[[1]])
    load(paste0(params.path, ".data"))
    load(paste0(params.path, ".params"))
    load(paste0(params.path, ".res"))
    if (identical(variant, "cumulative")) {
      expect_equal(params$fp_col1_str, "Cumulative Studies")
      expect_equal(params$fp_col2_str, "Cumulative Estimate")
    }
    expect_false(identical(params$fp_plot_lb, "[default]"))
    expect_false(identical(params$fp_plot_ub, "[default]"))
    params$fp_style <- "bmj"

    regenerated <- rcmetar.regenerate.plot.data(om.data, res, params)
    regenerated.path <- tempfile(fileext = ".svg")
    rcmetar.draw.forest.plot(regenerated, regenerated.path)

    expect_equal(regenerated$forest_variant, variant)
    expect_equal(regenerated$fp_style, "bmj")
    if (identical(variant, "cumulative")) {
      expect_equal(regenerated$params$fp_col1_str, "Cumulative Studies")
      expect_equal(regenerated$params$fp_col2_str, "Cumulative Estimate")
    }
    expect_true(rcmetar.is.metafor.forest.bundle(regenerated))
    expect_true(file.exists(regenerated.path))
    expect_gt(file.info(regenerated.path)$size, 3000)
  }
})

test_that("forest regeneration state rejects unsupported parameter overrides", {
  expect_error(
    rcmetar.forest.regeneration.state(
      "subgroup",
      subgroup.data = list(subgroup.list=list(), grouped.data=list(), results=list()),
      param.overrides = list(fp_col1_str="Unexpected")
    ),
    "does not support parameter overrides"
  )
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

test_that("cumulative workflow handles entered-effect-only data in Default, RevMan, and BMJ styles", {
  fixtures <- list(
    binary = list(fixture_fn = metafor_entered_binary_fixture, method = "binary.random", runner = cum.ma.binary),
    continuous = list(fixture_fn = metafor_entered_continuous_fixture, method = "continuous.random", runner = cum.ma.continuous),
    diagnostic = list(fixture_fn = metafor_entered_diagnostic_fixture, method = "diagnostic.random", runner = cum.ma.diagnostic)
  )

  for (entry in fixtures) {
    for (style in c("default", "revman", "bmj")) {
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

test_that("leave-one-out workflow handles entered-effect-only data in Default, RevMan, and BMJ styles", {
  fixtures <- list(
    binary = list(fixture_fn = metafor_entered_binary_fixture, method = "binary.random", runner = loo.ma.binary),
    continuous = list(fixture_fn = metafor_entered_continuous_fixture, method = "continuous.random", runner = loo.ma.continuous),
    diagnostic = list(fixture_fn = metafor_entered_diagnostic_fixture, method = "diagnostic.random", runner = loo.ma.diagnostic)
  )

  for (entry in fixtures) {
    for (style in c("default", "revman", "bmj")) {
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
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#2f5597")
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)

  plan <- rcmetar.forest.layout.preflight(bundle)
  expect_true(all(bundle$effect$yi >= plan$x$alim[[1]] &
                  bundle$effect$yi <= plan$x$alim[[2]]))
  expected.labels <- rcmetar.forest.left.block.labels(bundle)
  measured.width <- rcmetar.forest.with.measurement.device(max(vapply(
    expected.labels,
    function(label) max(strwidth(label, units = "inches", cex = plan$typography$cex)),
    numeric(1)
  )))
  expect_gte(plan$device$left_block_width, measured.width)
  expect_gt(min(plan$x$alim) - rcmetar.forest.study.x(plan$layout),
            measured.width * diff(plan$x$alim) / plan$device$plot_width)
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
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#000000")
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
  expect_match(bundle$style_blocks$heterogeneity, "Heterogeneity: Tau²=")
  expect_match(bundle$style_blocks$test_overall, "Test for overall effect: Z=")
  expect_equal(rcmetar.forest.accent.color(bundle$params), "#6b58a6")
  expect_true(file.exists(unname(result$images[[1]])))
  expect_gt(file.info(unname(result$images[[1]]))$size, 5000)
})
