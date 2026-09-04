testthat::test_that("boundary Reitsma covariance remains display-safe", {
  testthat::expect_null(RCMetaR:::rcmetar.reitsma.covariance.to.specificity(NULL))
  one.by.one <- matrix(1, nrow=1, ncol=1)
  testthat::expect_identical(
    RCMetaR:::rcmetar.reitsma.covariance.to.specificity(one.by.one), one.by.one
  )
})

testthat::test_that("Reitsma ignores a generic non-Reitsma rm.method", {
  testthat::expect_identical(
    RCMetaR:::rcmetar.reitsma.estimator(list(rm.method="DL")),
    "reml"
  )
  testthat::expect_identical(
    RCMetaR:::rcmetar.reitsma.estimator(list(estimator="ML")),
    "ml"
  )
  testthat::expect_error(
    RCMetaR:::rcmetar.reitsma.estimator(list(estimator="DL")),
    "Reitsma estimator must be REML or ML"
  )
})

testthat::test_that("Reitsma validates and represents diagnostic counts", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  data <- methods::new("DiagnosticData",
    TP=c(19, 8, 41, 5, 45), FN=c(10, 2, 12, 2, 32),
    TN=c(81, 13, 49, 18, 165), FP=c(1, 9, 1, 1, 58),
    study.names=letters[1:5]
  )
  result <- RCMetaR:::diagnostic.reitsma(data, list(create.plot=FALSE, conf.level=90, digits=2))
  testthat::expect_named(result$Summary, c(
    "Clinical interpretation", "Summary operating point", "Sampling-based summary ratios", "SROC AUC",
    "Marginal prediction", "Between-study heterogeneity", "Diagnostic I-squared",
    "Model information"
  ))
  testthat::expect_match(result$Summary[["Clinical interpretation"]], "summary sensitivity")
  testthat::expect_match(result$Summary[["Clinical interpretation"]], "summary specificity")
  model.info <- result$Summary[["Model information"]]
  testthat::expect_equal(model.info$studies.used, 5L)
  testthat::expect_identical(model.info$package.version, "0.5.12")
  testthat::expect_true(is.finite(model.info$logLik))
  testthat::expect_identical(model.info$summary.seed, 380381L)
  testthat::expect_identical(model.info$summary.iterations, 1000000L)
  testthat::expect_identical(model.info$summary.warnings, character())
  testthat::expect_true(is.character(model.info$warnings))
  testthat::expect_false("References" %in% names(result$Summary))
  testthat::expect_null(result$Summary[["Marginal prediction"]]$geometry)
  testthat::expect_true(is.data.frame(result$Summary[["Diagnostic I-squared"]][["I-squared estimates"]]))
  testthat::expect_false(any(grepl("^V[0-9]+$", names(result$Summary[["Diagnostic I-squared"]][["I-squared estimates"]]))))
  testthat::expect_true(all(grepl("%$", result$Summary[["Diagnostic I-squared"]][["I-squared estimates"]][["I-squared (%)"]])))
  testthat::expect_true(all(grepl("\\.[0-9]{2}%$", result$Summary[["Summary operating point"]][["Summary sensitivity"]])))
  testthat::expect_identical(result$Summary[["SROC AUC"]][["full.FPR.bounds"]], c(.01, .99))
  testthat::expect_true(all(result$Summary[["SROC AUC"]][["partial.FPR.bounds"]] >= c(.01, 0)))
  testthat::expect_match(result$Summary[["SROC AUC"]][["note"]], "equivalent parameterizations")
  testthat::expect_true(all(c("Zhou-Dendukuri", "Holling unadjusted range", "Holling adjusted range") %in%
    names(result$Summary[["Diagnostic I-squared"]][["I-squared summary"]])))
  testthat::expect_length(result$Summary[["Diagnostic I-squared"]][["I-squared estimates"]][["Measure"]], 7)
  ratios <- result$Summary[["Sampling-based summary ratios"]]
  testthat::expect_identical(
    rownames(ratios),
    c("Positive likelihood ratio", "Negative likelihood ratio",
      "Inverse negative likelihood ratio", "Diagnostic odds ratio")
  )
  testthat::expect_identical(
    colnames(ratios),
    c("Mean", "Median", "Lower bound (90% interval)", "Upper bound (90% interval)")
  )
  testthat::expect_false(any(grepl("posLR|negLR|invnegLR|DOR", rownames(ratios))))
  testthat::expect_length(result$plot_names, 0)
  testthat::expect_length(result$plot_params_paths, 0)
  testthat::expect_length(result$plot_capabilities, 0)
  testthat::expect_identical(result$sections, list(list(
    id="diagnostic.reitsma.summary", kind="text", order=0L,
    title="Summary", source_key="Summary"
  )))
  testthat::expect_equal(RCMetaR:::rcmetar.reitsma.correction.control("Studies with any zero cell"), "single")
  testthat::expect_equal(RCMetaR:::rcmetar.reitsma.correction.control("All studies if any zero exists"), "all")
  testthat::expect_equal(RCMetaR:::rcmetar.reitsma.correction.control("None"), "none")
})

