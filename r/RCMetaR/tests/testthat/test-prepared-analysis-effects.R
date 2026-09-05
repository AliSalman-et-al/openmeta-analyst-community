binary_preparation_fixture <- function() {
  new(
    "BinaryData",
    g1O1=c(0, 8, 3, 12), g1O2=c(20, 12, 17, 8),
    g2O1=c(5, 6, 4, 9), g2O2=c(15, 14, 16, 11),
    y=rep(99, 4), SE=rep(.001, 4),
    study.names=c("zero", "one", "two", "three"),
    years=as.integer(2011:2014),
    covariates=list(new("CovariateValues", cov.name="group",
                        cov.vals=c("A", "A", "B", "B"),
                        cov.type="factor", ref.var="A"))
  )
}

binary_preparation_params <- function(target) {
  list(measure="OR", adjust=.5, to=target, conf.level=95, digits=3,
       rm.method="REML", supress.output=TRUE, create.plot=FALSE,
       write.to.file=FALSE, cov_name="group", num.bootstrap.replicates=8,
       bootstrap.type="boot.ma", bootstrap.plot.path=tempfile(fileext=".png"),
       histogram.title="Bootstrap", histogram.xlab="Effect",
       fp_xticks="[default]", fp_plot_lb="[default]", fp_plot_ub="[default]",
       fp_xlabel="[default]", fp_col1_str="Study or Subgroup",
       fp_col2_str="[default]", fp_col3_str="[default]", fp_col4_str="Ev/Ctrl",
       fp_show_col1=TRUE, fp_show_col2=TRUE, fp_show_col3=TRUE, fp_show_col4=FALSE,
       fp_show_summary_line=TRUE, fp_outpath=file.path("r_tmp", paste0("prepared-", target, ".png")))
}

run_prepared_binary <- function(method, target, workflow="standard") {
  rcmetar.run.analysis(
    binary_preparation_fixture(),
    list(version=1, method=method, params=binary_preparation_params(target), workflow=workflow)
  )
}

test_that("the shared boundary reconstructs binary effects once", {
  data <- binary_preparation_fixture()
  params <- binary_preparation_params("only0")
  prepared <- rcmetar.prepare.analysis.data(data, params)
  result <- run_prepared_binary("binary.fixed.inv.var", "only0")
  expected <- metafor::rma.uni(yi=prepared@y, sei=prepared@SE, method="FE", level=95)

  expect_equal(result$input_data@y, prepared@y)
  expect_equal(result$res$b[[1]], expected$b[[1]], tolerance=1e-12)
})

test_that("binary correction targets alter fixed and random models", {
  fixed <- lapply(c("only0", "all", "if0all"), function(target)
    run_prepared_binary("binary.fixed.inv.var", target)$res$b[[1]])
  random <- lapply(c("only0", "all", "if0all"), function(target)
    run_prepared_binary("binary.random", target)$res$b[[1]])

  expect_gt(diff(range(unlist(fixed))), 1e-6)
  expect_gt(diff(range(unlist(random))), 1e-6)
})

test_that("Mantel-Haenszel uses the same corrected counts as displayed effects", {
  only0 <- run_prepared_binary("binary.fixed.mh", "only0")
  all <- run_prepared_binary("binary.fixed.mh", "all")
  any.zero <- run_prepared_binary("binary.fixed.mh", "if0all")

  expect_equal(only0$input_data@y,
               rcmetar.prepare.analysis.data(binary_preparation_fixture(),
                                             binary_preparation_params("only0"))@y)
  expect_gt(abs(only0$res$b[[1]] - all$res$b[[1]]), 1e-6)
  expect_equal(all$res$b[[1]], any.zero$res$b[[1]], tolerance=1e-12)
})

test_that("direct diagnostic reconstruction preserves entered effects", {
  raw <- new("DiagnosticData", TP=c(0, 8, 12), FN=c(10, 2, 4),
              TN=c(20, 18, 16), FP=c(2, 1, 3),
              y=rep(99, 3), SE=rep(.001, 3),
              study.names=c("zero", "one", "two"), years=as.integer(2011:2013))
  params <- list(measure="DOR", adjust=.5, to="only0", conf.level=95,
                 digits=3, rm.method="REML", supress.output=TRUE,
                 create.plot=FALSE, write.to.file=FALSE)
  prepared <- rcmetar.prepare.analysis.data(raw, params)
  expect_false(isTRUE(all.equal(prepared@y, raw@y)))

  entered <- new("DiagnosticData", y=c(.2, .3, .4), SE=c(.1, .2, .15),
                 study.names=c("a", "b", "c"), years=as.integer(2011:2013))
  entered.prepared <- rcmetar.prepare.analysis.data(entered, params)
  expect_identical(entered.prepared@y, entered@y)
  expect_identical(entered.prepared@SE, entered@SE)
})

