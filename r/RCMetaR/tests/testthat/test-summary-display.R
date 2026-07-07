summary_display_fixture <- function(res.overrides = list()) {
  params <- list(
    conf.level = 95,
    digits = 3,
    measure = "OR",
    rm.method = "DL",
    to = "only0",
    adjust = 0.5
  )
  data <- new(
    "BinaryData",
    g1O1 = c(6, 3, 19),
    g1O2 = c(21, 56, 145),
    g2O1 = c(9, 7, 13),
    g2O2 = c(18, 57, 139),
    y = c(-0.5596157879, -0.8295982833, 0.3372298124),
    SE = c(0.6172133998, 0.7152562329, 0.3790058736),
    study.names = c("Gonzalez", "Prins", "Maller"),
    years = as.integer(c(1993, 1993, 1993))
  )
  res <- list(
    b = -0.262,
    ci.lb = -0.724,
    ci.ub = 0.200,
    se = 0.236,
    pval = 0.267,
    tau2 = 0.378,
    k = 13,
    I2 = 92.645,
    QE = 33.360,
    QEp = 0.015,
    method = "DL"
  )
  for (name in names(res.overrides)) {
    res[[name]] <- res.overrides[[name]]
  }

  RCMetaR:::create.summary.disp(data, params, res, "Binary Random-Effects Model\n\nMetric: Odds Ratio")
}

subgroup_display_fixture <- function(with.missing.values = FALSE) {
  params <- list(
    conf.level = 95,
    digits = 3,
    measure = "OR"
  )
  res <- list(
    list(
      b = -0.262,
      ci.lb = -0.724,
      ci.ub = 0.200,
      se = 0.236,
      pval = 0.267,
      zval = -1.110,
      k = 13,
      QE = 33.360,
      QEp = 0.015,
      I2 = 92.645
    ),
    list(
      b = 0.125,
      ci.lb = -0.100,
      ci.ub = 0.350,
      se = 0.115,
      pval = 0.277,
      zval = 1.087,
      k = 4,
      QE = 5.100,
      QEp = 0.165,
      I2 = 41.2
    )
  )
  if (with.missing.values) {
    res[[2]]$QE <- NULL
    res[[2]]$QEp <- NA_real_
    res[[2]]$I2 <- NULL
    res[[2]]$pval <- NA_real_
    res[[2]]$zval <- NULL
  }

  RCMetaR:::create.subgroup.display(res, c("Early", "Late"), params, "Subgroup Analysis", "binary")
}

overall_display_fixture <- function() {
  params <- list(
    conf.level = 95,
    digits = 3,
    measure = "OR"
  )
  res <- list(
    list(
      b = -0.262,
      ci.lb = -0.724,
      ci.ub = 0.200,
      se = 0.236,
      pval = NULL
    ),
    list(
      b = 0.125,
      ci.lb = -0.100,
      ci.ub = 0.350,
      se = 0.115,
      pval = 0.277
    )
  )

  RCMetaR:::create.overall.display(
    res,
    c("First study", "Second study"),
    params,
    "Cumulative Summary",
    "binary"
  )
}

first_line_after <- function(lines, label) {
  label.index <- match(label, lines)
  lines[label.index + which(nzchar(lines[(label.index + 1):length(lines)]))[1]]
}

next_non_empty_line <- function(lines, line) {
  line.index <- match(line, lines)
  lines[line.index + which(nzchar(lines[(line.index + 1):length(lines)]))[1]]
}

expect_values_inside_header_columns <- function(header, values, labels) {
  starts <- vapply(labels, function(label) regexpr(label, header, fixed = TRUE)[1], integer(1))
  value.matches <- gregexpr("[^ ]+", values, perl = TRUE)[[1]]
  value.lengths <- attr(value.matches, "match.length")

  expect_equal(length(value.matches), length(labels))
  for (index in seq_along(labels)) {
    column.start <- if (index == 1) 1 else starts[index - 1] + nchar(labels[index - 1])
    column.end <- if (index == length(labels)) {
      nchar(values)
    } else {
      starts[index + 1] - 1
    }
    expect_gte(value.matches[index], column.start)
    expect_lte(value.matches[index] + value.lengths[index] - 1, column.end)
  }
}

test_that("round.display preserves signed negative estimates", {
  expect_equal(round.display(c(-0.809, -0.0004, 0.0004, 0.809), 3), c("-0.809", "-0.000", "< 0.001", "0.809"))
})

