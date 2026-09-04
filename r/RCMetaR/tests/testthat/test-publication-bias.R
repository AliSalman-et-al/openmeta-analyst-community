test_that("publication-bias display helpers emit trimmed, readable values", {
  expect_identical(
    vapply(c(0, 1.2, 10000, NA_real_), RCMetaR:::.small.study.number, character(1)),
    c("0", "1.200", "10000", "Not available")
  )
  expect_identical(
    vapply(c(0.015, 0.0004, NA_real_), RCMetaR:::.small.study.p.value, character(1)),
    c("0.015", "< 0.001", "not available")
  )
  expect_identical(RCMetaR:::.small.study.exact.number(0.015), "0.015")
  expect_identical(RCMetaR:::.small.study.integer(10), "10")
  expect_identical(RCMetaR:::.small.study.text(NA_character_), "Not available")
})

test_that("small-study effects public entry requires exact request version", {
  expect_error(
    RCMetaR:::rcmetar.run.small.study.effects(NULL, list(data.type="continuous", metric="MD")),
    "Unsupported small-study effects request version"
  )
  expect_error(
    RCMetaR:::rcmetar.run.small.study.effects(NULL, list(version=2L, data.type="continuous", metric="MD")),
    "Unsupported small-study effects request version"
  )
  expect_error(
    RCMetaR:::rcmetar.run.small.study.effects(NULL, list(version=1, data.type="continuous", metric="MD")),
    "Unsupported small-study effects request version"
  )
})

test_that("publication-bias confidence level controls intervals and labels", {
  expect_equal(RCMetaR:::.small.study.meta.level(90), .9)
  expect_error(
    RCMetaR:::.small.study.confidence.level(list(conf.level=numeric())),
    "finite percentage"
  )
  expect_identical(RCMetaR:::.small.study.confidence.label(90, short=TRUE), "90% CI")
  expect_identical(RCMetaR:::.small.study.confidence.label(90), "90% confidence interval")

  test <- list(method="classical-egger", role="primary", usable.studies=10,
               p.value=.2, statistic=1, coefficient=1, standard.error=.1,
               df=9, intercept=1, se.intercept=.1,
               model="multiplicative Egger regression")
  rendered <- RCMetaR:::.small.study.tests.text(list(test), confidence.level=90)
  expect_match(rendered, "90% CI", fixed=TRUE)
  expect_false(grepl("95% CI", rendered, fixed=TRUE))
  pooled <- list(TE.common=0.2, lower.common=-0.1, upper.common=.5,
                 TE.random=.3, lower.random=-.2, upper.random=.8)
  pooled.text <- RCMetaR:::.small.study.pooled.text(pooled, "MD", 90)
  expect_match(pooled.text, "90% confidence interval", fixed=TRUE)
  expect_false(grepl("95% confidence interval", pooled.text, fixed=TRUE))

  extrapolated <- RCMetaR:::.small.study.extrapolation(
    list(`classical-egger`=test), list(extrapolation=TRUE, conf.level=90), "MD"
  )
  expected.lower <- 1 - stats::qt(.95, 9) * .1
  expect_match(extrapolated$Extrapolation, "90% CI", fixed=TRUE)
  expect_match(extrapolated$Extrapolation, RCMetaR:::.small.study.number(expected.lower), fixed=TRUE)
  expect_false(grepl("95% CI", extrapolated$Extrapolation, fixed=TRUE))
})

test_that("publication-bias text sections do not expose missing-value artifacts", {
  test <- list(
    method = "classical-egger", role = "primary", usable.studies = NA_real_,
    p.value = NA_real_, statistic = NA_real_, coefficient = NA_real_,
    model = "multiplicative Egger regression", package = "meta",
    package.version = "8.5-0", predictor = "SE", weighting = "inverse variance",
    inference = "t-based test", df = NA_real_, call = "meta::metabias(...)"
  )
  rendered <- paste(
    RCMetaR:::.small.study.tests.text(list(test)),
    RCMetaR:::.small.study.method.details(list(test)),
    sep = "\n"
  )
  expect_match(rendered, "Studies: Not available", fixed = TRUE)
  expect_match(rendered, "Exact p-value: Not available", fixed = TRUE)
  expect_false(grepl("(^|[[:space:]])(NA|NaN|Inf|NULL)([[:space:]]|$)", rendered))
  expect_false(grepl("\\[1\\]", rendered))
})

