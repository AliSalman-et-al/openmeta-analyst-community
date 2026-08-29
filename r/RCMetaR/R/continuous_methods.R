# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

continuous.two.arm.metrics <- c("MD", "SMD")
continuous.one.arm.metrics <- c("TXMean")

compute.for.one.cont.study <- function(cont.data, params) {
  n1i <- cont.data@N1
  n2i <- cont.data@N2
  m1i <- cont.data@mean1
  m2i <- cont.data@mean2
  sd1i <- cont.data@sd1
  sd2i <- cont.data@sd2
  if (params$measure %in% continuous.one.arm.metrics) {
    return(data.frame(yi=m1i, vi=(sd1i^2) / n1i))
  }
  res <- escalc(params$measure, n1i=n1i, n2i=n2i, m1i=m1i, m2i=m2i, sd1i=sd1i, sd2i=sd2i)
  res
}

continuous.transform.f <- function(metric.str) {
  display.scale <- function(x, ...) {
    x
  }

  calc.scale <- function(x, ...) {
    x
  }

  list(display.scale = display.scale, calc.scale = calc.scale)
}

get.res.for.one.cont.study <- function(cont.data, params){
  y<-NULL
  se<-NULL
  if (length(cont.data@y) == 0 || is.na(cont.data@y)) {
    res <- compute.for.one.cont.study(cont.data, params)
    y <- res$yi[1]
    se <- sqrt(res$vi[1])
  }
  else {
    y <- cont.data@y[1]
    se <- cont.data@SE[1]
  }
  mult <- get.mult.from.conf.level(params$conf.level)
  ub <- y + mult*se
  lb <- y - mult*se
  res <- list("b"=c(y), "ci.lb"=lb, "ci.ub"=ub, "se"=se)
  res
}

create.cont.data.array <- function(cont.data, params, res) {
  tx1.name <- "tx A"
  tx2.name <- "tx B"
  digits.str <- paste("%.", params$digits, "f", sep="")
  effect.size.name <- pretty.metric.name(as.character(params$measure))
  study.ci.bounds <- calc.ci.bounds(cont.data, params)
  y.disp <- continuous.transform.f(params$measure)$display.scale(cont.data@y)
  lb.disp <- continuous.transform.f(params$measure)$display.scale(study.ci.bounds$lb)
  ub.disp <- continuous.transform.f(params$measure)$display.scale(study.ci.bounds$ub)
  y <- sprintf(digits.str, y.disp)
  LL <- sprintf(digits.str, lb.disp)
  UL <- sprintf(digits.str, ub.disp)
  weights <- res$study.weights
  weights <- sprintf(digits.str, weights)
  weights <- format(weights, justify="right")
  N.txA <- format(cont.data@N1, justify="right")
  mean.txA <- sprintf(digits.str, cont.data@mean1)
  sd.txA <- sprintf(digits.str, cont.data@sd1)
  if (params$measure %in% continuous.two.arm.metrics) {
      N.txB <- format(cont.data@N2, justify="right")
      mean.txB <- sprintf(digits.str, cont.data@mean2)
      sd.txB <- sprintf(digits.str, cont.data@sd2)
      raw.data <- array(
        c("Study", cont.data@study.names,
        paste(tx1.name, " N", sep=""), N.txA,
        paste(tx1.name, " Mean", sep=""), mean.txA,
        paste(tx1.name, " SD", sep=""), sd.txA,
        paste(tx2.name, " N", sep=""), N.txB,
        paste(tx2.name, " Mean", sep=""), mean.txB,
        paste(tx2.name, " SD", sep=""), sd.txB,
        effect.size.name, y, "Lower", LL, "Upper", UL, "Weight", weights),
        dim=c(length(cont.data@study.names) + 1, 11))
  } else if (params$measure %in% continuous.one.arm.metrics) {
    raw.data <- array(
      c("Study", cont.data@study.names,
      paste(tx1.name, " N", sep=""), N.txA,
      paste(tx1.name, " Mean", sep=""), mean.txA,
      paste(tx1.name, " SD", sep=""), sd.txA,
      effect.size.name, y, "Lower", LL, "Upper", UL, "Weight", weights),
      dim=c(length(cont.data@study.names) + 1, 8))
  }
  class(raw.data) <- "summary.data"
  return(raw.data)
}