test_that("summary display uses readable labels and aligned columns", {
  rendered <- capture.output(print(summary_display_fixture()))
  text <- paste(rendered, collapse = "\n")

  expect_match(text, "\u03c4\u00b2", fixed = TRUE)
  expect_match(text, "I\u00b2", fixed = TRUE)
  expect_false(grepl("tau^2", text, fixed = TRUE))
  expect_false(grepl("I^2", text, fixed = TRUE))
  expect_match(text, "92.645%", fixed = TRUE)
  expect_false(grepl(" Results (log scale)", text, fixed = TRUE))
  expect_match(
    text,
    "Calculation scale: log - estimate: -0.262, lower: -0.724, upper: 0.200, std. error: 0.236",
    fixed = TRUE
  )
  expect_false(grepl("Calculation scale: log; estimate", text, fixed = TRUE))
  expect_false(grepl("; lower bound:", text, fixed = TRUE))
  expect_false(grepl("Std. error: 0.236", text, fixed = TRUE))

  expect_match(text, "\nModel Results\n", fixed = TRUE)
  expect_match(text, "\nHeterogeneity\n", fixed = TRUE)
  expect_false(grepl("\n Model Results\n", text, fixed = TRUE))
  expect_false(grepl("\n Heterogeneity\n", text, fixed = TRUE))
  expect_false(grepl("p-Value", text, fixed = TRUE))
  expect_false(grepl("Het. p-Value", text, fixed = TRUE))
  expect_false(grepl("\n\n\n", text, fixed = TRUE))

  model.header <- first_line_after(rendered, "Model Results")
  model.values <- next_non_empty_line(rendered, model.header)
  heterogeneity.header <- first_line_after(rendered, "Heterogeneity")
  heterogeneity.values <- next_non_empty_line(rendered, heterogeneity.header)

  model.labels <- c("Estimate", "Lower bound", "Upper bound", "p-value")
  heterogeneity.labels <- c("\u03c4\u00b2", "Q(df=12)", "Het. p-value", "I\u00b2")
  expect_values_inside_header_columns(model.header, model.values, model.labels)
  expect_values_inside_header_columns(heterogeneity.header, heterogeneity.values, heterogeneity.labels)
})

test_that("summary display leaves unavailable statistics blank", {
  display <- summary_display_fixture(list(
    QE = NULL,
    QEp = NA_real_,
    I2 = NULL,
    pval = NA_real_
  ))

  model <- display$arrays$arr1
  heterogeneity <- display$arrays$arr2

  expect_equal(unname(model[2, 4]), "")
  expect_equal(unname(heterogeneity[2, 2]), "")
  expect_equal(unname(heterogeneity[2, 3]), "")
  expect_equal(unname(heterogeneity[2, 4]), "")
})

test_that("subgroup heterogeneity display uses readable I-squared labels", {
  rendered <- capture.output(print(subgroup_display_fixture()))
  text <- paste(rendered, collapse = "\n")

  expect_match(text, "I\u00b2", fixed = TRUE)
  expect_false(grepl("I^2", text, fixed = TRUE))
  expect_match(text, "92.645%", fixed = TRUE)
})

test_that("subgroup display leaves unavailable statistics blank", {
  display <- subgroup_display_fixture(with.missing.values = TRUE)
  model <- display$arrays$arr1
  heterogeneity <- display$arrays$arr2

  expect_equal(unname(model[3, 7]), "")
  expect_equal(unname(model[3, 8]), "")
  expect_equal(unname(heterogeneity[3, 2]), "")
  expect_equal(unname(heterogeneity[3, 3]), "")
  expect_equal(unname(heterogeneity[3, 4]), "")
})

test_that("overall display leaves unavailable p-values blank", {
  display <- overall_display_fixture()
  overall <- display$arrays$arr1

  expect_equal(overall[2, 6], "")
  expect_equal(overall[3, 6], "0.277")
})

test_that("meta-regression omnibus p-value uses small-p display convention", {
  display <- RCMetaR:::create.regression.display(
    list(
      b = c(0.1, 0.2),
      ci.lb = c(0.0, 0.1),
      ci.ub = c(0.2, 0.3),
      se = c(0.01, 0.02),
      pval = c(0.0002, 0.267),
      QMp = 0.0002
    ),
    list(digits = 3, measure = "OR"),
    list(
      cov.display.col = c("intercept", "latitude"),
      levels.display.col = character(0),
      studies.display.col = character(0),
      factor.n.levels = numeric(0),
      n.cont.covs = 1
    )
  )
  rendered <- paste(capture.output(print(display)), collapse = "\n")

  expect_match(rendered, "< 0.001", fixed = TRUE)
  expect_false(grepl("Omnibus p-value\n 0.000", rendered, fixed = TRUE))
})

test_that("forest plot p-value labels use small-p display convention", {
  expect_equal(
    RCMetaR:::forest.plot.p.value.label(0.0002, 3),
    "P< 0.001"
  )
  expect_equal(
    RCMetaR:::forest.plot.p.value.label(0.015, 3),
    "P=0.015"
  )
  expect_equal(
    RCMetaR:::forest.plot.p.value.label(NULL, 3),
    ""
  )
  expect_equal(
    RCMetaR:::forest.plot.p.value.label(NA_real_, 3),
    ""
  )
  expect_equal(
    RCMetaR:::forest.plot.heterogeneity.suffix("92.65%", "P=0.015"),
    " (I\u00b2=92.65%, P=0.015)"
  )
  expect_equal(
    RCMetaR:::forest.plot.heterogeneity.suffix("92.65%", ""),
    " (I\u00b2=92.65%)"
  )
  expect_equal(
    RCMetaR:::forest.plot.heterogeneity.suffix("", "P=0.015"),
    " (P=0.015)"
  )
  expect_equal(
    RCMetaR:::forest.plot.heterogeneity.suffix("", ""),
    ""
  )
})