test_that("generic entered effects produce one ordered ordinary funnel result", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    y=c(-0.2, 0.1, 0.3, -0.1),
    SE=c(0.1, 0.2, 0.15, 0.3),
    study.names=c("one", "two", "three", "four"),
    years=as.integer(2011:2014)
  )
  device.before <- grDevices::dev.cur()
  result <- rcmetar.run.small.study.effects(
    data,
    list(version=1L, data.type="continuous", metric="MD", funnels="ordinary",
         tests=character(), conf.level=90)
  )

  expect_equal(names(result)[1:6], c(
    "Warning", "Data and eligibility", "Tests", "Pooled comparison",
    "References", "Failures"
  ))
  expect_match(result$Warning, "No single result proves or rules out publication bias")
  expect_match(result$`Data and eligibility`, "Studies analyzed: 4")
  expect_match(result$`Pooled comparison`, "90% confidence interval", fixed=TRUE)
  expect_match(result$`Methods not applicable`, "Classical Egger test")
  expect_match(result$`Method details`, "No formal method details are available.")
  expect_equal(result$eligibility$`data.type`, "continuous")
  expect_equal(result$eligibility$metric, "MD")
  expect_false(isTRUE(result$eligibility$methods[[1]]$available))
  expect_match(result$eligibility$methods[[1]]$reason, "below 10")
  expect_identical(names(result$images), "Ordinary Funnel Plot")
  expect_true(file.exists(result$images[[1]]))
  expect_gt(file.info(result$images[[1]])$size, 0)
  expect_identical(result$plot_capabilities[[1]]$plot_kind, "funnel")
  expect_identical(result$plot_capabilities[[1]]$regenerator, "funnel")
  expect_identical(result$sections[[1]]$id, "small-study.warning")
  expect_identical(result$sections[[1]]$title, "Warning")
  expect_identical(result$sections[[1]]$source_key, "small-study.warning")
  expect_identical(result$sections[[1]]$value_key, "Warning")
  expect_true("Warning" %in% names(result))
  expect_false("small-study.warning" %in% names(result))
  image.sections <- Filter(function(section) identical(section$kind, "image"), result$sections)
  expect_identical(image.sections[[1]]$id, "small-study.funnel.1")
  expect_identical(image.sections[[1]]$title, "Ordinary Funnel Plot")
  expect_identical(grDevices::dev.cur(), device.before)
  expect_true(any(grepl("Funnel plot axis choice", result$References, fixed=TRUE)))
  expect_true(any(grepl("Viechtbauer", result$References, fixed=TRUE)))
  expect_false(any(grepl("Egger regression test", result$References, fixed=TRUE)))
})


test_that("optional asymmetry failures remain beside a successful funnel", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    y=c(-0.2, 0.1, 0.3, -0.1),
    SE=c(0.1, 0.2, 0.15, 0.3),
    study.names=c("one", "two", "three", "four"),
    years=as.integer(2011:2014)
  )
  result <- rcmetar.run.small.study.effects(
    data,
    list(version=1L, data.type="continuous", metric="MD", funnels="ordinary",
         tests=c("classical-egger", "invalid-method"), conf.level=95)
  )

  expect_true(file.exists(result$images[[1]]))
  expect_match(result$Failures, "invalid-method")
})


test_that("one failed funnel does not discard successful plots", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    y=c(-0.2, 0.1, 0.3, -0.1),
    SE=c(0.1, 0.2, 0.15, 0.3),
    study.names=c("one", "two", "three", "four"),
    years=as.integer(2011:2014)
  )
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels=c("ordinary", "contour"),
    tests=character(), `funnel.point.color`=c("black", "not-a-color")
  ))

  expect_identical(names(result$images), "Ordinary Funnel Plot")
  expect_match(result$Failures, "Contour Funnel Plot")
  expect_false(grepl("trim-and-fill", result$Failures, fixed=TRUE))
  expect_false(any(grepl("Contour-enhanced funnel plots", result$References, fixed=TRUE)))
})


test_that("ordinary and contour funnels persist their prepared geometry", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    y=c(-0.2, 0.1, 0.3, -0.1),
    SE=c(0.1, 0.2, 0.15, 0.3),
    study.names=c("one", "two", "three", "four"),
    years=as.integer(2011:2014)
  )
  device.before <- grDevices::dev.cur()
  result <- rcmetar.run.small.study.effects(
    data,
    list(version=1L, data.type="continuous", metric="MD",
         funnels=c("ordinary", "contour"), tests=character(), conf.level=95,
         `funnel.contour.levels`="90,95,99",
         `funnel.pooled.overlay.visible`=TRUE,
         `funnel.point.size`=1.5,
         `funnel.point.symbol`=18,
         `funnel.point.color`="#0072B2",
         `funnel.reference.color`="#D55E00",
         `funnel.region.color`="#D7E9F4",
         `funnel.background.color`="#FAFAFA",
         `funnel.label.policy`="all",
         `funnel.sampling.conf.level`=90,
         `funnel.include.tau2`=TRUE,
         `funnel.reference.visible`=FALSE)
  )

  expect_true(all(file.info(unlist(result$images))$size > 0))
  expect_identical(result$plot_capabilities[["Ordinary Funnel Plot"]]$plot_kind, "funnel")
  expect_identical(result$plot_capabilities[["Contour Funnel Plot"]]$plot_kind, "contour_funnel")
  params.path <- result$plot_params_paths[["Contour Funnel Plot"]]
  load(paste0(params.path, ".params"))
  expect_equal(params$`funnel.contour.levels`, "90,95,99")
  expect_true(isTRUE(params$`funnel.pooled.overlay.visible`))
  expect_equal(params$`funnel.point.size`, 1.5)
  expect_equal(params$`funnel.point.symbol`, 18)
  expect_identical(params$`funnel.point.color`, "#0072B2")
  expect_identical(params$`funnel.reference.color`, "#D55E00")
  expect_identical(params$`funnel.region.color`, "#D7E9F4")
  expect_identical(params$`funnel.background.color`, "#FAFAFA")
  expect_identical(params$`funnel.label.policy`, "all")
  expect_equal(params$`funnel.sampling.conf.level`, 90)
  expect_true(isTRUE(params$`funnel.include.tau2`))
  expect_false(isTRUE(params$`funnel.reference.visible`))
  expect_equal(params$`prepared.effects`, data@y)
  expect_equal(params$`prepared.standard.errors`, data@SE)

  for (title in c("Ordinary Funnel Plot", "Contour Funnel Plot")) {
    path <- result$plot_params_paths[[title]]
    load(paste0(path, ".params"))
    load(paste0(path, ".data"))
    load(paste0(path, ".res"))
    regenerated <- tempfile(fileext=".png")
    expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, regenerated)))
    expect_gt(file.info(regenerated)$size, 0)
    expect_identical(
      unname(tools::md5sum(regenerated)),
      unname(tools::md5sum(result$images[[title]]))
    )
    expect_identical(grDevices::dev.cur(), device.before)
  }
  path <- result$plot_params_paths[["Ordinary Funnel Plot"]]
  load(paste0(path, ".params")); load(paste0(path, ".data")); load(paste0(path, ".res"))
  for (extension in c("pdf", "svg", "tiff")) {
    exported <- tempfile(fileext=paste0(".", extension))
    expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, exported)))
    expect_gt(file.info(exported)$size, 0)
  }

  for (label.policy in c("none", "outside-pseudo-confidence-region", "all")) {
    labeled <- rcmetar.run.small.study.effects(
      data,
      list(version=1L, data.type="continuous", metric="MD", funnels="ordinary",
           tests=character(), conf.level=95,
           `funnel.label.policy`=label.policy)
    )
    expect_true(file.exists(labeled$images[[1]]))
    expect_gt(file.info(labeled$images[[1]])$size, 0)
  }
})

