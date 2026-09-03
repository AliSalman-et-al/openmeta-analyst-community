# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

create.summary.disp <- function(om.data, params, res, model.title) {
  result.digits <- display.digits(params)
  se.digits <- display.digits(params, minimum=3L)
  digits.str <- paste("%.", result.digits, "f", sep="")
  se.digits.str <- paste("%.", se.digits, "f", sep="")
  transform.name <- get.transform.name(om.data)
  scale.str <- get.scale(params)
  tau2 <- format.numeric.display(res$tau2, digits.str)
  degf <- res$k - 1
  I2 <- format.percent.display(res$I2, "%.1f")
  QLabel =  paste("Q(df=", degf, ")", sep="")
  if (params$measure=="PFT" && length(om.data@g1O1) > 0 && length(om.data@g1O2) > 0) {
    n <- om.data@g1O1 + om.data@g1O2
  }
  else {
    n <- NULL
  }
  QE <- format.numeric.display(res$QE, digits.str)
  QEp <- format.p.value.display(res$QEp, params$digits)
  pVal <- format.p.value.display(res$pval, params$digits)

  res.title <- "Model Results"
  transform <- rcmetar.transform.by.name(transform.name, params$measure)
  y.disp <- sprintf(digits.str, transform$display.scale(res$b, ni=n))
  lb.disp <- sprintf(digits.str, transform$display.scale(res$ci.lb, ni=n))
  ub.disp <- sprintf(digits.str, transform$display.scale(res$ci.ub, ni=n))
  se <- sprintf(se.digits.str, res$se)

  if (res$method=="FE") {
    het.col.labels <- c(QLabel, "Het. p-value")
    het.col.vals <-  c(QE, QEp)
    het.array <- rbind(het.col.labels, het.col.vals)
  } else {
    het.col.labels <- c("\u03c4\u00b2", QLabel, "Het. p-value", "I\u00b2")
    het.col.vals <-  c(tau2, QE, QEp, I2)
    het.array <- rbind(het.col.labels, het.col.vals)
  }
  class(het.array) <- "summary.data"
  het.title <- "Heterogeneity"

  if (scale.str == "log" || scale.str == "logit" || scale.str == "arcsine") {
    res.col.labels <- c("Estimate", display.confidence.interval.labels(params), "p-value")
    res.col.vals <- c(y.disp, lb.disp, ub.disp, pVal)
    res.array <- rbind(res.col.labels, res.col.vals)
    estCalc <- sprintf(digits.str, res$b)
    lbCalc <- sprintf(digits.str, res$ci.lb)
    ubCalc <- sprintf(digits.str, res$ci.ub)
    calc.note <- paste(
      "Calculation scale: ", scale.str,
      " - estimate: ", estCalc,
      ", lower: ", lbCalc,
      ", upper: ", ubCalc,
      ", std. error: ", se,
      sep=""
    )
    arrays <- list(arr1=res.array, arr2=het.array)
    table.titles <- c(res.title, het.title)
    notes <- c(calc.note)
  } else {
    col.labels <- c("Estimate", display.confidence.interval.labels(params), "Std. error", "p-value")
    col.vals <- c(y.disp, lb.disp, ub.disp, se, pVal)
    res.array <- rbind(col.labels, col.vals)
    arrays = list(arr1=res.array, arr2=het.array)
    table.titles <- c(res.title, het.title)
    notes <- NULL
  }


  summary.disp <- list(
    "model.title" = model.title,
    "table.titles" = table.titles,
    "arrays" = arrays,
    "notes" = notes,
    "MAResults" = res)
  class(summary.disp) <- "summary.display"
  summary.disp
}

save.plot.data <- function(plot.data, out.path=NULL) {
  if (is.null(out.path)){
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }
  save(plot.data, file=paste(out.path, ".plotdata", sep=""))
  out.path
}