testthat::test_that("Reitsma SROC reports a semantic image section", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  data <- methods::new("DiagnosticData",
    TP=c(19, 8, 41, 5, 45), FN=c(10, 2, 12, 2, 32),
    TN=c(81, 13, 49, 18, 165), FP=c(1, 9, 1, 1, 58),
    study.names=letters[1:5]
  )
  output <- tempfile(fileext=".svg")
  result <- RCMetaR:::diagnostic.reitsma(data, list(
    create.plot=TRUE, fp_outpath=output, conf.level=95, digits=2
  ))
  testthat::expect_true(file.exists(output))
  testthat::expect_identical(result$image_order, "SROC")
  testthat::expect_identical(result$sections[[1]]$id, "diagnostic.reitsma.summary")
  testthat::expect_identical(result$sections[[2]], list(
    id="diagnostic.reitsma.sroc", kind="image", order=1L,
    title="SROC", source_key="SROC"
  ))
})

testthat::test_that("multiple diagnostic results retain editable Reitsma plot data", {
  library(RCMetaR)
  namespace <- asNamespace("RCMetaR")
  original <- get("diagnostic.reitsma", envir=namespace)
  replacement <- function(diagnostic.data, params) list(
    Summary=list(), References=character(), images=c(SROC="sroc.svg"),
    image_order="SROC", plot_names=c(SROC="sroc"),
    plot_params_paths=c(SROC="sroc-data"),
    plot_capabilities=list(SROC=RCMetaR:::.rcmetar.plot.descriptor.for.kind("sroc", TRUE)),
    sections=list(list(
      id="diagnostic.reitsma.sroc", kind="image", order=1L,
      title="SROC", source_key="SROC"
    ))
  )
  unlockBinding("diagnostic.reitsma", namespace)
  assign("diagnostic.reitsma", replacement, envir=namespace)
  on.exit({
    assign("diagnostic.reitsma", original, envir=namespace)
    lockBinding("diagnostic.reitsma", namespace)
  }, add=TRUE)
  data <- methods::new("DiagnosticData", study.names=letters[1:5])
  result <- RCMetaR:::multiple.diagnostic(
    c("diagnostic.reitsma"), list(list(create.plot=TRUE)), data
  )
  testthat::expect_identical(names(result$images), "SROC")
  testthat::expect_identical(names(result$plot_names), "SROC")
  testthat::expect_identical(names(result$plot_params_paths), "SROC")
  testthat::expect_identical(result$plot_params_paths[["SROC"]], "sroc-data")
  testthat::expect_identical(result$sections[[1]]$id, "diagnostic.reitsma.sroc")
})

testthat::test_that("plot capability attachment rejects editable plots without regeneration data", {
  library(RCMetaR)
  result <- list(
    images=c(SROC="sroc.svg"),
    plot_capabilities=list(SROC=RCMetaR:::.rcmetar.plot.descriptor.for.kind("sroc", TRUE))
  )
  testthat::expect_error(
    RCMetaR:::.rcmetar.attach.plot.capabilities(result, list(workflow="standard", method="diagnostic.reitsma")),
    "Editable plot capability descriptor missing plot data.*SROC"
  )
})