test_that("references follow the methods and plots that produced the result", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    y=seq(-.3, .4, length.out=10),
    SE=seq(.1, .2, length.out=10),
    study.names=paste0("s", 1:10),
    years=as.integer(2011:2020)
  )
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels=c("ordinary", "contour"),
    tests=c("classical-egger", "mixed-effects-egger", "begg-mazumdar")
  ))

  expect_match(result$`Method details`, "Package:")
  expect_match(result$`Method details`, "Predictor:")
  expect_match(result$`Method details`, "Weighting:")
  expect_match(result$`Method details`, "Exact p-value:")
  expect_match(result$`Method details`, "Call:")
  expect_true(any(grepl("Egger, M.", result$References, fixed=TRUE)))
  expect_true(any(grepl("Sterne, J. A. C., & Egger", result$References, fixed=TRUE)))
  expect_true(any(grepl("Begg-Mazumdar rank test", result$References, fixed=TRUE)))
  expect_true(any(grepl("Contour-enhanced funnel plots", result$References, fixed=TRUE)))
  expect_false(any(grepl("Harbord test", result$References, fixed=TRUE)))
  expect_false(any(grepl("Cochrane meta package", result$References, fixed=TRUE)))
})

test_that("ordinary funnel sampling-region visibility is persisted for regeneration", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new("ContinuousData", y=c(-0.2, 0.1, 0.3, -0.1),
              SE=c(0.1, 0.2, 0.15, 0.3),
              study.names=c("one", "two", "three", "four"),
              years=as.integer(2011:2014))
  visible <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary", tests=character(),
    `funnel.sampling.region.visible`=TRUE))
  hidden <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary", tests=character(),
    `funnel.sampling.region.visible`=FALSE))
  visible.path <- visible$plot_params_paths[["Ordinary Funnel Plot"]]
  hidden.path <- hidden$plot_params_paths[["Ordinary Funnel Plot"]]
  load(paste0(visible.path, ".params"))
  expect_true(isTRUE(params$`funnel.sampling.region.visible`))
  load(paste0(hidden.path, ".params"))
  expect_false(isTRUE(params$`funnel.sampling.region.visible`))
  load(paste0(hidden.path, ".data")); load(paste0(hidden.path, ".res"));
  regenerated <- tempfile(fileext=".png")
  expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, regenerated)))
  expect_gt(file.info(regenerated)$size, 0)
  expect_identical(
    unname(tools::md5sum(regenerated)),
    unname(tools::md5sum(hidden$images[["Ordinary Funnel Plot"]]))
  )
})

test_that("funnel regeneration uses the persisted funnel index for vector settings", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new("ContinuousData", y=c(-0.2, 0.1, 0.3, -0.1),
              SE=c(0.1, 0.2, 0.15, 0.3),
              study.names=c("one", "two", "three", "four"),
              years=as.integer(2011:2014))
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels=c("ordinary", "contour"),
    tests=character(), conf.level=95,
    `funnel.label.policy`=c("none", "all"),
    `funnel.contour.levels`=c("", "80,90"),
    `funnel.sampling.region.visible`=c(TRUE, FALSE)))
  path <- result$plot_params_paths[["Contour Funnel Plot"]]
  load(paste0(path, ".params"))
  expect_identical(params$`funnel.index`, 2L)
  expect_identical(params$`funnel.contour.levels`[[2L]], "80,90")
  expect_identical(params$`funnel.label.policy`[[2L]], "all")
  load(paste0(path, ".data")); load(paste0(path, ".res"))
  regenerated <- tempfile(fileext=".png")
  expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, regenerated)))
  expect_gt(file.info(regenerated)$size, 0)
  expect_identical(
    unname(tools::md5sum(regenerated)),
    unname(tools::md5sum(result$images[["Contour Funnel Plot"]]))
  )
})