save.plot.data.and.params <- function(data, params, res, level, out.path=NULL) {
  if (is.null(out.path)){
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }

  save(data, file=paste(out.path, ".data", sep=""))

  save(params, file=paste(out.path, ".params", sep=""))

  save(res, file=paste(out.path, ".res", sep=""))

  save(level, file=paste(out.path, ".level", sep=""))

  out.path
}


save.data <- function(om.data, res, params, plot.data, out.path=NULL) {
  if (is.null(out.path)){
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }

  save(om.data, file=paste(out.path, ".data", sep=""))
  if (inherits(plot.data$regeneration_state, "rcmetar_forest_regeneration_state")) {
    res <- plot.data$regeneration_state
    for (param.name in names(res$param_overrides)) {
      params[[param.name]] <- res$param_overrides[[param.name]]
    }
  }
  save(res, file=paste(out.path, ".res", sep=""))

  save(plot.data, file=paste(out.path, ".plotdata", sep=""))
  save(params, file=paste(out.path, ".params", sep=""))
  out.path
}

update.changed.plot.params <- function(params, changed.params) {
  if (length(changed.params) == 0) {
    return(params)
  }
  for (param.name in names(changed.params)) {
    value <- changed.params[[param.name]]
    if (length(value) > 1) {
      value <- paste(value, collapse=", ")
    }
    params[[param.name]][1] <- value
  }
  params
}

rcmetar.regression.display.value <- function(value, digits, percent=FALSE) {
  if (display.value.is.missing(value) || length(value) != 1 || !is.finite(as.numeric(value))) {
    return("Not estimable")
  }
  if (percent) {
    return(sprintf(paste0("%.", digits, "f%%"), as.numeric(value)))
  }
  sprintf(paste0("%.", digits, "f"), as.numeric(value))
}

rcmetar.regression.summary.array <- function(rows, headers=c("Statistic", "Value")) {
  values <- do.call(rbind, rows)
  result <- rbind(headers, values)
  class(result) <- "summary.data"
  result
}

rcmetar.regression.factor.tests <- function(res, display.data, params) {
  factor.levels <- display.data$factor.n.levels
  factor.names <- display.data$factor.cov.names
  if (!inherits(res, "rma") || length(factor.levels) == 0 || length(factor.names) != length(factor.levels)) {
    return(list())
  }
  coefficient.index <- 2 + display.data$n.cont.covs
  tests <- list()
  for (index in seq_along(factor.levels)) {
    coefficient.count <- factor.levels[index] - 1
    btt <- coefficient.index:(coefficient.index + coefficient.count - 1)
    test <- tryCatch(anova(res, btt=btt), error=function(e) NULL)
    if (!is.null(test)) {
      tests[[factor.names[index]]] <- list(result=test, df1=coefficient.count)
    }
    coefficient.index <- coefficient.index + coefficient.count
  }
  tests
}

rcmetar.regression.test.row <- function(label, statistic, df1, p.value, df2=NULL, digits=3L) {
  display.df <- function(value) {
    if (display.value.is.missing(value) || length(value) != 1 || !is.finite(as.numeric(value))) {
      return("Not estimable")
    }
    as.character(as.numeric(value))
  }
  df <- if (is.null(df2) || display.value.is.missing(df2)) {
    display.df(df1)
  } else {
    paste(display.df(df1), display.df(df2), sep=", ")
  }
  formatted.p <- if (display.value.is.missing(p.value) || length(p.value) != 1 ||
                     !is.finite(as.numeric(p.value))) "Not estimable" else
    format.p.value.display(p.value, digits)
  c(label, rcmetar.regression.display.value(statistic, digits), df,
    formatted.p)
}

