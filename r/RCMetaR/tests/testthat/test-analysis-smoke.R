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
    fp_col1_str = "Study or Subgroup",
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
  if (length(result$images) > 0) {
    expect_named(result$plot_capabilities, names(result$images), ignore.order = TRUE)
    expect_true(all(vapply(
      result$plot_capabilities,
      function(descriptor) identical(
        names(descriptor),
        c("plot_kind", "editable", "styleable", "composition", "regenerator")
      ),
      logical(1)
    )))
  }
}

test_that("plot capability metadata distinguishes workflow-specific forest kinds", {
  fixture <- binary_fixture()
  expected_kinds <- c(
    standard = "forest",
    cumulative = "cumulative_forest",
    "leave-one-out" = "leave_one_out_forest",
    subgroup = "subgroup_forest"
  )

  for (workflow in names(expected_kinds)) {
    result <- rcmetar.run.analysis(
      fixture$data,
      list(version=1, method= "binary.random", params = fixture$params, workflow = workflow)
    )
    expect_true(all(vapply(
      result$plot_capabilities,
      function(descriptor) identical(descriptor$plot_kind, unname(expected_kinds[[workflow]])),
      logical(1)
    )))
    expect_true(all(vapply(
      result$plot_capabilities,
      function(descriptor) isTRUE(descriptor$editable),
      logical(1)
    )))
  }
})

test_that("plot kind capabilities derive editability from support and artifact data", {
  expected <- list(
    forest = list(styleable = TRUE, regenerator = "forest", editable = TRUE),
    cumulative_forest = list(styleable = TRUE, regenerator = "forest", editable = TRUE),
    leave_one_out_forest = list(styleable = TRUE, regenerator = "forest", editable = TRUE),
    subgroup_forest = list(styleable = TRUE, regenerator = "forest", editable = TRUE),
    regression = list(styleable = TRUE, regenerator = "regression", editable = TRUE),
    roc = list(styleable = FALSE, regenerator = "none", editable = FALSE),
    sroc = list(styleable = TRUE, regenerator = "sroc", editable = TRUE),
    other = list(styleable = FALSE, regenerator = "none", editable = FALSE)
  )

  for (plot.kind in names(expected)) {
    with.data <- .rcmetar.plot.descriptor.for.kind(plot.kind, has.params = TRUE)
    without.data <- .rcmetar.plot.descriptor.for.kind(plot.kind, has.params = FALSE)
    expect_identical(with.data$styleable, expected[[plot.kind]]$styleable)
    expect_identical(with.data$regenerator, expected[[plot.kind]]$regenerator)
    expect_identical(with.data$editable, expected[[plot.kind]]$editable)
    expect_false(without.data$editable)
  }
})

test_that("analysis plot capability query maps workflows through the kind registry", {
  cases <- list(
    list("binary", "binary.random", "standard", "forest"),
    list("binary", "binary.random", "cumulative", "cumulative_forest"),
    list("binary", "binary.random", "leave-one-out", "leave_one_out_forest"),
    list("binary", "binary.random", "subgroup", "subgroup_forest"),
    list("binary", "binary.random", "bootstrap", "other"),
    list("binary", "meta.regression", "meta-regression", "regression")
  )

  for (case in cases) {
    descriptor <- rcmetar.analysis.plot.capabilities(
      case[[1]], case[[2]], case[[3]]
    )[[1]]
    expect_identical(descriptor$plot_kind, case[[4]])
    expect_identical(
      descriptor$editable,
      descriptor$regenerator != "none"
    )
  }

  reitsma <- rcmetar.analysis.plot.capabilities(
    "diagnostic", "diagnostic.reitsma", "standard"
  )
  expect_identical(vapply(reitsma, `[[`, character(1), "plot_kind"), "sroc")

  reitsma.regression <- rcmetar.analysis.plot.capabilities(
    "diagnostic", "diagnostic.reitsma", "meta-regression"
  )
  expect_identical(
    vapply(reitsma.regression, `[[`, character(1), "plot_kind"),
    "forest"
  )
})