testthat::test_that("cumulative diagnostic aggregation retains forest regeneration data", {
  library(RCMetaR)
  namespace <- asNamespace("RCMetaR")
  original <- get("cum.ma.diagnostic", envir=namespace)
  replacement <- function(fname, diagnostic.data, params) list(
    images=c("Cumulative Forest Plot"="cumulative.svg"),
    plot_params_paths=c("Cumulative Forest Plot"="cumulative-data"),
    References=character()
  )
  unlockBinding("cum.ma.diagnostic", namespace)
  assign("cum.ma.diagnostic", replacement, envir=namespace)
  on.exit({
    assign("cum.ma.diagnostic", original, envir=namespace)
    lockBinding("cum.ma.diagnostic", namespace)
  }, add=TRUE)
  data <- methods::new("DiagnosticData", y=seq(.1, .5, length.out=5), SE=rep(.1, 5), study.names=letters[1:5])
  result <- RCMetaR:::multiple.cum.ma.diagnostic(
    c("diagnostic.fixed.inv.var"), list(list(measure="Sens")), data
  )
  testthat::expect_identical(names(result$plot_params_paths), "Sens Forest Plot")
  testthat::expect_identical(result$plot_params_paths[["Sens Forest Plot"]], "cumulative-data")
})

testthat::test_that("legacy joint methods fail with removal guidance", {
  library(RCMetaR)
  data <- methods::new("DiagnosticData",
    TP=rep(1, 5), FN=rep(1, 5), TN=rep(1, 5), FP=rep(1, 5), study.names=letters[1:5]
  )
  error <- tryCatch(rcmetar.validate.analysis.request(data, method="diagnostic.hsroc", params=list(measure="Sens")), error=function(e) e)
  testthat::expect_s3_class(error, "simpleError")
  testthat::expect_match(conditionMessage(error), "diagnostic.reitsma")
})

testthat::test_that("Reitsma uses mada numeric estimates and restores RNG state", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  counts <- data.frame(
    TP=c(19, 8, 41, 5, 45), FN=c(10, 2, 12, 2, 32),
    TN=c(81, 13, 49, 18, 165), FP=c(1, 9, 1, 1, 58)
  )
  data <- methods::new("DiagnosticData", TP=counts$TP, FN=counts$FN,
    TN=counts$TN, FP=counts$FP, study.names=letters[1:5])
  fit <- mada::reitsma(counts, correction=.5, correction.control="all", method="reml")
  set.seed(12345)
  before <- .Random.seed
  wrapped <- RCMetaR:::diagnostic.reitsma(data, list(create.plot=FALSE))
  testthat::expect_identical(.Random.seed, before)
  point <- wrapped$Summary[["Summary operating point"]]
  testthat::expect_named(point, c("Summary sensitivity", "Summary specificity", "False-positive rate"))
  testthat::expect_equal(names(point[["Summary sensitivity"]]), c("Estimate", "Lower bound (95% CI)", "Upper bound (95% CI)"))
  testthat::expect_match(point[["Summary sensitivity"]][["Estimate"]], "%", fixed=TRUE)
  prediction <- wrapped$Summary[["Marginal prediction"]][["intervals"]]
  testthat::expect_true(all(c("Sensitivity", "Specificity", "False-positive rate") %in% names(prediction)))
  testthat::expect_equal(names(prediction[["Sensitivity"]]), c("Estimate", "Lower bound (95% PI)", "Upper bound (95% PI)"))
  testthat::expect_match(prediction[["Specificity"]][["Estimate"]], "%", fixed=TRUE)
  raw.point <- RCMetaR:::rcmetar.reitsma.summary.point(fit, .95)
  raw.prediction <- RCMetaR:::rcmetar.reitsma.marginal.prediction(fit, .95)
  testthat::expect_true(raw.prediction$specificity[["lower"]] <= raw.prediction$specificity[["estimate"]])
  testthat::expect_true(raw.prediction$specificity[["estimate"]] <= raw.prediction$specificity[["upper"]])
  testthat::expect_equal(unname(raw.point$sensitivity[["estimate"]]),
                         unname(mada::talpha(fit$alphasens)$linkinv(fit$coefficients["(Intercept)", "tsens"])), tolerance=1e-12)
  one <- RCMetaR:::rcmetar.reitsma.summary.points(fit, .95, 380381L)
  two <- RCMetaR:::rcmetar.reitsma.summary.points(fit, .95, 380381L)
  testthat::expect_identical(one, two)
})