test_that("generic tests use distinct package-native Egger and Begg procedures", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    y=c(-.20, .10, .30, -.10, .20, .40, -.30, .05, .11, -.02),
    SE=c(.10, .20, .15, .30, .12, .22, .17, .27, .14, .19),
    study.names=paste0("study-", 1:10), years=as.integer(2011:2020)
  )
  result <- rcmetar.run.small.study.effects(
    data,
    list(version=1L, data.type="continuous", metric="MD", funnels="ordinary",
         tests=c("classical-egger", "mixed-effects-egger", "begg-mazumdar"),
         conf.level=95)
  )
  expect_setequal(names(result$tests.data), c("classical-egger", "mixed-effects-egger", "begg-mazumdar"))
  expect_identical(result$tests.data$`classical-egger`$package, "meta")
  expect_identical(result$tests.data$`classical-egger`$package.version, "8.5-0")
  expect_match(result$tests.data$`classical-egger`$call, "method.bias='Egger'")
  expect_identical(result$tests.data$`mixed-effects-egger`$package, "metafor")
  expect_match(result$tests.data$`mixed-effects-egger`$call, "regtest")
  expect_identical(result$tests.data$`mixed-effects-egger`$model, "REML mixed-effects meta-regression")
  expect_identical(result$tests.data$`mixed-effects-egger`$weighting, "inverse-variance weights with REML heterogeneity")
  expect_identical(result$tests.data$`mixed-effects-egger`$inference, "z test from metafor::regtest")
  expect_identical(result$tests.data$`begg-mazumdar`$role, "exploratory")
  expect_identical(result$tests.data$`begg-mazumdar`$package.version, "8.5-0")
  expect_identical(result$tests.data$`begg-mazumdar`$inference, "z test from Kendall rank correlation")
  expect_match(result$Tests, "Classical Egger test")
  expect_match(result$Tests, "Mixed-effects Egger test")
  expect_match(result$Tests, "Begg-Mazumdar test")
  expect_match(result$Tests, "Studies:")
  expect_match(result$Tests, "Result:")
  expect_match(result$Tests, "95% CI")
  expect_match(result$`Method details`, "Weighting: inverse-variance weights with REML heterogeneity", fixed=TRUE)
  expect_match(result$`Method details`, "Inference: z test from metafor::regtest", fixed=TRUE)
  expect_match(result$`Method details`, "Weighting: not applicable (Kendall rank-based test)", fixed=TRUE)
  expect_match(result$`Method details`, "Inference: z test from Kendall rank correlation", fixed=TRUE)
  expect_match(result$`Pooled comparison`, "Common effect", ignore.case=TRUE)
  expect_match(result$`Pooled comparison`, "Random effects (REML)", fixed=TRUE)
  expect_match(result$`Pooled comparison`, "not estimates corrected", ignore.case=TRUE)
})

test_that("generic guardrails expose hard minimum and automatic k guard", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  make_data <- function(k, se=seq(.1, .1 + .01 * (k - 1), length.out=k)) new(
    "ContinuousData", y=seq(-.2, .2, length.out=k), SE=se,
    study.names=paste0("study-", seq_len(k)), years=as.integer(2011:(2010+k))
  )
  hard <- rcmetar.run.small.study.effects(make_data(2), list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary",
    tests=c("classical-egger"), conf.level=95))
  expect_false(hard$eligibility$methods[[1]]$available)
  expect_match(hard$eligibility$methods[[1]]$reason, "fewer than 3")
  expect_match(hard$Warning, "No formal asymmetry test was run", fixed=TRUE)
  expect_match(hard$Warning, "at least 3 usable studies", fixed=TRUE)
  expect_match(hard$Warning, "2 usable studies were available", fixed=TRUE)

  disabled <- rcmetar.run.small.study.effects(make_data(4), list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary",
    tests=c("classical-egger"), conf.level=95))
  expect_false(disabled$eligibility$methods[[1]]$available)
  expect_match(disabled$eligibility$methods[[1]]$reason, "below 10")
  expect_match(disabled$Failures, "below 10")
  expect_match(disabled$Warning, "No formal asymmetry test was run", fixed=TRUE)
  expect_match(disabled$Warning, "at least 10 usable studies", fixed=TRUE)
  expect_match(disabled$Warning, "4 usable studies were available", fixed=TRUE)
  expect_equal(sum(gregexpr("Observed standard-error range", disabled$Warning, fixed=TRUE)[[1L]] > 0), 1L)
  expect_length(disabled$eligibility$`standard.error.range`, 2)
  expect_true(any(grepl("standard-error range", disabled$eligibility$warnings, ignore.case=TRUE)))
  expect_true(any(grepl("analysis summary", disabled$eligibility$warnings, ignore.case=TRUE)))
  expect_match(disabled$`Data and eligibility`, "Observed standard-error range: \\[0\\.1, 0\\.13\\]", fixed=FALSE)
  expect_match(disabled$Warning, "the exact range is reported in the analysis summary", fixed=TRUE)

  automatic <- rcmetar.run.small.study.effects(make_data(4), list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary",
    tests=c("classical-egger"), conf.level=95))
  expect_false(automatic$eligibility$methods[[1]]$available)
  expect_false("classical-egger" %in% names(automatic$tests.data))

  constant <- rcmetar.run.small.study.effects(make_data(4, rep(.2, 4)), list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary",
    tests=c("classical-egger"), conf.level=95))
  expect_false(constant$eligibility$methods[[1]]$available)
  expect_match(constant$eligibility$methods[[1]]$reason, "variance is zero")
})