test_that("plot data availability is matched to each plot artifact", {
  result <- list(
    images = c(
      "First Plot" = "first.svg",
      "Second Plot" = "second.svg",
      "Third Plot" = "third.svg",
      "Fourth Plot" = "fourth.svg"
    ),
    plot_params_paths = c(
      "First Plot" = "first.plotdata",
      "Second Plot" = "",
      "Third Plot" = NA_character_
    )
  )
  request <- list(workflow = "standard", method = "binary.random")

  attached <- .rcmetar.attach.plot.capabilities(result, request)

  expect_true(attached$plot_capabilities[["First Plot"]]$editable)
  expect_false(attached$plot_capabilities[["Second Plot"]]$editable)
  expect_false(attached$plot_capabilities[["Third Plot"]]$editable)
  expect_false(attached$plot_capabilities[["Fourth Plot"]]$editable)
})

test_that("representative binary analysis paths execute", {
  fixture <- binary_fixture()
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "binary.random", params = fixture$params)))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "binary.random", params = fixture$params, workflow = "cumulative")))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "binary.random", params = fixture$params, workflow = "leave-one-out")))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "binary.random", params = fixture$params, workflow = "subgroup")))
})

test_that("forest analysis returns an explicit internal SVG display artifact", {
  fixture <- continuous_fixture()
  fixture$params$create.plot <- TRUE
  fixture$params$fp_outpath <- tempfile(fileext = ".png")
  fixture$params$fp_display_path <- tempfile(pattern = "forest-display-", fileext = ".svg")

  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "continuous.random", params = fixture$params)
  )

  expect_equal(unname(result$images[["Forest Plot"]]), fixture$params$fp_outpath)
  expect_equal(
    unname(result$display_images[["Forest Plot"]]),
    fixture$params$fp_display_path
  )
  expect_true(file.exists(fixture$params$fp_outpath))
  expect_true(file.exists(fixture$params$fp_display_path))
  expect_false(file.exists(rcmetar.plot.canonical_svg_path(fixture$params$fp_outpath)))

  fixture$params$fp_outpath <- tempfile(pattern = "forest-export-", fileext = ".svg")
  fixture$params$fp_display_path <- tempfile(
    pattern = "forest-internal-display-", fileext = ".svg"
  )
  svg.result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "continuous.random", params = fixture$params)
  )
  expect_false(rcmetar.plot.paths.equal(
    fixture$params$fp_outpath,
    fixture$params$fp_display_path
  ))
  expect_equal(
    unname(svg.result$display_images[["Forest Plot"]]),
    fixture$params$fp_display_path
  )
  expect_true(file.exists(fixture$params$fp_outpath))
  expect_true(file.exists(fixture$params$fp_display_path))
})

test_that("representative continuous analysis paths execute", {
  fixture <- continuous_fixture()
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "continuous.random", params = fixture$params)))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "continuous.random", params = fixture$params, workflow = "cumulative")))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "continuous.random", params = fixture$params, workflow = "leave-one-out")))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "continuous.random", params = fixture$params, workflow = "subgroup")))
})

test_that("single-arm continuous GUI metric label produces a metafor forest bundle", {
  fixture <- continuous_fixture()
  fixture$params$measure <- "TX Mean"
  fixture$params$create.plot <- TRUE
  fixture$params$fp_outpath <- tempfile(fileext = ".png")
  fixture$data <- new(
    "ContinuousData",
    y = fixture$data@mean1,
    SE = fixture$data@sd1 / sqrt(fixture$data@N1),
    study.names = fixture$data@study.names,
    years = fixture$data@years
  )

  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "continuous.random", params = fixture$params)
  )
  plot.data.env <- new.env(parent = emptyenv())
  load(
    paste0(unname(result$plot_params_paths[["Forest Plot"]]), ".plotdata"),
    envir = plot.data.env
  )
  plot.data <- plot.data.env$plot.data

  expect_true(rcmetar.is.metafor.forest.bundle(plot.data))
  expect_equal(plot.data$params$measure, "TXMean")
  expect_true(file.exists(unname(result$images[["Forest Plot"]])))
})