testthat::test_that("Reitsma model information captures summary warnings", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  namespace <- asNamespace("RCMetaR")
  original <- get("rcmetar.reitsma.summary.points", envir=namespace)
  unlockBinding("rcmetar.reitsma.summary.points", namespace)
  assign("rcmetar.reitsma.summary.points", function(fit, level, seed, iterations=1000000L) {
    warning("controlled SummaryPts warning")
    original(fit, level, seed, iterations=1000L)
  }, envir=namespace)
  on.exit({
    assign("rcmetar.reitsma.summary.points", original, envir=namespace)
    lockBinding("rcmetar.reitsma.summary.points", namespace)
  }, add=TRUE)
  data <- methods::new("DiagnosticData",
    TP=c(19, 8, 41, 5, 45), FN=c(10, 2, 12, 2, 32),
    TN=c(81, 13, 49, 18, 165), FP=c(1, 9, 1, 1, 58),
    study.names=letters[1:5]
  )
  result <- RCMetaR:::diagnostic.reitsma(data, list(create.plot=FALSE))
  model.info <- result$Summary[["Model information"]]
  testthat::expect_true(any(grepl("controlled SummaryPts warning", model.info$summary.warnings, fixed=TRUE)))
  testthat::expect_true(any(grepl("controlled SummaryPts warning", model.info$warnings, fixed=TRUE)))
})

testthat::test_that("Reitsma rejects entered effects, incomplete counts, and boundary None correction", {
  library(RCMetaR)
  entered <- methods::new("DiagnosticData", y=rep(.7, 5), SE=rep(.1, 5), study.names=letters[1:5])
  testthat::expect_error(RCMetaR:::rcmetar.reitsma.validate.counts(entered), "complete TP/FN/FP/TN")
  incomplete <- methods::new("DiagnosticData", TP=rep(1, 5), FN=rep(1, 5), TN=rep(1, 5), study.names=letters[1:5])
  testthat::expect_error(RCMetaR:::rcmetar.reitsma.validate.counts(incomplete), "complete TP/FN/FP/TN")
  boundary <- methods::new("DiagnosticData", TP=c(0,1,2,3,4), FN=rep(1,5), TN=rep(4,5), FP=rep(1,5), study.names=letters[1:5])
  testthat::expect_error(RCMetaR:::diagnostic.reitsma(boundary, list(correction.policy="None", create.plot=FALSE)), "boundary")
})

testthat::test_that("Boundary covariance preserves valid summaries and omits undefined SROC output", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  data <- methods::new("DiagnosticData", TP=rep(9, 5), FN=rep(1, 5), TN=rep(9, 5), FP=rep(1, 5), study.names=letters[1:5])
  fit <- mada::reitsma(data.frame(TP=data@TP, FN=data@FN, FP=data@FP, TN=data@TN), correction=.5, correction.control="all")
  fit$Psi[,] <- 0
  plot.data <- RCMetaR:::rcmetar.reitsma.plot.data(fit, data, .95)
  testthat::expect_true(is.finite(RCMetaR:::rcmetar.reitsma.summary.point(fit, .95)$sensitivity[["estimate"]]))
  testthat::expect_true(is.matrix(plot.data$curve))
  testthat::expect_null(plot.data$auc)
  testthat::expect_true(any(grepl("unavailable|undefined", plot.data$warnings, ignore.case=TRUE)))
})