test_that("binary OR routes Harbord at low tau and Rucker AS+RE above the rule of thumb", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  make_data <- function(a, b, c, d) new(
    "BinaryData", g1O1=a, g1O2=b, g2O1=c, g2O2=d,
    y=rep(999, length(a)), SE=rep(999, length(a)),
    study.names=paste0("study-", seq_along(a)), years=as.integer(2011:(2010+length(a)))
  )
  low <- make_data(
    c(2,4,7,1,5,3,8,6,9,2), c(8,16,13,19,15,7,12,14,11,18),
    c(1,3,4,2,3,2,5,4,6,1), c(9,17,16,18,17,8,15,16,14,19)
  )
  low.result <- rcmetar.run.small.study.effects(low, list(
    version=1L, data.type="binary", metric="OR", funnels="ordinary",
    tests=c("harbord", "rucker-as-re", "peters"),
    `correction.policy`="Studies with any zero cell",
    extrapolation=TRUE
  ))
  expect_equal(low.result$eligibility$`package.versions`[["meta"]], "8.5-0")
  expect_true(low.result$eligibility$methods[[1]]$available)
  expect_identical(low.result$eligibility$methods[[1]]$role, "primary")
  expect_true(low.result$eligibility$methods[[2]]$available)
  expect_identical(low.result$eligibility$methods[[2]]$role, "sensitivity")
  expect_identical(low.result$eligibility$methods[[2]]$reason, "")
  expect_identical(low.result$tests.data$harbord$package, "meta")
  expect_match(low.result$tests.data$harbord$call, "method.bias='Harbord'")
  expect_false(grepl("correction.policy", low.result$tests.data$harbord$call, fixed=TRUE))
  expect_false(grepl("prepared.OR.model\\$TE <-", low.result$tests.data$harbord$call))
  expect_match(low.result$tests.data$harbord$predictor, "1/sqrt\\(V\\)")
  expect_match(low.result$tests.data$harbord$weighting, "variance V")
  low.params.path <- low.result$plot_params_paths[[1L]]
  load(paste0(low.params.path, ".params"))
  expect_equal(low.result$tests.data$peters$prepared.effects, params$`prepared.effects`)
  expect_equal(low.result$tests.data$peters$prepared.standard.errors, params$`prepared.standard.errors`)
  expect_match(low.result$tests.data$peters$call, "prepared.OR.model\\$TE <- prepared.effects")
  expect_match(low.result$tests.data$peters$call, "prepared.OR.model\\$seTE <- prepared.standard.errors")
  expect_equal(low.result$tests.data$harbord$routing.effects, params$`prepared.effects`)
  expect_equal(low.result$tests.data$harbord$routing.standard.errors, params$`prepared.standard.errors`)
  routing <- RCMetaR:::.small.study.prepared.model(
    params$`prepared.effects`, params$`prepared.standard.errors`, low@study.names, "OR"
  )
  expect_equal(routing$TE, params$`prepared.effects`)
  expect_equal(routing$seTE, params$`prepared.standard.errors`)
  expect_equal(low.result$eligibility$`reml.tau2`, routing$tau2)
  expect_match(low.result$`Data and eligibility`, "Heterogeneity (REML tau-squared)", fixed=TRUE)
  expect_match(low.result$Extrapolation, "Peters test")

  high <- make_data(
    c(1,18,2,17,1,19,3,16,2,18), c(9,2,28,3,39,1,17,4,28,2),
    c(18,2,17,3,19,1,16,4,17,2), c(2,8,3,27,1,19,4,16,3,28)
  )
  high.result <- rcmetar.run.small.study.effects(high, list(
    version=1L, data.type="binary", metric="OR", funnels="ordinary",
    tests=c("harbord", "rucker-as-re", "peters")))
  expect_false(high.result$eligibility$methods[[1]]$available)
  expect_match(high.result$eligibility$methods[[1]]$reason, "above 0.1")
  expect_true(high.result$eligibility$methods[[2]]$available)
  expect_identical(high.result$eligibility$methods[[2]]$role, "primary")
  expect_identical(high.result$eligibility$methods[[2]]$reason, "")
  expect_match(high.result$`Data and eligibility`, "Primary test: R\u00fccker AS+RE test", fixed=TRUE)
  expect_identical(high.result$tests.data$`rucker-as-re`$package, "meta")
  expect_match(high.result$tests.data$`rucker-as-re`$call, "sm='ASD'")
  expect_match(high.result$tests.data$`rucker-as-re`$call, "method.bias='Thompson'")
  expect_match(high.result$tests.data$peters$predictor, "n.e\\+n.c")
  expect_match(high.result$tests.data$peters$weighting, "Peters seTE")
  expect_false(grepl("incr|method.incr", high.result$tests.data$`rucker-as-re`$call))
  expect_identical(high.result$tests.data$peters$role, "sensitivity")
})

