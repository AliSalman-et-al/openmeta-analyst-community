test_that("comprehensive visual QA accounts for every user-visible plot family", {
  script <- system.file("qa", "render_plot_visual_qa.R", package="RCMetaR")
  if (!nzchar(script)) {
    repo.root <- normalizePath(file.path(testthat::test_path(), "..", "..", "..", ".."), winslash = "/")
    script <- file.path(repo.root, "r", "RCMetaR", "inst", "qa", "render_plot_visual_qa.R")
  }
  expect_true(file.exists(script))
  qa <- new.env(parent = globalenv())
  sys.source(script, envir = qa)

  inventory <- qa$qa_visual_coverage_inventory()
  expect_setequal(
    inventory$family,
    c(
      "standard_forest",
      "cumulative_forest",
      "leave_one_out_forest",
      "subgroup_forest",
      "regression",
      "coefficient_forest",
      "bootstrap_histogram",
      "roc",
      "sroc"
    )
  )
  expect_true(all(inventory$status %in% c("covered", "excluded")))
  expect_true(all(nzchar(inventory$reason[inventory$status == "excluded"])))
  expect_true(all(nzchar(inventory$evidence[inventory$status == "excluded"])))
  expect_true(all(inventory$status[match(c("coefficient_forest", "sroc"), inventory$family)] == "covered"))
  expect_true(all(inventory$harness[match(c("coefficient_forest", "sroc"), inventory$family)] == "reitsma"))
  expect_setequal(unique(inventory$plot_kind), names(.rcmetar.plot.kind.capabilities()))

  covered <- inventory$family[inventory$status == "covered"]
  expect_silent(qa$qa_validate_visual_coverage(inventory, covered))
  expect_error(
    qa$qa_validate_visual_coverage(inventory, setdiff(covered, "regression")),
    "missing covered plot families: regression"
  )
  expect_error(
    qa$qa_validate_visual_coverage(inventory, covered, c(qa$qa_supported_plot_kinds(), "new_plot_kind")),
    "registry disagree"
  )

  output.root <- tempfile("visual-qa-report-")
  dir.create(output.root)
  forest.image <- tempfile(fileext = ".png")
  bubble.image <- tempfile(fileext = ".png")
  writeBin(as.raw(1:10), forest.image)
  writeBin(as.raw(1:10), bubble.image)
  forest <- data.frame(
    case=paste0(covered[covered != "regression"], "__case"),
    family=covered[covered != "regression"],
    kind="binary_two_arm", workflow="standard", style="default", scenario="base",
    image=forest.image, bytes=1000, error=NA_character_
  )
  bubble <- data.frame(
    case="regression__case",
    family="regression",
    kind="binary", workflow="meta-regression", style="default", scenario="base",
    image=bubble.image, bytes=1000, error=NA_character_
  )
  expect_silent(qa$qa_write_visual_qa_reports(output.root, forest, bubble))
  expect_true(file.exists(file.path(output.root, "coverage.csv")))
  expect_true(file.exists(file.path(output.root, "manifest.csv")))
  failed <- bubble
  failed$error <- "renderer exploded"
  expect_error(
    qa$qa_write_visual_qa_reports(output.root, forest, failed),
    "Visual QA render failures"
  )
})
