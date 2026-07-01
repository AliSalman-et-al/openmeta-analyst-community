test_that("diagnostic.hsroc retries a failed first chain in a clean directory", {
  work <- tempfile("openmetar_hsroc_")
  dir.create(work)
  dir.create(file.path(work, "r_tmp"))
  old <- getwd()
  setwd(work)
  on.exit(setwd(old), add = TRUE)

  diagnostic.data <- new(
    "DiagnosticData",
    TP = c(19, 8, 41, 5, 45),
    FN = c(10, 2, 12, 2, 32),
    TN = c(81, 13, 49, 18, 165),
    FP = c(1, 9, 1, 1, 58)
  )
  params <- list(
    num.chains = 1,
    num.iters = 10,
    burn.in = 1,
    thin = 1,
    lambda.lower = -2,
    lambda.upper = 2,
    theta.lower = -2,
    theta.upper = 2
  )

  calls <- character()
  summary.chains <- character()
  write.valid.chain <- function(path) {
    for (file.name in hsroc.required.chain.files()) {
      write(c(0.1, 0.2, 0.3), file=file.path(path, file.name), ncolumns=1)
    }
  }
  fake.HSROC <- function(..., path) {
    calls <<- c(calls, path)
    if (length(calls) == 1) {
      stop("simulated transient HSROC failure")
    }
    write.valid.chain(path)
    invisible(NULL)
  }
  fake.HSROCSummary <- function(..., chain) {
    summary.chains <<- chain
    list(
      `Between-study parameters` = matrix(1:4, nrow = 2),
      `Within-study parameters` = array(1:8, dim = c(2, 2, 2)),
      image.list = list("Summary ROC" = "roc.png")
    )
  }

  local_mocked_bindings(
    HSROC = fake.HSROC,
    HSROCSummary = fake.HSROCSummary,
    .package = "OpenMetaR"
  )
  result <- diagnostic.hsroc(diagnostic.data, params)

  expect_type(result, "list")
  expect_true("Summary" %in% names(result))
  expect_length(calls, 2)
  expect_match(calls[[2]], "chain_1_retry_1$")
  expect_identical(summary.chains, calls[[2]])
  expect_equal(normalizePath(getwd(), winslash = "/"), normalizePath(work, winslash = "/"))
})