test_that("binary OR corrections preserve policy labels and exclude native double-zero studies", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "BinaryData",
    g1O1=c(0, 2, 4, 5, 6, 7, 8, 3, 4, 5),
    g1O2=c(10, 8, 6, 5, 4, 3, 2, 7, 6, 5),
    g2O1=c(0, 1, 3, 4, 5, 6, 7, 2, 3, 4),
    g2O2=c(10, 9, 7, 6, 5, 4, 3, 8, 7, 6),
    y=rep(123, 10), SE=rep(456, 10), study.names=paste0("study-", 1:10), years=as.integer(2011:2020)
  )
  for (policy in c("Studies with any zero cell", "All studies", "All studies if any zero exists")) {
    result <- rcmetar.run.small.study.effects(data, list(
      version=1L, data.type="binary", metric="OR", funnels="ordinary", tests=character(),
      `correction.policy`=policy
    ))
    expect_match(result$`Data and eligibility`, "Continuity correction:")
    expect_match(result$`Data and eligibility`, policy, fixed=TRUE)
    params.path <- result$plot_params_paths[[1L]]
    load(paste0(params.path, ".params"))
    expect_identical(params$`correction.policy`, policy)
    expect_equal(params$`prepared.effects`[[1L]], NA_real_)
    expect_equal(params$`prepared.standard.errors`[[1L]], NA_real_)
    expect_false(isTRUE(params$`prepared.effects`[[2L]] == 123))
    expect_equal(result$eligibility$methods[[2L]]$`usable.studies`, sum(is.finite(params$`prepared.effects`)))
  }
  incomplete <- data
  incomplete@g2O2 <- incomplete@g2O2[-10]
  no.primary <- rcmetar.run.small.study.effects(incomplete, list(
    version=1L, data.type="binary", metric="OR", funnels="ordinary", tests=character()
  ))
  expect_true(grepl("complete two-arm raw counts", paste(vapply(no.primary$eligibility$methods, `[[`, character(1), "reason"), collapse=" ")))
  expect_match(no.primary$`Data and eligibility`, "Primary test: None available")
  prepared <- RCMetaR:::.small.study.reconstruct(data, "OR", list(`correction.policy`="Studies with any zero cell"))
  shared.keep <- which(is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0)
  asd <- RCMetaR:::.small.study.asd.model(data, list(), shared.keep)
  expect_equal(asd$k, length(shared.keep))
})

test_that("independent two-group SMD uses native Pustejovsky-Rodgers", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new(
    "ContinuousData",
    N1=c(20,24,30,36,40,45,50,60,70,80), mean1=c(1.1,1.4,1.2,1.8,1.5,1.9,1.7,2.0,1.6,2.1), sd1=rep(1,10),
    N2=c(22,28,34,38,44,48,56,64,76,88), mean2=c(.8,1.0,.9,1.1,1.0,1.2,1.1,1.3,1.2,1.4), sd2=rep(1,10),
    y=rep(999,10), SE=rep(999,10), study.names=paste0("s",1:10), years=as.integer(2011:2020)
  )
  automatic <- rcmetar.run.small.study.effects(data, list(version=1L, data.type="continuous", metric="SMD", funnels="ordinary", tests=character()))
  expect_true(automatic$eligibility$methods[[1]]$available)
  expect_true("pustejovsky-rodgers" %in% names(automatic$tests.data))
  selected <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="SMD", funnels="ordinary", tests=c("pustejovsky-rodgers")))
  expect_true(selected$eligibility$methods[[1]]$available)
  expect_identical(selected$eligibility$methods[[1]]$role, "primary")
  expect_identical(selected$tests.data$`pustejovsky-rodgers`$package.version, "8.5-0")
  expect_match(selected$tests.data$`pustejovsky-rodgers`$call, "method.bias='Pustejovsky'")
  expect_match(selected$tests.data$`pustejovsky-rodgers`$predictor, "sqrt")
  expect_match(selected$tests.data$`pustejovsky-rodgers`$weighting, "inverse")
  expect_equal(selected$tests.data$`pustejovsky-rodgers`$usable.studies, 10)

  missing <- data
  missing@N2 <- missing@N2[-10]
  missing.result <- rcmetar.run.small.study.effects(missing, list(
    version=1L, data.type="continuous", metric="SMD", funnels="ordinary", tests=character()))
  expect_false(missing.result$eligibility$methods[[1]]$available)
  expect_match(missing.result$eligibility$methods[[1]]$reason, "sample sizes")
  expect_match(missing.result$`Data and eligibility`, "Primary test: None available")
})

test_that("ordinary SMD Egger is a separate non-primary artifact", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new("ContinuousData", y=seq(-.2,.2,length.out=10), SE=seq(.1,.2,length.out=10),
              study.names=paste0("s",1:10), years=as.integer(2011:2020))
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="SMD", funnels="ordinary", tests=c("classical-egger")))
  expect_true(result$eligibility$methods[[2]]$available)
  expect_identical(result$eligibility$methods[[2]]$role, "sensitivity")
  expect_match(result$eligibility$methods[[2]]$reason, "")
  expect_match(result$Warning, "standardized mean differences", ignore.case=TRUE)
  expect_match(result$Tests, "Classical Egger test")
})

test_that("RR, RD, and one-arm proportion remain descriptive without automatic tests", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  binary <- new("BinaryData", g1O1=c(2,4,6,8,10,12,14,16,18,20), g1O2=c(18,16,14,12,10,8,6,4,2,1),
                g2O1=c(1,3,5,7,9,11,13,15,17,19), g2O2=c(19,17,15,13,11,9,7,5,3,2),
                y=rep(999,10), SE=rep(999,10), study.names=paste0("s",1:10), years=as.integer(2011:2020))
  for (metric in c("RR", "RD")) {
    result <- rcmetar.run.small.study.effects(binary, list(version=1L, data.type="binary", metric=metric, funnels="ordinary", tests=character()))
    expect_match(result$`Data and eligibility`, "Primary test: None available")
    expect_true(all(vapply(result$eligibility$methods, function(x) !isTRUE(x$available), logical(1))))
    expect_match(paste(vapply(result$eligibility$methods, `[[`, character(1), "reason"), collapse=" "), "No automatic primary")
  }
  one.arm <- binary
  one.arm@g2O1 <- numeric(); one.arm@g2O2 <- numeric()
  one.arm@y <- seq(.1,.5,length.out=10); one.arm@SE <- seq(.05,.15,length.out=10)
  proportion <- rcmetar.run.small.study.effects(one.arm, list(version=1L, data.type="binary", metric="PR", funnels="ordinary", tests=character()))
  expect_match(proportion$`Data and eligibility`, "Primary test: None available")
  expect_match(paste(proportion$eligibility$warnings, collapse=" "), "one-arm|effect-SE", ignore.case=TRUE)
  expect_false(any(grepl("Peters", vapply(proportion$eligibility$methods, `[[`, character(1), "method"), fixed=TRUE)))
})