testthat::test_that("Reitsma meta-regression reports coding, odds ratios, and separate forests", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  data <- methods::new("DiagnosticData", TP=c(19,8,41,5,45,8), FN=c(10,2,12,2,32,2),
    TN=c(81,13,49,18,165,32), FP=c(1,9,1,1,58,6), study.names=letters[1:6],
    covariates=list(methods::new("CovariateValues", cov.name="quality",
      cov.vals=c("A","A","B","B","A","B"), cov.type="factor", ref.var="A")))
  result <- RCMetaR:::diagnostic.reitsma.meta.regression(data,
    list(create.plot=FALSE, rm.method="DL", correction.policy="All studies if any zero exists", adjust=.5, conf.level=95))
  testthat::expect_identical(names(result$Summary)[1], "Clinical interpretation")
  testthat::expect_match(result$Summary[["Clinical interpretation"]], "jointly models sensitivity and false-positive rate")
  testthat::expect_match(result$Summary[["Clinical interpretation"]], "Reference rows equal 1")
  testthat::expect_true(all(c("Sensitivity coefficients", "Specificity coefficients", "Moderator coding", "Moderator block tests") %in% names(result$Summary)))
  residual.i2 <- result$Summary[["Residual diagnostic I-squared"]][["I-squared estimates"]]
  testthat::expect_true(is.data.frame(residual.i2))
  testthat::expect_identical(colnames(residual.i2), c("Measure", "I-squared (%)"))
  testthat::expect_true(all(grepl("%$", residual.i2[["I-squared (%)"]])))
  testthat::expect_identical(names(result$Summary)[length(result$Summary)], "Model information")
  testthat::expect_equal(result$Summary[["Model information"]]$studies.used, 6L)
  testthat::expect_identical(result$Summary[["Model information"]]$package.version, "0.5.12")
  testthat::expect_identical(result$sections, list(list(
    id="diagnostic.reitsma.meta.regression.summary", kind="text", order=0L,
    title="Summary", source_key="Summary"
  )))
  prepared <- RCMetaR:::.rcmetar.reitsma.prepare.meta.regression(data)
  plots <- RCMetaR:::.rcmetar.reitsma.meta.regression.plots(
    data, result$res,
    list(create.plot=TRUE, fp_outpath=tempfile(fileext=".svg")),
    prepared$coding,
    result$Summary[["Sensitivity coefficients"]],
    result$Summary[["Specificity coefficients"]]
  )
  testthat::expect_identical(
    vapply(plots$sections, function(section) section$id, character(1)),
    c("diagnostic.reitsma.sensitivity.coefficients",
      "diagnostic.reitsma.specificity.coefficients")
  )
  testthat::expect_identical(
    vapply(plots$sections, function(section) section$title, character(1)),
    c("Sensitivity Moderator Coefficients", "Specificity Moderator Coefficients")
  )
  testthat::expect_true(all(c("Odds Ratio", "Odds Ratio lower", "Odds Ratio upper") %in% colnames(result$Summary[["Specificity coefficients"]])))
  testthat::expect_false(any(grepl("Intercept", rownames(result$Summary[["Sensitivity coefficients"]]), fixed=TRUE)))
  reference <- result$Summary[["Sensitivity coefficients"]][grep("reference", rownames(result$Summary[["Sensitivity coefficients"]]), fixed=TRUE), "Odds Ratio"]
  testthat::expect_equal(unname(reference), 1)
})

testthat::test_that("Reitsma meta-regression retains warnings from every fit", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  n <- 6L
  data <- methods::new("DiagnosticData", TP=c(19, 8, 41, 5, 45, 8),
    FN=c(10, 2, 12, 2, 32, 2), TN=c(81, 13, 49, 18, 165, 32),
    FP=c(1, 9, 1, 1, 58, 6), study.names=letters[seq_len(n)],
    covariates=list(methods::new("CovariateValues", cov.name="quality",
      cov.vals=c("A", "A", "B", "B", "A", "B"), cov.type="factor", ref.var="A")))

  namespace <- asNamespace("mada")
  original <- get("reitsma", envir=namespace)
  unlockBinding("reitsma", namespace)
  assign("reitsma", function(...) {
    warning("controlled meta-regression fit warning")
    original(...)
  }, envir=namespace)
  on.exit({
    assign("reitsma", original, envir=namespace)
    lockBinding("reitsma", namespace)
  }, add=TRUE)

  result <- RCMetaR:::diagnostic.reitsma.meta.regression(data,
    list(create.plot=FALSE, estimator="REML", correction.policy="All studies if any zero exists",
      adjust=.5, conf.level=95))
  warnings <- result$Summary[["Model information"]]$warnings
  testthat::expect_true(any(grepl("Full model fit: controlled meta-regression fit warning", warnings, fixed=TRUE)))
  testthat::expect_true(any(grepl("Full ML likelihood-ratio fit: controlled meta-regression fit warning", warnings, fixed=TRUE)))
  testthat::expect_true(any(grepl("Intercept-only likelihood-ratio fit: controlled meta-regression fit warning", warnings, fixed=TRUE)))
  testthat::expect_true(any(grepl("Reduced model for moderator 'quality': controlled meta-regression fit warning", warnings, fixed=TRUE)))
})