create.regression.display <- function(res, params, display.data) {
  bootstrap.type <- if (is.null(params$bootstrap.type)) "" else as.character(params$bootstrap.type)
  cov.display.col <- display.data$cov.display.col
  levels.display.col <- display.data$levels.display.col
  studies.display.col <- display.data$studies.display.col
  factor.n.levels <- display.data$factor.n.levels
  n.cont.covs <- display.data$n.cont.covs
  n.cont.rows <- n.cont.covs + 1
  n.factor.covs <- length(factor.n.levels)
  n.rows <- length(cov.display.col) + 1
  result.digits <- display.digits(params)
  se.digits <- display.digits(params, minimum=3L)
  digits.str <- paste("%.", result.digits, "f", sep="")
  inference.method <- rcmetar.inference.method(params)
  t.inference <- inference.method %in% c("t", "knha", "adhoc")
  ci.labels <- display.confidence.interval.labels(params)

  if (n.factor.covs == 0) {
    col.labels <- if (bootstrap.type == "boot.meta.reg") {
      c("Covariate", "Estimate", ci.labels)
    } else if (t.inference) {
      c("Covariate", "Estimate", ci.labels, "Std. error", "t", "df", "p-value")
    } else {
      c("Covariate", "Estimate", ci.labels, "Std. error", "z", "p-value")
    }
  } else {
    col.labels <- if (bootstrap.type == "boot.meta.reg") {
      c("Covariate", "Level", "Studies", "Estimate", ci.labels)
    } else if (t.inference) {
      c("Covariate", "Level", "Studies", "Estimate", ci.labels, "Std. error", "t", "df", "p-value")
    } else {
      c("Covariate", "Level", "Studies", "Estimate", ci.labels, "Std. error", "z", "p-value")
    }
  }

  reg.array <- array(dim=c(length(cov.display.col) + 1, length(col.labels)), dimnames=list(NULL, col.labels))
  reg.array[1,] <- col.labels
  display.values <- function(values, digits) {
    vapply(seq_along(res$b), function(index) {
      value <- if (length(values) >= index) values[index] else NULL
      rcmetar.regression.display.value(value, digits)
    }, character(1))
  }
  display.p.values <- function(values) {
    vapply(seq_along(res$b), function(index) {
      value <- if (length(values) >= index) values[index] else NULL
      if (display.value.is.missing(value) || length(value) != 1 || !is.finite(as.numeric(value))) {
        "Not estimable"
      } else {
        format.p.value.display(value, params$digits)
      }
    }, character(1))
  }
  coeffs <- display.values(res$b, result.digits)
  lbs <- display.values(res$ci.lb, result.digits)
  ubs <- display.values(res$ci.ub, result.digits)
  coeffs.tmp <- coeffs[1:n.cont.rows]
  lbs.tmp <- lbs[1:n.cont.rows]
  ubs.tmp <- ubs[1:n.cont.rows]

  if (bootstrap.type != "boot.meta.reg") {
    se <- display.values(res$se, se.digits)
    pvals <- display.p.values(res$pval)
    statistics <- display.values(res$zval, se.digits)
    dfs <- rep(if (!is.null(res$ddf)) res$ddf else res$k - res$p, length(res$b))
    se.tmp <- se[1:n.cont.rows]
    pvals.tmp <- pvals[1:n.cont.rows]
    statistics.tmp <- statistics[1:n.cont.rows]
    dfs.tmp <- dfs[1:n.cont.rows]
  }

  if (n.factor.covs > 0) {
    insert.row <- n.cont.rows + 1
    for (count in seq_len(n.factor.covs)) {
      n.levels <- factor.n.levels[count]
      coefficient.range <- insert.row:(insert.row + n.levels - 2)
      coeffs.tmp <- c(coeffs.tmp, "", coeffs[coefficient.range])
      lbs.tmp <- c(lbs.tmp, "", lbs[coefficient.range])
      ubs.tmp <- c(ubs.tmp, "", ubs[coefficient.range])
      if (bootstrap.type != "boot.meta.reg") {
        se.tmp <- c(se.tmp, "", se[coefficient.range])
        pvals.tmp <- c(pvals.tmp, "", pvals[coefficient.range])
        statistics.tmp <- c(statistics.tmp, "", statistics[coefficient.range])
        dfs.tmp <- c(dfs.tmp, "", dfs[coefficient.range])
      }
      insert.row <- insert.row + n.levels - 1
    }
    reg.array[2:n.rows, "Level"] <- levels.display.col
    reg.array[2:n.rows, "Studies"] <- studies.display.col
  }

  reg.array[2:n.rows, "Covariate"] <- cov.display.col
  reg.array[2:n.rows, "Estimate"] <- coeffs.tmp
  reg.array[2:n.rows, ci.labels[[1]]] <- lbs.tmp
  reg.array[2:n.rows, ci.labels[[2]]] <- ubs.tmp
  if (bootstrap.type != "boot.meta.reg") {
    reg.array[2:n.rows, "Std. error"] <- se.tmp
    reg.array[2:n.rows, if (t.inference) "t" else "z"] <- statistics.tmp
    if (t.inference) reg.array[2:n.rows, "df"] <- dfs.tmp
    reg.array[2:n.rows, "p-value"] <- pvals.tmp
  }
  class(reg.array) <- "summary.data"

  metric.name <- pretty.metric.name(as.character(params$measure))
  if (bootstrap.type == "boot.meta.reg") {
    model.title <- paste("Bootstrapped Meta-Regression based on ", params$num.bootstrap.replicates,
                         " replicates.\n\n", params$extra.attempts,
                         " resampling attempts failed.\n\nMetric: ", metric.name, sep="")
    reg.disp <- list(model.title=model.title, table.titles="Coefficient estimates",
                     arrays=list(reg.array), MAResults=res)
    class(reg.disp) <- "summary.display"
    return(reg.disp)
  }

  model.title <- paste("Meta-Regression\n\nMetric: ", metric.name, sep="")
  method.names <- rcmetar.random.effects.method.names()
  estimator <- if (identical(as.character(res$method), "FE")) {
    "Fixed effect"
  } else if (as.character(res$method) %in% names(method.names)) {
    method.names[[as.character(res$method)]]
  } else {
    as.character(res$method)
  }
  inference.label <- rcmetar.inference.method.names()[[inference.method]]
  residual.df <- res$k - res$p
  overview <- rcmetar.regression.summary.array(list(
    c("Studies analyzed", as.character(res$k)),
    c("Model coefficients", as.character(res$p)),
    c("Residual degrees of freedom", as.character(residual.df)),
    c("Heterogeneity estimator", estimator),
    c("Inference Method", inference.label)
  ))

  specification.rows <- list()
  continuous.names <- display.data$cont.cov.names
  continuous.ranges <- display.data$cont.cov.ranges
  if (is.null(continuous.names)) continuous.names <- cov.display.col[seq_len(n.cont.covs) + 1]
  for (name in continuous.names) {
    observed.range <- continuous.ranges[[name]]
    range.label <- if (length(observed.range) == 2 && all(is.finite(observed.range))) {
      paste0("Continuous; observed range ", sprintf(digits.str, observed.range[1]),
             " to ", sprintf(digits.str, observed.range[2]))
    } else {
      "Continuous"
    }
    specification.rows[[length(specification.rows) + 1]] <- c(name, range.label)
  }
  factor.names <- display.data$factor.cov.names
  factor.references <- display.data$factor.ref.levels
  if (!is.null(factor.names)) {
    for (index in seq_along(factor.names)) {
      specification.rows[[length(specification.rows) + 1]] <- c(
        factor.names[index], paste0("Categorical; reference level: ", factor.references[index]))
    }
  }
  zero.outside <- any(vapply(continuous.names, function(name) {
    observed.range <- continuous.ranges[[name]]
    length(observed.range) == 2 && all(is.finite(observed.range)) &&
      (0 < observed.range[1] || 0 > observed.range[2])
  }, logical(1)))
  intercept.note <- "Estimated effect at continuous moderator value zero and categorical reference levels"
  if (zero.outside) intercept.note <- paste0(intercept.note, "; extrapolated beyond an observed continuous range")
  specification.rows <- c(list(c("Intercept", intercept.note)), specification.rows)
  specification <- rcmetar.regression.summary.array(specification.rows, c("Term", "Specification"))

  scale <- get.scale(params)
  coefficient.title <- if (scale %in% c("log", "logit", "arcsine")) {
    paste0("Coefficient estimates (", scale, " scale)")
  } else {
    "Coefficient estimates"
  }

  arrays <- list(overview, specification, reg.array)
  titles <- c("Model overview", "Model specification", coefficient.title)

  if (!identical(as.character(res$method), "FE")) {
    heterogeneity <- rcmetar.regression.summary.array(list(
      c("Residual heterogeneity (\u03c4\u00b2)", rcmetar.regression.display.value(res$tau2, result.digits)),
      c("SE of \u03c4\u00b2", rcmetar.regression.display.value(res$se.tau2, se.digits)),
      c("Residual heterogeneity (\u03c4)", rcmetar.regression.display.value(sqrt(res$tau2), result.digits)),
      c("Residual I\u00b2", rcmetar.regression.display.value(res$I2, 1L, percent=TRUE)),
      c("Residual H\u00b2", rcmetar.regression.display.value(res$H2, result.digits)),
      c("Heterogeneity explained (R\u00b2)", rcmetar.regression.display.value(res$R2, 1L, percent=TRUE))
    ))
    arrays <- c(arrays, list(heterogeneity))
    titles <- c(titles, "Residual heterogeneity")
  }

  moderator.df2 <- if (t.inference) residual.df else NULL
  moderator.label <- if (t.inference) "Overall moderators (F)" else "Overall moderators (Q\u2098)"
  test.rows <- list(rcmetar.regression.test.row(
    moderator.label, res$QM, res$m, res$QMp, moderator.df2, params$digits))
  factor.tests <- rcmetar.regression.factor.tests(res, display.data, params)
  for (name in names(factor.tests)) {
    factor.test <- factor.tests[[name]]$result
    statistic <- if (!is.null(factor.test$QM)) factor.test$QM else factor.test$F
    df1 <- factor.tests[[name]]$df1
    test.rows[[length(test.rows) + 1]] <- rcmetar.regression.test.row(
      paste0(name, " (joint)"), statistic, df1, factor.test$QMp,
      if (t.inference) residual.df else NULL, params$digits)
  }
  test.rows[[length(test.rows) + 1]] <- rcmetar.regression.test.row(
    "Residual heterogeneity (Q\u2091)", res$QE, residual.df, res$QEp,
    NULL, params$digits)
  tests <- rcmetar.regression.summary.array(test.rows, c("Test", "Statistic", "df", "p-value"))
  arrays <- c(arrays, list(tests))
  titles <- c(titles, "Model tests")

  notes <- if (!identical(as.character(res$method), "FE")) {
    "Heterogeneity explained (R\u00b2) is the proportional reduction in estimated between-study heterogeneity relative to the corresponding model without moderators."
  } else {
    NULL
  }
  reg.disp <- list(model.title=model.title, table.titles=titles, arrays=arrays,
                   notes=notes, MAResults=res)
  class(reg.disp) <- "summary.display"
  reg.disp
}