test_that("trim-and-fill uses native L0/R0 controls and persists augmented plots", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new("ContinuousData", y=c(-.8, -.6, -.4, -.2, -.1, .1, .2, .3, .4, 1.5),
              SE=c(.10, .11, .12, .13, .14, .15, .16, .17, .18, .19),
              study.names=paste0("s", 1:10), years=as.integer(2011:2020))
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels=c("ordinary", "contour"), tests=character(),
    `trim.and.fill`=TRUE, `trim.and.fill.estimator`="L0",
    `trim.and.fill.side`="auto", `trim.and.fill.model`="random",
    `funnel.reference.visible`=c(TRUE, FALSE),
    `funnel.pooled.overlay.visible`=c(FALSE, TRUE),
    `funnel.sampling.region.visible`=c(FALSE, TRUE),
    `funnel.include.tau2`=c(TRUE, FALSE)
  ))
  expect_match(result$`Trim-and-fill`, "L0")
  expect_match(result$`Trim-and-fill`, "Random effects (REML)", fixed=TRUE)
  expect_false(grepl("Call:", result$`Trim-and-fill`, fixed=TRUE))
  expect_identical(result$`Trim-and-fill data`$estimator, "L0")
  expect_identical(result$`Trim-and-fill data`$side.rule, "automatic side")
  expect_identical(result$`Trim-and-fill data`$package.version, "8.5-0")
  expect_match(result$`Trim-and-fill data`$scenarios[[1]]$call, "meta::trimfill", fixed=TRUE)
  expect_true(length(result$`Trim-and-fill data`$scenarios[[1]]$augmented.effects) >= 10)
  expect_true(any(grepl("Trim-and-fill", names(result$images))))
  expect_true(all(file.exists(unlist(result$images[grep("Trim-and-fill", names(result$images))]))))
  path <- result$plot_params_paths[[grep("Trim-and-fill", names(result$plot_params_paths))[1L]]]
  load(paste0(path, ".params"))
  expect_true(length(params$`prepared.effects`) >= 10)
  expect_identical(params$`trim.and.fill.estimator`, "L0")
  expect_identical(params$`funnel.index`, 1L)
  load(paste0(path, ".data"))
  load(paste0(path, ".res"))
  regenerated <- tempfile(fileext=".png")
  expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, regenerated)))
  expect_gt(file.info(regenerated)$size, 0)
  trimfill.title <- grep("Trim-and-fill", names(result$images), value=TRUE)[[1L]]
  expect_identical(
    unname(tools::md5sum(regenerated)),
    unname(tools::md5sum(result$images[[trimfill.title]]))
  )

  bilateral <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="SMD", funnels="ordinary", tests=character(),
    `trim.and.fill`=TRUE, `trim.and.fill.estimator`="R0",
    `trim.and.fill.side`="auto", `trim.and.fill.model`="common"
  ))
  expect_true(all(c("Trim-and-fill left", "Trim-and-fill right") %in% names(bilateral$`Trim-and-fill data`$scenarios)))
  expect_match(bilateral$`Trim-and-fill left`, "R0")
  expect_match(bilateral$`Trim-and-fill right`, "Common effect", fixed=TRUE)
})

test_that("infinite-precision sensitivity reports only supported successful tests", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new("ContinuousData", y=seq(-.3, .4, length.out=10), SE=seq(.1, .2, length.out=10),
              study.names=paste0("s", 1:10), years=as.integer(2011:2020))
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary",
    tests=c("classical-egger", "mixed-effects-egger"),
    extrapolation=TRUE
  ))
  expect_match(result$Extrapolation, "infinite precision", ignore.case=TRUE)
  expect_match(result$Extrapolation, "Classical Egger test", fixed=TRUE)
  expect_match(result$Extrapolation, "Mixed-effects Egger test", fixed=TRUE)
  expect_identical(result$tests.data$`mixed-effects-egger`$package, "metafor")
  expect_false(grepl("Call:", result$Extrapolation, fixed=TRUE))
  expect_false(grepl("more valid", result$Extrapolation, ignore.case=TRUE))

  short.data <- data
  short.data@y <- short.data@y[1:4]
  short.data@SE <- short.data@SE[1:4]
  short.data@study.names <- short.data@study.names[1:4]
  short.data@years <- short.data@years[1:4]
  short <- rcmetar.run.small.study.effects(short.data, list(
    version=1L, data.type="continuous", metric="MD", funnels="ordinary",
    tests=c("classical-egger"),
    `extrapolation`=TRUE
  ))
  expect_match(short$Extrapolation, "at least 10 usable studies")
})