write.cont.study.data.to.file <- function(cont.data, params, res, data.outpath) {
  effect.size.name <- pretty.metric.name(as.character(params$measure))
  study.ci.bounds <- calc.ci.bounds(cont.data, params)
  if (params$measure %in% continuous.two.arm.metrics) {
    study.data.df <- data.frame(
      "study.names"=paste(cont.data@study.names, " ", cont.data@years, sep=""),
      "N1" = cont.data@N1,
      "mean1" = cont.data@mean1,
      "sd1" = cont.data@sd1,
      "N2" = cont.data@N2,
      "mean2" = cont.data@mean2,
      "sd2" = cont.data@sd2,
      "Effect.size" = continuous.transform.f(params$measure)$display.scale(cont.data@y),
      "Lower.bound" = continuous.transform.f(params$measure)$display.scale(study.ci.bounds$lb),
      "Upper.bound" = continuous.transform.f(params$measure)$display.scale(study.ci.bounds$ub),
      "Weight" = res$study.weights)
  } else if(params$measure %in% continuous.one.arm.metrics) {
    study.data.df <- data.frame(
      "study.names"=paste(cont.data@study.names, " ", cont.data@years, sep=""),
      "N1" = cont.data@N1,
      "mean1" = cont.data@mean1,
      "sd1" = cont.data@sd1,
      "Effect.size" = continuous.transform.f(params$measure)$display.scale(cont.data@y),
      "Lower.bound" = continuous.transform.f(params$measure)$display.scale(study.ci.bounds$lb),
      "Upper.bound" = continuous.transform.f(params$measure)$display.scale(study.ci.bounds$ub),
      "Weight" = res$study.weights)
  }
  names(study.data.df)[names(study.data.df)=="Effect.size"] <- effect.size.name
  write.csv(study.data.df, file=data.outpath, row.names=FALSE)
}

continuous.fixed <- function(cont.data, params){
  if (!("ContinuousData" %in% class(cont.data))) stop("Continuous data expected.")

  results <- NULL
  input.params <- params
  inference.method <- rcmetar.validate.inference.method(params, length(cont.data@y))

  if (length(cont.data@study.names) == 1){
    res <- get.res.for.one.cont.study(cont.data, params)
    results <- list("Summary"=res, "res"=res)
  }
  else {
    res<-rma.uni(
      yi=cont.data@y,
      sei=cont.data@SE,
      slab=cont.data@study.names,
      method="FE",
      test=inference.method,
      level=params$conf.level,
      digits=params$digits)
    pure.res <- res

		res$weights <- weights(res)
		results <- list("Summary"=res)

    metric.name <- pretty.metric.name(as.character(params$measure))
    model.title <- paste("Continuous Fixed-Effect Model\n\nMetric: ", metric.name, sep="")
    summary.disp <- create.summary.disp(cont.data, params, res, model.title)
    forest.path <- paste(params$fp_outpath, sep="")
    plot.data <- create.plot.data.continuous(cont.data, params, res)
    changed.params <- plot.data$changed.params

		forest.plot.params.path <- ""
		if (is.null(params$supress.output) || !params$supress.output) {
      params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
      changed.params <- c(changed.params, params.changed.in.forest.plot)
      params <- update.changed.plot.params(params, changed.params)
      forest.plot.params.path <- save.data(cont.data, res, params, plot.data)
		}

    plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
    images <- c("Forest Plot"=forest.path)
    plot.names <- c("forest plot"="forest_plot")
		pure.res$weights <- weights(res)
        results <- list(
          "input_data"=cont.data,
          "input_params"=input.params,
          "images"=images,
          "Summary"=capture.output.and.collapse(summary.disp),
          "plot_names"=plot.names,
          "plot_params_paths"=plot.params.paths,
          "res"=pure.res,
          "res.info"=continuous.fixed.value.info(),
          "Weights"=weights(res))
  }

  results[["References"]] <- rcmetar.unique.references(c(
    rcmetar.method.references("rma.uni.fixed"),
    rcmetar.inference.method.references(params)))

  results
}