testthat::test_that("Reitsma meta-regression supports continuous and additive moderators", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  n <- 8L
  data <- methods::new("DiagnosticData", TP=c(19, 8, 41, 5, 45, 8, 21, 33),
    FN=c(10, 2, 12, 2, 32, 2, 9, 11), TN=c(81, 13, 49, 18, 165, 32, 72, 91),
    FP=c(1, 9, 1, 1, 58, 6, 5, 7), study.names=letters[seq_len(n)],
    covariates=list(
      methods::new("CovariateValues", cov.name="quality", cov.vals=c("A", "A", "B", "B", "A", "B", "A", "B"), cov.type="factor", ref.var="A"),
      methods::new("CovariateValues", cov.name="threshold", cov.vals=seq_len(n), cov.type="continuous", ref.var="")
    ))
  result <- RCMetaR:::diagnostic.reitsma.meta.regression(data,
    list(create.plot=FALSE, estimator="REML", correction.policy="All studies if any zero exists", adjust=.5, conf.level=95))
  testthat::expect_true(all(c("quality", "threshold") %in% names(result$Summary[["Moderator coding"]])))
  testthat::expect_equal(result$Summary[["Moderator coding"]][["quality"]]$reference, "A")
  testthat::expect_true(is.finite(result$Summary[["Overall ML likelihood-ratio test"]]$p.value))
})

testthat::test_that("Reitsma meta-regression quotes arbitrary moderator names in full and reduced models", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  n <- 8L
  data <- methods::new("DiagnosticData", TP=c(19, 8, 41, 5, 45, 8, 21, 33),
    FN=c(10, 2, 12, 2, 32, 2, 9, 11), TN=c(81, 13, 49, 18, 165, 32, 72, 91),
    FP=c(1, 9, 1, 1, 58, 6, 5, 7), study.names=letters[seq_len(n)],
    covariates=list(
      methods::new("CovariateValues", cov.name="Study quality", cov.vals=c("A", "A", "B", "B", "A", "B", "A", "B"), cov.type="factor", ref.var="A"),
      methods::new("CovariateValues", cov.name="a+b", cov.vals=seq_len(n), cov.type="continuous", ref.var="")
    ))
  result <- RCMetaR:::diagnostic.reitsma.meta.regression(data,
    list(create.plot=FALSE, estimator="REML", correction.policy="All studies if any zero exists", adjust=.5, conf.level=95))
  testthat::expect_true(any(grepl("`Study quality`", result$Summary[["Model information"]]$formula, fixed=TRUE)))
  testthat::expect_true(any(grepl("`a+b`", result$Summary[["Model information"]]$formula, fixed=TRUE)))
  testthat::expect_identical(names(result$Summary[["Moderator block tests"]]), c("Study quality", "a+b"))
  for (side in c("Sensitivity coefficients", "Specificity coefficients")) {
    labels <- rownames(result$Summary[[side]])
    testthat::expect_true(any(grepl("Study quality", labels, fixed=TRUE)))
    testthat::expect_true(any(grepl("a+b", labels, fixed=TRUE)))
    testthat::expect_false(any(grepl("Study.quality", labels, fixed=TRUE)))
    testthat::expect_false(any(grepl("a.b", labels, fixed=TRUE)))
  }
})

testthat::test_that("Reitsma coefficient regeneration restores categorical reference rows without refitting", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  counts <- data.frame(TP=c(19, 8, 41, 5, 45, 8), FN=c(10, 2, 12, 2, 32, 2),
    TN=c(81, 13, 49, 18, 165, 32), FP=c(1, 9, 1, 1, 58, 6))
  fit.data <- transform(counts, quality=factor(c("A", "A", "B", "B", "A", "B"), levels=c("A", "B")))
  fit <- mada::reitsma(fit.data, formula=RCMetaR:::rcmetar.reitsma.formula("quality"),
    correction=.5, correction.control="all", method="reml")
  diagnostic.data <- methods::new("DiagnosticData", TP=counts$TP, FN=counts$FN, TN=counts$TN, FP=counts$FP,
    study.names=letters[seq_len(nrow(counts))])
  bundle <- RCMetaR:::rcmetar.regenerate.plot.data(diagnostic.data, fit, list(
    conf.level=95, reitsma.coefficient.scale="Sensitivity",
    reitsma.moderator.coding=list(quality=list(type="factor", levels=c("A", "B"), reference="A"))))
  testthat::expect_true(any(grepl("quality = A (reference)", bundle$labels, fixed=TRUE)))
})