test_that("diagnostic Deeks uses corrected DOR and effective-sample-size geometry", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  data <- new("DiagnosticData",
    TP=c(0, 8, 12, 5, 9, 14, 6, 11, 7, 13),
    FN=c(10, 2, 4, 5, 3, 6, 4, 5, 3, 7),
    FP=c(2, 1, 3, 4, 2, 5, 3, 2, 4, 1),
    TN=c(20, 18, 16, 15, 19, 14, 17, 18, 16, 19),
    y=rep(999, 10), SE=rep(.001, 10), study.names=paste0("d", 1:10), years=as.integer(2011:2020))
  # Diagnostic configuration selects only the Deeks plot and test.
  result <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks",
    tests=character()
  ))
  expect_true(result$eligibility$methods[[1]]$available)
  expect_identical(result$tests.data$deeks$method, "Deeks test (meta implementation)")
  expect_identical(result$tests.data$deeks$package.version, "8.5-0")
  expect_match(result$tests.data$deeks$call, "method.bias='Deeks'")
  expect_match(result$tests.data$deeks$predictor, "4\\*n.e\\*n.c")
  expect_match(result$tests.data$deeks$weighting, "ESS")
  expect_equal(result$tests.data$deeks$effective.sample.size[[1L]], 4 * 10 * 22 / 32, tolerance=1e-12)
  expect_match(result$`Data and eligibility`, "All studies if any zero exists")
  expect_match(result$eligibility$warnings, "Observed Deeks ESS predictor range")
  expect_false("Pooled comparison" %in% names(result))
  expect_false("Trim-and-fill" %in% names(result))
  expect_false("Extrapolation" %in% names(result))
  expect_true("Deeks Effective-Sample-Size Funnel Plot" %in% names(result$images))
  path <- result$plot_params_paths[["Deeks Effective-Sample-Size Funnel Plot"]]
  load(paste0(path, ".params"))
  expect_identical(params$`funnel.xlab`, "1/sqrt(ESS)")
  expect_identical(params$`funnel.ylab`, "Log diagnostic odds ratio")
  expect_equal(params$deeks.predictor, 1 / sqrt(params$deeks.ess))
  load(paste0(path, ".data"))
  load(paste0(path, ".res"))
  regenerated <- tempfile(fileext=".png")
  expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, regenerated)))
  expect_gt(file.info(regenerated)$size, 0)
  expect_identical(
    unname(tools::md5sum(regenerated)),
    unname(tools::md5sum(result$images[["Deeks Effective-Sample-Size Funnel Plot"]]))
  )
  params$`funnel.xlab` <- "Edited ESS axis"
  params$`funnel.ylab` <- "Edited log DOR axis"
  edited <- tempfile(fileext=".svg")
  expect_true(file.exists(rcmetar.regenerate.small.study.funnel(om.data, res, params, edited)))
  expect_gt(file.info(edited)$size, 0)
  custom <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=character(),

    `funnel.xlab`="Edited ESS axis", `funnel.ylab`="Edited log DOR axis"
  ))
  custom.path <- custom$plot_params_paths[["Deeks Effective-Sample-Size Funnel Plot"]]
  load(paste0(custom.path, ".params"))
  expect_identical(params$`funnel.xlab`, "Edited ESS axis")
  expect_identical(params$`funnel.ylab`, "Edited log DOR axis")
  alternative <- rcmetar.run.small.study.effects(data, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=c("deeks"),
    correction.policy="Studies with any zero cell"
  ))
  expect_match(alternative$`Data and eligibility`, "Studies with any zero cell", fixed=TRUE)
  expect_false(identical(result$tests.data$deeks$prepared.effects, alternative$tests.data$deeks$prepared.effects))

  small <- data
  for (field in c("TP", "FN", "FP", "TN", "y", "SE", "study.names", "years")) {
    methods::slot(small, field) <- methods::slot(small, field)[1:4]
  }
  disabled <- rcmetar.run.small.study.effects(small, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=character()
  ))
  expect_match(disabled$eligibility$methods[[1]]$reason, "below 10")
  automatic <- rcmetar.run.small.study.effects(small, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=c("deeks")))
  expect_false(automatic$eligibility$methods[[1]]$available)
  expect_false("deeks" %in% names(automatic$tests.data))
  hard <- small
  for (field in c("TP", "FN", "FP", "TN", "y", "SE", "study.names", "years")) {
    methods::slot(hard, field) <- methods::slot(hard, field)[1:2]
  }
  hard.result <- rcmetar.run.small.study.effects(hard, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=character()
  ))
  expect_match(hard.result$eligibility$methods[[1]]$reason, "fewer than 3")
})

test_that("diagnostic Deeks requires complete counts", {
  testthat::skip_if_not_installed("meta")
  testthat::skip_if_not_installed("metafor")
  entered <- new("DiagnosticData", y=seq(.2, .8, length.out=10), SE=seq(.1, .2, length.out=10),
                 study.names=paste0("e", 1:10), years=as.integer(2011:2020))
  no.counts <- rcmetar.run.small.study.effects(entered, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=c("deeks")))
  expect_false(no.counts$eligibility$methods[[1]]$available)
  expect_match(no.counts$eligibility$methods[[1]]$reason, "TP/FN/FP/TN")
  expect_match(no.counts$`Data and eligibility`, "Primary test: None available")
  expect_false(any(grepl("Deeks", no.counts$References, fixed=TRUE)))

  incomplete <- new("DiagnosticData", TP=1:9, FN=rep(5, 9), FP=rep(2, 9), TN=rep(8, 9),
                    y=rep(99, 10), SE=rep(.1, 10), study.names=paste0("i", 1:10), years=as.integer(2011:2020))
  incomplete.result <- rcmetar.run.small.study.effects(incomplete, list(
    version=1L, data.type="diagnostic", metric="DOR", funnels="deeks", tests=character()))
  expect_false(incomplete.result$eligibility$methods[[1]]$available)
  expect_match(incomplete.result$eligibility$methods[[1]]$reason, "complete TP/FN/FP/TN")
})