test_that("representative diagnostic analysis paths execute", {
  fixture <- diagnostic_fixture("Sens")
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "diagnostic.random", params = fixture$params)))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "diagnostic.random", params = fixture$params, workflow = "cumulative")))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "diagnostic.random", params = fixture$params, workflow = "leave-one-out")))
  expect_analysis_result(rcmetar.run.analysis(fixture$data, list(version=1, method= "diagnostic.random", params = fixture$params, workflow = "subgroup")))
})

test_that("core analysis facade dispatches representative workflows", {
  binary <- binary_fixture()
  binary_result <- rcmetar.run.analysis(
    binary$data,
    list(version=1, method= "binary.random", params = binary$params)
  )
  expect_analysis_result(binary_result)
  expect_equal(attr(binary_result, "rcmetar.request")$workflow, "standard")

  continuous <- continuous_fixture()
  continuous_result <- rcmetar.run.analysis(
    continuous$data,
    list(version=1, method= "continuous.random", params = continuous$params, workflow = "leave-one-out")
  )
  expect_analysis_result(continuous_result)
  expect_s3_class(continuous_result[["Leave-one-out Summary"]], "summary.display")

  diagnostic <- diagnostic_fixture("Sens")
  subgroup_result <- rcmetar.run.analysis(
    diagnostic$data,
    list(version=1, method= "diagnostic.random", params = diagnostic$params, workflow = "subgroup")
  )
  expect_analysis_result(subgroup_result)
  expect_equal(attr(subgroup_result, "rcmetar.request")$workflow, "subgroup")
})

test_that("core diagnostic multi-analysis facade preserves multi-metric results", {
  fixture <- diagnostic_fixture("Sens")
  sens_params <- fixture$params
  spec_params <- fixture$params
  sens_params$create.plot <- TRUE
  spec_params$create.plot <- TRUE
  sens_params$fp_display_path <- tempfile(
    pattern = "diagnostic-sens-display-", fileext = ".svg"
  )
  spec_params$measure <- "Spec"
  spec_params$fp_outpath <- file.path("r_tmp", "forest_Spec.png")
  spec_params$fp_display_path <- tempfile(
    pattern = "diagnostic-spec-display-", fileext = ".svg"
  )
  spec_effects <- get.res.for.one.diag.study(fixture$data, spec_params)
  spec_data <- fixture$data
  spec_data@y <- spec_effects$b
  spec_data@SE <- spec_effects$se

  result <- rcmetar.run.diagnostic.analyses(
    spec_data,
    c("diagnostic.random", "diagnostic.random"),
    list(sens_params, spec_params),
    version=1
  )

  expect_analysis_result(result)
  expect_true(any(grepl("Sens|Spec", names(result))))
  expect_named(
    result$display_images,
    c("diagnostic.Sens.forest", "diagnostic.Spec.forest"),
    ignore.order = TRUE
  )
  expect_false("SROC" %in% names(result$display_images))
  expect_true(all(file.exists(c(
    sens_params$fp_display_path,
    spec_params$fp_display_path
  ))))
  expect_equal(attr(result, "rcmetar.request")$workflow, "standard")
  expect_false(any(file.exists(paste0(
    c(sens_params$fp_outpath, spec_params$fp_outpath),
    "INTER"
  ))))
})

test_that("diagnostic study effects include confidence intervals for each metric", {
  effects <- rcmetar.diagnostic.study.effects(
    tp = 19,
    fn = 10,
    fp = 1,
    tn = 81,
    metrics = c("Sens", "Spec", "PLR", "NLR", "DOR"),
    conf.level = 95
  )

  expect_named(effects, c("Sens", "Spec", "PLR", "NLR", "DOR"))
  for (metric in names(effects)) {
    expect_length(effects[[metric]]$calc_scale, 3)
    expect_length(effects[[metric]]$display_scale, 3)
    expect_false(any(is.na(effects[[metric]]$calc_scale)))
    expect_false(any(is.na(effects[[metric]]$display_scale)))
  }
})

test_that("core facade rejects incompatible methods before dispatch", {
  fixture <- binary_fixture()
  expect_error(
    rcmetar.run.analysis(
      fixture$data,
      list(version=1, method= "continuous.random", params = fixture$params)
    ),
    "not supported for binary data"
  )
})