testthat::test_that("saved Reitsma geometry regenerates without calling mada extractors", {
  library(RCMetaR)
  geometry <- list(
    kind="sroc", fpr=c(.1, .2), sensitivity=c(.8, .7), sample.size=c(20, 30),
    study.names=c("a", "b"), curve=cbind(c(.1, .2), c(.8, .7)),
    confidence.region=NULL, prediction.region=NULL, auc=NULL,
    summary.point=list(sensitivity=c(estimate=.8), specificity=c(estimate=.9)),
    style=list(xlabel="False Positive Rate", ylabel="Sensitivity")
  )
  params <- list(reitsma.sroc.geometry=geometry, fp_xlabel="Edited FPR")
  regenerated <- RCMetaR:::rcmetar.regenerate.plot.data(NULL, NULL, params)
  testthat::expect_identical(regenerated$curve, geometry$curve)
  testthat::expect_identical(regenerated$style$xlabel, "Edited FPR")
})

testthat::test_that("Reitsma legend stores sample-size markers and omits unavailable lines", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  style <- list(show.legend=TRUE, show.confidence=TRUE, show.prediction=TRUE,
    show.marker.legend=TRUE, marker.area="sample-size", point.size.multiplier=1, point.pch=21)
  marker.only <- RCMetaR:::rcmetar.reitsma.legend.spec(style, NULL, NULL, NULL, c(10, 20))
  testthat::expect_identical(marker.only$labels, c("Study sample size (n=10)", "Study sample size (n=20)"))
  testthat::expect_equal(length(marker.only$labels), length(marker.only$col))
  testthat::expect_equal(length(marker.only$labels), length(marker.only$pch))
  testthat::expect_equal(length(marker.only$labels), length(marker.only$pt.cex))
  hidden <- style
  hidden$show.marker.legend <- FALSE
  testthat::expect_length(
    RCMetaR:::rcmetar.reitsma.legend.spec(hidden, NULL, NULL, NULL, c(10, 20))$labels,
    0
  )
  uniform <- style
  uniform$marker.area <- "uniform"
  testthat::expect_length(
    RCMetaR:::rcmetar.reitsma.legend.spec(uniform, NULL, NULL, NULL, c(10, 20))$labels,
    0
  )
  counts <- data.frame(TP=c(19, 8, 41, 5, 45), FN=c(10, 2, 12, 2, 32),
    TN=c(81, 13, 49, 18, 165), FP=c(1, 9, 1, 1, 58))
  fit <- mada::reitsma(counts, correction=.5, correction.control="all", method="reml")
  diagnostic.data <- methods::new("DiagnosticData", TP=counts$TP, FN=counts$FN,
    TN=counts$TN, FP=counts$FP, study.names=letters[seq_len(nrow(counts))])
  plot.data <- RCMetaR:::rcmetar.reitsma.plot.data(fit, diagnostic.data, .90,
    params=list(fp_point_area_by_sample_size=TRUE, fp_show_legend=TRUE,
      fp_accent_color="#123456", fp_plot_lb=.1, fp_plot_ub=.9,
      fp_xticks=c(.1, .5, .9), fp_sroc_plot_lb=.2, fp_sroc_plot_ub=.8,
      fp_sroc_yticks=c(.2, .5, .8)))
  testthat::expect_true(any(plot.data$legend$labels == "SROC"))
  testthat::expect_true(any(grepl("Study sample size", plot.data$legend$labels, fixed=TRUE)))
  testthat::expect_equal(length(plot.data$legend$labels), length(plot.data$legend$col))
  testthat::expect_identical(plot.data$style$accent.color, "#123456")
  testthat::expect_identical(plot.data$style$plot.lb, "0.1")
  testthat::expect_identical(plot.data$style$plot.ub, "0.9")
  testthat::expect_equal(plot.data$style$xticks, c(.1, .5, .9))
  testthat::expect_identical(plot.data$style$y.plot.lb, "0.2")
  testthat::expect_identical(plot.data$style$y.plot.ub, "0.8")
  testthat::expect_equal(plot.data$style$yticks, c(.2, .5, .8))
})

