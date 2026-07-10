test_that("comprehensive visual QA accounts for every user-visible plot family", {
  repo.root <- normalizePath(file.path(testthat::test_path(), "..", "..", "..", ".."), winslash = "/")
  script <- file.path(repo.root, "r", "RCMetaR", "inst", "qa", "render_plot_visual_qa.R")
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
      "sroc",
      "hsroc_diagnostics"
    )
  )
  expect_true(all(inventory$status %in% c("covered", "excluded")))
  expect_true(all(nzchar(inventory$reason[inventory$status == "excluded"])))
  expect_true(all(nzchar(inventory$evidence[inventory$status == "excluded"])))

  covered <- inventory$family[inventory$status == "covered"]
  expect_silent(qa$qa_validate_visual_coverage(inventory, covered))
  expect_error(
    qa$qa_validate_visual_coverage(inventory, setdiff(covered, "regression")),
    "missing covered plot families: regression"
  )

  output.root <- tempfile("visual-qa-report-")
  dir.create(output.root)
  forest <- data.frame(
    case=paste0(covered[covered != "regression"], "__case"),
    family=covered[covered != "regression"],
    image="plot.png",
    bytes=1000
  )
  bubble <- data.frame(
    case="regression__case",
    family="regression",
    image="bubble.png",
    bytes=1000
  )
  expect_silent(qa$qa_write_visual_qa_reports(output.root, forest, bubble))
  expect_true(file.exists(file.path(output.root, "coverage.csv")))
  expect_true(file.exists(file.path(output.root, "manifest.csv")))
})