test_that("core method discovery and metadata avoid direct implementation export scanning", {
  fixture <- binary_fixture()
  methods <- rcmetar.available.methods("binary", fixture$data, "OR")

  expect_true("Binary Random-Effects" %in% names(methods))
  expect_equal(methods[["Binary Random-Effects"]], "binary.random")
  expect_false(any(grepl("parameters|pretty.names|overall", methods)))

  params <- rcmetar.method.parameters("binary.random")
  expect_named(params, c("parameters", "defaults", "var_order", "pretty.names"), ignore.order = TRUE)
  expect_true("conf.level" %in% names(params$parameters))
  expect_identical(params$parameters$inference.method, c("z", "t", "knha", "adhoc"))
  expect_identical(params$defaults$inference.method, "z")
  expect_identical(
    params$parameters$rm.method,
    c("HE", "DL", "HS", "HSk", "SJ", "ML", "REML", "EB", "PM", "PMM")
  )

  regression.methods <- rcmetar.available.methods(
    "binary", fixture$data, "OR", workflow = "meta-regression"
  )
  expect_identical(unname(unlist(regression.methods)), "meta.regression")
  regression.params <- rcmetar.method.parameters("meta.regression")
  expect_identical(
    regression.params$var_order,
    c("rm.method", "inference.method", "conf.level", "digits")
  )
  expect_identical(regression.params$defaults$rm.method, "REML")
  expect_identical(regression.params$defaults$inference.method, "z")

  fixed.params <- rcmetar.method.parameters("binary.fixed.inv.var")
  expect_true("inference.method" %in% names(fixed.params$parameters))
  mh.params <- rcmetar.method.parameters("binary.fixed.mh")
  expect_false("inference.method" %in% names(mh.params$parameters))

  description <- rcmetar.method.description("binary.random")
  expect_type(description, "character")
  expect_true(nzchar(description))
})

test_that("meta-regression supplies metafor digits when the request omits them", {
  fixture <- binary_fixture()
  fixture$params$digits <- NULL
  fixture$params$create.plot <- FALSE

  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "meta.regression", params = fixture$params,
         workflow = "meta-regression", stop.at.rma = TRUE)
  )

  expect_s3_class(result, "rma")
  expect_length(result$b, 2)
})

test_that("inference method reaches metafor results and is reported", {
  fixture <- binary_fixture()
  fixture$params$inference.method <- "knha"
  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "binary.random", params = fixture$params)
  )

  expect_identical(result$res$test, "knha")
  expect_identical(result[["Inference Method"]], "Knapp-Hartung")
  expect_true(any(grepl("Knapp-Hartung inference", result$References, fixed = TRUE)))
})

test_that("non-normal inference requires positive residual degrees of freedom", {
  expect_error(
    RCMetaR:::rcmetar.validate.inference.method(
      list(inference.method = "t"),
      k = 2,
      p = 2
    ),
    "requires positive residual degrees of freedom"
  )
})

test_that("reference normalization preserves declared order while removing repeats", {
  refs <- RCMetaR:::rcmetar.unique.references(c("method A", "method B", "method A", "method C"))

  expect_identical(refs, c("method A", "method B", "method C"))
})

test_that("single factor diagnostic meta-regression returns adjusted means", {
  fixture <- diagnostic_fixture("DOR")
  result <- rcmetar.run.analysis(
    fixture$data,
    list(version=1, method= "diagnostic.reitsma", params = fixture$params, workflow = "meta-regression")
  )

  expect_true(all(c("Summary", "res", "References") %in% names(result)))
  expect_true(all(c("Sensitivity coefficients", "Specificity coefficients") %in% names(result$Summary)))
})

test_that("Reitsma feasibility requires count-based diagnostic data", {
  entered.effects <- new(
    "DiagnosticData",
    y = c(qlogis(0.65), qlogis(0.80), qlogis(0.77), qlogis(0.71), qlogis(0.58)),
    SE = c(0.14, 0.18, 0.09, 0.26, 0.08),
    study.names = c("a", "b", "c", "d", "e")
  )
  count.data <- diagnostic_fixture("Sens")$data

  expect_false(diagnostic.reitsma.is.feasible(entered.effects, "Sens"))
  expect_true(diagnostic.reitsma.is.feasible(count.data, "Sens"))
})