adjusted_means_display <- function(res, params, display.data) {
  display.scale <- function(x, metric) {
    if (metric.is.log.scale(metric)) {
      exp(x)
    } else if (metric.is.logit.scale(metric)) {
      invlogit(x)
    } else if (metric.is.arcsine.scale(metric)) {
      invarcsine.sqrt(x)
    } else {
      x
    }
  }

  factor.n.levels <- display.data$factor.n.levels
  if (length(factor.n.levels) != 1) {
    stop("adjusted_means_display requires exactly one factor covariate")
  }
  if (!is.null(display.data$n.cont.covs) && display.data$n.cont.covs != 0) {
    stop("adjusted_means_display does not support continuous covariates")
  }

  n.levels <- factor.n.levels[[1]]
  if (n.levels < 2) {
    stop("adjusted_means_display requires at least two factor levels")
  }
  levels.display.col <- display.data$levels.display.col
  studies.display.col <- display.data$studies.display.col

  coefficient.count <- length(as.vector(res$b))
  if (coefficient.count < n.levels) {
    stop("meta-regression result has fewer coefficients than factor levels")
  }

  mult <- get.mult.from.conf.level(params$conf.level)
  digits.str <- paste("%.", display.digits(params), "f", sep="")
  se.digits.str <- paste("%.", display.digits(params, minimum=3L), "f", sep="")

  design.matrix <- cbind(
    Intercept=rep(1, n.levels),
    rbind(rep(0, n.levels - 1), diag(n.levels - 1))
  )
  betas <- as.matrix(res$b[1:n.levels, , drop=FALSE])
  covariance <- as.matrix(res$vb[1:n.levels, 1:n.levels, drop=FALSE])

  estimates <- as.vector(design.matrix %*% betas)
  variances <- diag(design.matrix %*% covariance %*% t(design.matrix))
  se <- sqrt(variances)
  ci.lb <- estimates - mult * se
  ci.ub <- estimates + mult * se

  estimates.disp <- display.scale(estimates, params$measure)
  ci.lb.disp <- display.scale(ci.lb, params$measure)
  ci.ub.disp <- display.scale(ci.ub, params$measure)

  ci.labels <- display.confidence.interval.labels(params)
  adj.array <- array(
    dim=c(n.levels + 1, 6),
    dimnames=list(NULL, c("Level", "Studies", "Estimate", ci.labels, "Std. error"))
  )
  adj.array[1,] <- c("Level", "Studies", "Estimate", ci.labels, "Std. error")
  level.start <- display.data$n.cont.covs + 2
  level.end <- level.start + n.levels - 1
  if (length(levels.display.col) < level.end || length(studies.display.col) < level.end) {
    stop("display data does not contain factor levels")
  }
  adj.array[2:(n.levels + 1), "Level"] <- levels.display.col[level.start:level.end]
  adj.array[2:(n.levels + 1), "Studies"] <- studies.display.col[level.start:level.end]
  adj.array[2:(n.levels + 1), "Estimate"] <- sprintf(digits.str, estimates.disp)
  adj.array[2:(n.levels + 1), ci.labels[[1]]] <- sprintf(digits.str, ci.lb.disp)
  adj.array[2:(n.levels + 1), ci.labels[[2]]] <- sprintf(digits.str, ci.ub.disp)
  adj.array[2:(n.levels + 1), "Std. error"] <- sprintf(se.digits.str, se)

  metric.name <- pretty.metric.name(as.character(params$measure))
  model.title <- paste("Adjusted Means\n\nMetric: ", metric.name, sep="")
  adj.disp <- list(
    "model.title" = model.title,
    "table.titles" = c("Adjusted Means"),
    "arrays" = list(arr1=adj.array),
    "MAResults" = list(b=estimates, se=se, ci.lb=ci.lb, ci.ub=ci.ub)
  )
  class(adj.disp) <- "summary.display"
  adj.disp
}

