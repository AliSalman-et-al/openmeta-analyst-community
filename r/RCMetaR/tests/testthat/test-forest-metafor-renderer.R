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

read_png_dimensions <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con))
  bytes <- readBin(con, "integer", n = 24, size = 1, signed = FALSE, endian = "big")
  c(
    width = sum(bytes[17:20] * 256^(3:0)),
    height = sum(bytes[21:24] * 256^(3:0))
  )
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
  expect_equal(bundle$ilab$headers, c("Events", "Total", "Events", "Total"))
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
  expect_equal(bundle$ilab$headers, c("Events", "Total", "Events", "Total"))

  png_path <- tempfile(fileext = ".png")
  rcmetar.draw.forest.plot(bundle, png_path)

  expect_true(file.exists(png_path))
  expect_gt(file.info(png_path)$size, 3000)
})