continuous.fixed.parameters <- function(){
  params <- list("inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int")

  defaults <- list("inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS)

  var_order <- c("inference.method", "conf.level", "digits")
  parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

continuous.fixed.pretty.names <- function() {
  pretty.names <- list(
    "pretty.name"="Continuous Fixed-Effect Inverse Variance",
     "description" = "Performs fixed-effect meta-analysis with inverse variance weighting.",
     "inference.method"=rcmetar.inference.method.metadata(),
     "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
     "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
     "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
     "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
               is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
               is added to all two-by-two tables if at least one table contains a zero.")
      )
}

continuous.fixed.overall <- function(results){
  res <- results$res
}

continuous.random <- function(cont.data, params) {
  if (!("ContinuousData" %in% class(cont.data)))
  stop("Continuous data expected.")

  results <- NULL
	input.params <- params
	inference.method <- rcmetar.validate.inference.method(params, length(cont.data@y))

  if (length(cont.data@study.names) == 1) {
      res <- get.res.for.one.cont.study(cont.data, params)
      results <- list("Summary"=res, "res"=res)
  }
  else {
    res<-rma.uni(
      yi=cont.data@y, sei=cont.data@SE,
      slab=cont.data@study.names,
      method=params$rm.method,
      test=inference.method,
      level=params$conf.level,
      digits=params$digits)
    pure.res<-res

		res$weights <- weights(res)
    results <- list("Summary"=res)

    metric.name <- pretty.metric.name(as.character(params$measure))
    model.title <- paste("Continuous Random-Effects Model\n\nMetric: ", metric.name, sep="")
    summary.disp <- create.summary.disp(cont.data, params, res, model.title)

    forest.path <- paste(params$fp_outpath, sep="")
    plot.data <- create.plot.data.continuous(cont.data, params, res)
    changed.params <- plot.data$changed.params

		forest.plot.params.path <- ""
		if (is.null(params$supress.output) || !params$supress.output) {
      params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
      changed.params <- c(changed.params, params.changed.in.forest.plot)
      params <- update.changed.plot.params(params, changed.params)
      forest.plot.params.path <- save.data(cont.data, res, params, plot.data)
		}

    plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
    images <- c("Forest Plot"=forest.path)
    plot.names <- c("forest plot"="forest_plot")
    pure.res$weights <- weights(res)
    results <- list(
      "input_data"=cont.data,
      "input_params"=input.params,
      "images"=images,
      "Summary"=capture.output.and.collapse(summary.disp),
      "plot_names"=plot.names,
      "plot_params_paths"=plot.params.paths,
      "res"=pure.res,
      "res.info"=continuous.random.value.info(),
      "Weights"=weights(res))
  }

  results[["References"]] <- rcmetar.unique.references(c(
    rcmetar.method.references("rma.uni.random"),
    rcmetar.inference.method.references(params)))

  results
}

continuous.random.value.info <- function() {
  rma.uni.value.info()
}

continuous.fixed.value.info <- function() {
  rma.uni.value.info()
}


continuous.random.parameters <- function() {
  rm_method_ls <- rcmetar.random.effects.methods()

  params <- list("rm.method"=rm_method_ls, "inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int")

  defaults <- list("rm.method"="DL", "inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS)

  var_order <- c("rm.method", "inference.method", "conf.level", "digits")
  parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

continuous.random.pretty.names <- function() {
	rm_method_names <- rcmetar.random.effects.method.names()

  pretty.names <- list(
    "pretty.name"="Continuous Random-Effects",
    "description" = "Performs random-effects meta-analysis.",
    "rm.method"=list("pretty.name"="Random-Effects method", "description"="Method for estimating between-studies heterogeneity", "rm.method.names"=rm_method_names),
    "inference.method"=rcmetar.inference.method.metadata(),
    "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
    "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
    "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
    "to"=list("pretty.name"="Correction factor target", "description"="When Add correction factor is set to \"only 0\", the correction factor
             is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
             is added to all two-by-two tables if at least one table contains a zero.")
    )
}

continuous.random.overall <- function(results){
  res <- results$res
}

continuous.fixed.is.feasible.for.funnel <- function () {
	TRUE
}
continuous.random.is.feasible.for.funnel <- function () {
	TRUE
}