create.overall.display <- function(res, study.names, params, model.title, data.type) {
  if (data.type == "continuous") {
    transform.name <- "continuous.transform.f"
  } else if (data.type == "diagnostic") {
    transform.name <- "diagnostic.transform.f"
  }  else {
    transform.name <- "binary.transform.f"
  }
  scale.str <- get.scale(params)
  overall.array <- array(dim=c(length(study.names) + 1, 6))

  overall.array[1,] <- c("Studies", "Estimate", display.confidence.interval.labels(params), "Std. error", "p-value")

  for (count in 1:length(res)) {
    y <- res[[count]]$b
    lb <- res[[count]]$ci.lb
    ub <- res[[count]]$ci.ub
    se <- res[[count]]$se
    digits.str <- paste("%.", display.digits(params), "f", sep="")
    se.digits.str <- paste("%.", display.digits(params, minimum=3L), "f", sep="")
    transform <- rcmetar.transform.by.name(transform.name, params$measure)
    y.disp <- sprintf(digits.str, transform$display.scale(y, n=NULL))
    lb.disp <- sprintf(digits.str, transform$display.scale(lb, n=NULL))
    ub.disp <- sprintf(digits.str, transform$display.scale(ub, n=NULL))
    se.disp <- sprintf(se.digits.str, se)

    pVal <- format.p.value.display(res[[count]]$pval, params$digits)
    overall.array[count+1,] <- c(study.names[count], y.disp, lb.disp, ub.disp, se.disp, pVal)
  }

  table.titles <- c("Model Results")
  arrays <- list(arr1=overall.array)
  overall.disp <- list("model.title" = model.title, "table.titles" = table.titles, "arrays" = arrays,
             "MAResults" = res )
  class(overall.disp) <- "summary.display"
  overall.disp
}

