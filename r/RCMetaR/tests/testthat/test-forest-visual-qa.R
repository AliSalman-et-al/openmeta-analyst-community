test_that("optional forest visual QA matrix renders", {
  skip_if_not(identical(Sys.getenv("RCMETAR_RUN_VISUAL_QA"), "true"))

  find.repo.root <- function() {
    current <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
    repeat {
      if (file.exists(file.path(current, "r", "RCMetaR", "inst", "qa", "render_forest_visual_qa.R"))) {
        return(current)
      }
      parent <- dirname(current)
      if (identical(parent, current)) {
        skip("Could not locate rc-metastudio repository root")
      }
      current <- parent
    }
  }

  repo.root <- find.repo.root()
  script <- file.path(repo.root, "r", "RCMetaR", "inst", "qa", "render_forest_visual_qa.R")
  skip_if_not(file.exists(script))

  output.root <- file.path(tempdir(), "rcmetar-forest-visual-qa-test")
  Sys.setenv(RCMETASTUDIO_QA_ROOT = output.root)
  source(script, local = TRUE)
  manifest <- qa_render_matrix(output.root)

  expect_equal(nrow(manifest), 225)
  expect_setequal(
    unique(manifest$kind),
    c("binary_two_arm", "binary_one_arm", "continuous_two_arm", "continuous_one_arm", "diagnostic")
  )
  expect_setequal(unique(manifest$workflow), c("standard", "cumulative", "leave-one-out"))
  expect_setequal(unique(manifest$style), c("default", "revman", "bmj"))
  expect_false(any(is.na(manifest$image)))
  expect_true(all(file.exists(manifest$image)))
  expect_true(all(manifest$bytes > 1000))
})