testthat::test_that("Reitsma meta-regression rejects missing and rank-deficient moderators", {
  library(RCMetaR)
  counts <- list(TP=rep(2, 6), FN=rep(3, 6), TN=rep(4, 6), FP=rep(1, 6))
  missing <- methods::new("DiagnosticData", TP=counts$TP, FN=counts$FN, TN=counts$TN, FP=counts$FP,
    study.names=letters[1:6], covariates=list(methods::new("CovariateValues", cov.name="quality",
      cov.vals=c("A", "A", "B", "B", "A", NA_character_), cov.type="factor", ref.var="A")))
  testthat::expect_error(RCMetaR:::diagnostic.reitsma.meta.regression(missing, list(create.plot=FALSE)), "Missing moderator")
  collapsed <- methods::new("DiagnosticData", TP=counts$TP, FN=counts$FN, TN=counts$TN, FP=counts$FP,
    study.names=letters[1:6], covariates=list(methods::new("CovariateValues", cov.name="quality",
      cov.vals=factor(rep("A", 6), levels=c("A", "B")), cov.type="factor", ref.var="A")))
  testthat::expect_error(
    RCMetaR:::diagnostic.reitsma.meta.regression(collapsed, list(create.plot=FALSE)),
    "Categorical moderator 'quality' has fewer than two observed levels after missing-value exclusions"
  )
  duplicate <- methods::new("DiagnosticData", TP=counts$TP, FN=counts$FN, TN=counts$TN, FP=counts$FP,
    study.names=letters[1:6], covariates=list(
      methods::new("CovariateValues", cov.name="quality", cov.vals=c("A", "A", "B", "B", "A", "B"), cov.type="factor", ref.var="A"),
      methods::new("CovariateValues", cov.name="quality_duplicate", cov.vals=c("A", "A", "B", "B", "A", "B"), cov.type="factor", ref.var="A")
    ))
  testthat::expect_error(RCMetaR:::diagnostic.reitsma.meta.regression(duplicate, list(create.plot=FALSE)), "rank deficient")
})

testthat::test_that("Reitsma warning capture preserves partial output and omits unavailable AUC", {
  library(RCMetaR)
  testthat::skip_if_not_installed("mada")
  testthat::skip_if_not(as.character(utils::packageVersion("mada")) == "0.5.12")
  captured <- RCMetaR:::rcmetar.reitsma.capture.warnings({
    warning("controlled warning")
    42
  })
  testthat::expect_equal(captured$value, 42)
  testthat::expect_identical(captured$warnings, "controlled warning")
  failed <- RCMetaR:::rcmetar.reitsma.capture.warnings(stop("controlled failure"))
  testthat::expect_null(failed$value)
  testthat::expect_identical(failed$error, "controlled failure")
  testthat::expect_error(
    RCMetaR:::rcmetar.reitsma.require.value(
      list(value=NULL, error="mada optimizer exploded"),
      "Full ML likelihood-ratio fit"
    ),
    "Full ML likelihood-ratio fit failed: mada optimizer exploded"
  )

  namespace <- asNamespace("mada")
  original <- get("AUC", envir=namespace)
  unlockBinding("AUC", namespace)
  assign("AUC", function(...) {
    warning("controlled AUC warning")
    stop("controlled AUC failure")
  }, envir=namespace)
  on.exit({
    assign("AUC", original, envir=namespace)
    lockBinding("AUC", namespace)
  }, add=TRUE)
  data <- methods::new("DiagnosticData",
    TP=c(19, 8, 41, 5, 45), FN=c(10, 2, 12, 2, 32),
    TN=c(81, 13, 49, 18, 165), FP=c(1, 9, 1, 1, 58),
    study.names=letters[1:5]
  )
  result <- RCMetaR:::diagnostic.reitsma(data, list(create.plot=FALSE))
  testthat::expect_false("SROC AUC" %in% names(result$Summary))
  testthat::expect_true(any(grepl("SROC AUC unavailable: controlled AUC failure",
    result$Summary[["Model information"]]$warnings, fixed=TRUE)))
})