create.subgroup.display <- function(res, study.names, params, model.title, data.type) {
  if (data.type == "continuous") {
    transform.name <- "continuous.transform.f"
  } else if (data.type == "diagnostic") {
    transform.name <- "diagnostic.transform.f"
  }  else {
    transform.name <- "binary.transform.f"
  }
  scale.str <- "standard"
  if (metric.is.log.scale(params$measure)){
    scale.str <- "log"
  } else if (metric.is.logit.scale(params$measure)) {
    scale.str <- "logit"
  }
  subgroup.array <- array(dim=c(length(study.names) + 1, 8))
  het.array <- array(dim=c(length(study.names) + 1, 4))

  n <- length(study.names)

  subgroup.array[1,] <- c("Subgroups", "Studies", "Estimate", display.confidence.interval.labels(params), "Std. error", "p-value", "z-value")
  het.array[1,] <- c("Studies", "Q (df)",
               "Het. p-value", "I\u00b2")
  for (count in 1:length(study.names)) {
    num.studies <- res[[count]]$k
    y <- res[[count]]$b
    lb <- res[[count]]$ci.lb
    ub <- res[[count]]$ci.ub
    se <- res[[count]]$se
    digits.str <- paste("%.", display.digits(params), "f", sep="")
    se.digits.str <- paste("%.", display.digits(params, minimum=3L), "f", sep="")
    transform <- rcmetar.transform.by.name(transform.name, params$measure)
    y.disp <- sprintf(digits.str, transform$display.scale(y, n))
    lb.disp <- sprintf(digits.str, transform$display.scale(lb, n))
    ub.disp <- sprintf(digits.str, transform$display.scale(ub, n))
    se.disp <- sprintf(se.digits.str, se)
    if (!display.value.is.missing(res[[count]]$QE)) {
      degf <- res[[count]]$k - 1
      QE <- sprintf(digits.str, res[[count]]$QE)
      QE <- paste(QE, " (", degf,")", sep="")
    } else {
      QE <- ""
    }
    I2 <- format.percent.display(res[[count]]$I2, "%.1f")
    QEp <- format.p.value.display(res[[count]]$QEp, params$digits)
    pVal <- format.p.value.display(res[[count]]$pval, params$digits)
    zVal <- g.round.display.zval(res[[count]]$zval, digits=params$digits)

    if (is.null(num.studies))
      num.studies <- 1

    subgroup.array[count+1,] <- c(study.names[count], num.studies, y.disp, lb.disp, ub.disp, se.disp, pVal, zVal)
    het.array[count+1,] <- c(study.names[count], QE, QEp, I2)
  }

  table.titles <- c("Model Results", "Heterogeneity")
  arrays <- list(arr1=subgroup.array, arr2=het.array)
  subgroup.disp <- list("model.title" = model.title, "table.titles" = table.titles, "arrays" = arrays,
             "MAResults" = res )
  class(subgroup.disp) <- "summary.display"
  subgroup.disp
}