test_that("single diagnostic execution uses reconstructed or entered DOR", {
  params <- list(measure="DOR", adjust=.5, to="only0", conf.level=95,
                 digits=3, rm.method="REML", supress.output=TRUE,
                 create.plot=FALSE, write.to.file=FALSE)
  raw <- new("DiagnosticData", TP=0, FN=10, TN=20, FP=2,
              y=99, SE=.001, study.names="zero", years=2011L)
  raw.result <- rcmetar.run.analysis(raw, list(version=1, method="diagnostic.fixed.inv.var", params=params))
  expected <- rcmetar.prepare.analysis.data(raw, params)
  expect_equal(raw.result$Summary$MAResults$b[[1]], expected@y[[1]], tolerance=1e-12)

  entered <- new("DiagnosticData", y=.7, SE=.2, study.names="entered", years=2011L)
  entered.result <- rcmetar.run.analysis(entered, list(version=1, method="diagnostic.fixed.inv.var", params=params))
  expect_equal(entered.result$Summary$MAResults$b[[1]], .7, tolerance=1e-12)
})

test_that("wrapped binary workflows consume the prepared base effects", {
  for (workflow in c("cumulative", "leave-one-out")) {
    only0 <- run_prepared_binary("binary.random", "only0", workflow)
    all <- run_prepared_binary("binary.random", "all", workflow)
    expect_false(identical(only0$res, all$res), info=workflow)
  }

  only0 <- rcmetar.prepare.analysis.data(binary_preparation_fixture(),
                                         binary_preparation_params("only0"))
  all <- rcmetar.prepare.analysis.data(binary_preparation_fixture(),
                                       binary_preparation_params("all"))
  only0.group <- RCMetaR:::get.subgroup.data.binary(only0, "A", c("A", "A", "B", "B"))
  all.group <- RCMetaR:::get.subgroup.data.binary(all, "A", c("A", "A", "B", "B"))
  expect_false(identical(only0.group@y, all.group@y))

  set.seed(42)
  only0 <- run_prepared_binary("binary.random", "only0", "bootstrap")
  set.seed(42)
  all <- run_prepared_binary("binary.random", "all", "bootstrap")
  expect_false(identical(only0$res$t, all$res$t))
})

test_that("Peto remains count-native and entered effect-only data stay unchanged", {
  native <- run_prepared_binary("binary.fixed.peto", "only0")
  expect_true(is.finite(native$res$b[[1]]))

  entered <- new("BinaryData", y=.2, SE=.1,
                 study.names="a", years=2011L)
  params <- binary_preparation_params("all")
  prepared <- rcmetar.prepare.analysis.data(entered, params)
  expect_identical(prepared@y, entered@y)
  expect_identical(prepared@SE, entered@SE)
  result <- rcmetar.run.analysis(entered, list(version=1, method="binary.fixed.peto", params=params))
  expect_equal(result$Summary$b[[1]], .2, tolerance=1e-12)
})

test_that("display correction labels map to the established correction targets", {
  data <- binary_preparation_fixture()
  old <- rcmetar.prepare.analysis.data(data, binary_preparation_params("if0all"))
  labeled.params <- binary_preparation_params("only0")
  labeled.params$correction.policy <- "All studies if any zero exists"
  labeled <- rcmetar.prepare.analysis.data(data, labeled.params)
  expect_equal(labeled@y, old@y, tolerance=1e-12)
})

test_that("one-arm raw preparation ignores absent group-two cells", {
  data <- new("BinaryData", g1O1=c(0, 2, 4), g1O2=c(10, 8, 6),
              y=rep(999, 3), SE=rep(999, 3),
              study.names=c("zero", "one", "two"), years=as.integer(2011:2013))
  params <- binary_preparation_params("only0")
  params$measure <- "PR"
  prepared <- rcmetar.prepare.analysis.data(data, params)
  expect_false(identical(prepared@y, data@y))
  corrected <- RCMetaR:::rcmetar.corrected.binary.counts(
    data, list(measure="PR", to="only0", adjust=.5)
  )
  expect_equal(corrected$a, c(.5, 2, 4))
  expect_equal(corrected$b, c(10.5, 8, 6))
  expect_length(corrected$c, 0)
  expect_length(corrected$d, 0)
})

test_that("truncated raw companions preserve entered continuous and diagnostic effects", {
  continuous <- new("ContinuousData", N1=c(20, 22, 24), mean1=c(1, 2), sd1=c(1, 1, 1),
                    N2=c(20, 22, 24), mean2=c(0, 1, 2), sd2=c(1, 1, 1),
                    y=c(7, 8, 9), SE=c(.1, .2, .3),
                    study.names=c("a", "b", "c"), years=as.integer(2011:2013))
  cont.params <- list(measure="MD", conf.level=95, rm.method="REML")
  prepared.continuous <- rcmetar.prepare.analysis.data(continuous, cont.params)
  expect_identical(prepared.continuous@y, continuous@y)
  expect_identical(prepared.continuous@SE, continuous@SE)

  diagnostic <- new("DiagnosticData", TP=c(1, 2, 3), FN=c(2, 3),
                    FP=c(1, 1, 1), TN=c(8, 7, 6),
                    y=c(7, 8, 9), SE=c(.1, .2, .3),
                    study.names=c("a", "b", "c"), years=as.integer(2011:2013))
  diag.params <- list(measure="DOR", conf.level=95, rm.method="REML")
  prepared.diagnostic <- rcmetar.prepare.analysis.data(diagnostic, diag.params)
  expect_identical(prepared.diagnostic@y, diagnostic@y)
  expect_identical(prepared.diagnostic@SE, diagnostic@SE)
})
