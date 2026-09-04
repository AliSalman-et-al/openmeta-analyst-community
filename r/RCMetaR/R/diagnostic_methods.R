# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

diagnostic.logit.metrics <- c("Sens", "Spec", "PPV", "NPV", "Acc")
diagnostic.log.metrics <- c("PLR", "NLR", "DOR")
bivariate.methods <- c("diagnostic.reitsma")

diagnostic.summary.metric.name <- function(metric) {
    if (trimws(as.character(metric)) == "DOR") {
        return("Odds Ratio")
    }
    pretty.metric.name(metric)
}

rcmetar.corrected.diagnostic.counts <- function(diagnostic.data, params) {
    values <- list(TP=diagnostic.data@TP, FN=diagnostic.data@FN,
                   TN=diagnostic.data@TN, FP=diagnostic.data@FP)
    if (length(values$TP) == 0) return(values)
    target <- if (!is.null(params$to)) as.character(params$to) else "only0"
    if (!is.null(params$correction.policy)) target <- as.character(params$correction.policy)
    target <- switch(target,
        "Studies with any zero cell"="only0",
        "All studies"="all",
        "All studies if any zero exists"="if0all",
        target
    )
    adjust <- if (!is.null(params$adjust)) as.numeric(params$adjust) else 0
    zero <- (values$TP * values$FN * values$TN * values$FP) == 0
    apply.correction <- switch(target,
        only0=zero,
        all=rep(TRUE, length(zero)),
        if0all=if (any(zero)) rep(TRUE, length(zero)) else rep(FALSE, length(zero)),
        rep(FALSE, length(zero))
    )
    for (name in names(values)) {
        values[[name]][apply.correction] <- values[[name]][apply.correction] + adjust
    }
    values
}

adjust.raw.data <- function(diagnostic.data, params) {
    rcmetar.corrected.diagnostic.counts(diagnostic.data, params)
}

compute.diag.point.estimates <- function(diagnostic.data, params) {
    if (length(diagnostic.data@TP) == 0) {
        if (length(diagnostic.data@y) > 0 && length(diagnostic.data@SE) > 0) {
            return(diagnostic.data)
        }
        stop("Diagnostic point estimates require either TP/FN/TN/FP counts or entered effect estimates and standard errors.")
    }

    data.adj <- adjust.raw.data(diagnostic.data, params)
    terms <- compute.diagnostic.terms(raw.data=data.adj, params)
    metric <- params$measure
    TP <- data.adj$TP
    FN <- data.adj$FN
    TN <- data.adj$TN
    FP <- data.adj$FP

    y <- terms$numerator / terms$denominator

    diagnostic.data@y <- diagnostic.transform.f(params$measure)$calc.scale(y)

    diagnostic.data@SE <- switch(metric,
        Sens = sqrt((1 / TP) + (1 / FN)),
        Spec = sqrt((1 / TN) + (1 / FP)),
        PPV = sqrt((1 / TP) + (1 / FP)),
        NPV = sqrt((1 / TN) + (1 / FN)),
        Acc = sqrt((1 / (TP + TN)) + (1 / (FP + FN))),
        PLR = sqrt((1 / TP) - (1 / (TP + FN)) + (1 / FP) - (1 / (TN + FP))),
        NLR = sqrt((1 / FN) - (1 / (TP + FN)) + (1 / TN) - (1 / (TN + FP))),
        DOR = sqrt((1 / TP) + (1 / FN) + (1 / FP) + (1 / TN)))


    diagnostic.data
}

compute.diagnostic.terms <- function(raw.data, params) {
    metric <- params$measure
    TP <- raw.data$TP
    FN <- raw.data$FN
    TN <- raw.data$TN
    FP <- raw.data$FP
    numerator <- switch(metric,
        Sens = TP,
        Spec = TN,
        PPV =  TP,
        NPV =  TN,
        Acc = TP + TN,
        PLR = TP * (TN + FP),
        NLR = FN * (TN + FP),
        DOR = TP * TN)

    denominator <- switch(metric,
        Sens = TP + FN,
        Spec = TN + FP,
        PPV =  TP + FP,
        NPV =  TN + FN,
        Acc = TP + TN + FP + FN,
        PLR = FP * (TP + FN),
        NLR = TN * (TP + FN),
        DOR = FP * FN)

    terms <- list("numerator"=numerator, "denominator"=denominator)
}

diagnostic.transform.f <- function(metric.str){
    display.scale <- function(x, ...){
        if (metric.str %in% diagnostic.log.metrics){
            exp(x)
        } else if (metric.str %in% diagnostic.logit.metrics) {
            invlogit(x)
        } else {
            x
        }
    }

    calc.scale <- function(x, ...){
        if (metric.str %in% diagnostic.log.metrics){
            log(x)
        } else if (metric.str %in% diagnostic.logit.metrics){
            logit(x)
        } else {
            x
        }
    }
    list(display.scale = display.scale, calc.scale = calc.scale)
}

get.res.for.one.diag.study <- function(diagnostic.data, params){
    if (length(diagnostic.data@y) == 0 || length(diagnostic.data@SE) == 0) {
        diagnostic.data <- compute.diag.point.estimates(diagnostic.data, params)
    }

    y <- diagnostic.data@y
    se <- diagnostic.data@SE

    mult <- get.mult.from.conf.level(params$conf.level)
    ub <- y + mult*se
    lb <- y - mult*se
    res <- list("b"=c(y), "ci.lb"=lb, "ci.ub"=ub, "se"=se)
    res
}

rcmetar.diagnostic.prepare <- function(diagnostic.data, params) {
    if (!is(diagnostic.data, "DiagnosticData")) stop("Diagnostic data expected.", call.=FALSE)
    compute.diag.point.estimates(diagnostic.data, params)
}

rcmetar.diagnostic.fit <- function(prepared.data, method, params) {
    if (!is(prepared.data, "DiagnosticData")) stop("Prepared diagnostic data expected.", call.=FALSE)
    if (!is.character(method) || length(method) != 1L || !nzchar(method))
        stop("Diagnostic method must be one method name.", call.=FALSE)
    .rcmetar.call.method(method, prepared.data, params)
}

rcmetar.diagnostic.extract <- function(fit, params) {
    if (!is.list(fit)) stop("Diagnostic authority result must be a list.", call.=FALSE)
    metric <- as.character(params$measure %||% "")
    summary.title <- paste(diagnostic.summary.metric.name(metric), "Summary", sep=" ")
    plot.title <- paste(diagnostic.summary.metric.name(metric), "Forest Plot", sep=" ")
    summary <- if (!is.null(fit$Summary)) stats::setNames(list(fit$Summary), summary.title) else list()
    images <- if (!is.null(fit$images)) stats::setNames(fit$images, plot.title) else character()
    plot.paths <- if (!is.null(fit$plot_params_paths)) stats::setNames(fit$plot_params_paths, plot.title) else character()
    capabilities <- fit$plot_capabilities %||% list()
    if (length(images) && !length(capabilities)) {
        capabilities <- stats::setNames(list(.rcmetar.plot.descriptor.for.kind(
            "forest", has.params=length(plot.paths) > 0)), names(images))
    }
    list(summary=summary, images=images, plot.paths=plot.paths,
         plot.names=fit$plot_names %||% character(),
         plot.capabilities=capabilities,
         references=fit$References %||% character(),
         image.order=fit$image_order %||% names(images))
}

rcmetar.diagnostic.report <- function(extracted, results, images, image.order,
                                      plot.names, plot.paths, plot.capabilities,
                                      references) {
    list(results=c(results, extracted$summary),
         images=c(images, extracted$images),
         image.order=c(image.order, extracted$image.order),
         plot.names=c(plot.names, extracted$plot.names),
         plot.params.paths=c(plot.paths, extracted$plot.paths),
         plot.capabilities=c(plot.capabilities, extracted$plot.capabilities),
         references=c(references, extracted$references))
}

multiple.diagnostic <- function(fnames, params.list, diagnostic.data) {

    results <- list()
    pretty.names <- diagnostic.fixed.inv.var.pretty.names()

    images <- c()
    image.order <- c()
    plot.names <- c()
    plot.params.paths <- c()
    plot.capabilities <- list()
    plot.pdfs.paths <- c()
    remove.indices <- c()
	references <- c()

    joint.index <- which(fnames == "diagnostic.reitsma")
    if (length(joint.index) > 1L) stop("Only one diagnostic.reitsma request is allowed; use joint.metrics for Sensitivity and Specificity.", call.=FALSE)
    if (length(joint.index) == 1L) {
            joint.params <- params.list[[joint.index]]
            joint.params$joint.metrics <- unique(c(
                unlist(strsplit(paste(as.character(joint.params$joint.metrics %||% character()), collapse=","), "[,[:space:]]+")),
                as.character(joint.params$measure %||% character())
            ))
            biv.results <- diagnostic.reitsma(diagnostic.data, joint.params)
            results <- c(results, biv.results$Summary)
            images <- c(images, biv.results$images)
            plot.names <- c(plot.names, biv.results$plot_names)
            plot.params.paths <- c(plot.params.paths, biv.results$plot_params_paths)
            plot.capabilities <- c(plot.capabilities, biv.results$plot_capabilities)
            image.order <- append.image.order(image.order, biv.results)
            remove.indices <- joint.index
			references <- c(references, biv.results$References)
    }

    fnames <- fnames[setdiff(1:length(fnames), remove.indices)]
    params.list <- params.list[setdiff(1:length(params.list), remove.indices)]



    if (length(params.list) > 0) {
        for (count in 1:length(params.list)) {
            prepared_diagnostic_data <- rcmetar.diagnostic.prepare(
                diagnostic.data, params.list[[count]])
            analysis_result <- rcmetar.diagnostic.fit(
                prepared_diagnostic_data, fnames[count], params.list[[count]])
            extracted <- rcmetar.diagnostic.extract(
                analysis_result, params.list[[count]])
            reported <- rcmetar.diagnostic.report(
                extracted, results, images, image.order, plot.names,
                plot.params.paths, plot.capabilities, references)
            results <- reported$results
            images <- reported$images
            image.order <- reported$image.order
            plot.names <- reported$plot.names
            plot.params.paths <- reported$plot.params.paths
            plot.capabilities <- reported$plot.capabilities
            references <- reported$references
        }
    }

    graphics.off()
    results <- c(results, list("images"=images,
					           "image_order"=image.order,
                               "plot_names"=plot.names,
                               "plot_params_paths"=plot.params.paths,
                               "plot_capabilities"=plot.capabilities,
							   "References"=rcmetar.unique.references(references)))
    results
}

append.image.order <- function(image.order, results){
    if ("image_order" %in% names(results)){
        image.order <- c(image.order, results[["image_order"]])
    } else{
        image.order <- c(image.order, names(results$images))
    }
    image.order
}

diagnostic.fixed.inv.var <- function(diagnostic.data, params){
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
    results <- NULL
    inference.method <- rcmetar.validate.inference.method(params, length(diagnostic.data@y))
    if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
        res <- get.res.for.one.diag.study(diagnostic.data, params)
        summary.disp <- list("MAResults" = res)
        results <- list("Summary"=summary.disp)
    } else {
        res<-rma.uni(yi=diagnostic.data@y, sei=diagnostic.data@SE,
                     slab=diagnostic.data@study.names,
                     method="FE", test=inference.method, level=params$conf.level,
                     digits=params$digits)
		res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
		res$study.names <- diagnostic.data@study.names
		res$study.years <- diagnostic.data@years
        model.title <- paste("Diagnostic Fixed-Effect Model - Inverse Variance (k = ", res$k, ")", sep="")
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        pretty.names <- diagnostic.fixed.inv.var.pretty.names()
        pretty.metric <- diagnostic.summary.metric.name(as.character(params$measure))
        for (count in 1:length(summary.disp$table.titles)) {
          summary.disp$table.titles[count] <- paste(" ", pretty.metric, " -", summary.disp$table.titles[count], sep="")
        }
        if ((is.null(params$write.to.file)) || params$write.to.file == TRUE) {
            results.path <- paste("./r_tmp/diag_fixed_inv_var_", params$measure, "_results.csv", sep="")
            write.results.to.file(diagnostic.data, params, res, outpath=results.path)
        }
        if ((is.null(params$create.plot)) || params$create.plot == TRUE) {
            forest.path <- paste(params$fp_outpath, sep="")
            plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
            changed.params <- plot.data$changed.params
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)

            plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
            images <- c("Forest Plot"=forest.path)
            plot.names <- c("forest plot"="forest_plot")


            results <- list("images"=images,
					        "Summary"=summary.disp,
                            "plot_names"=plot.names,
                            "plot_params_paths"=plot.params.paths)
        } else {
            results <- list("Summary"=summary.disp)
        }
    }

	references <- rcmetar.unique.references(c(
        rcmetar.method.references("rma.uni.fixed"),
        rcmetar.inference.method.references(params)))
	results[["References"]] <- references

    results
}

diagnostic.fixed.inv.var.parameters <- function(){
    apply_adjustment_to = c("only0", "all")

    params <- list("inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply_adjustment_to)

    defaults <- list("inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order = c("inference.method", "conf.level", "digits", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

diagnostic.fixed.inv.var.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Diagnostic Fixed-Effect Inverse Variance",
                         "description" = "Performs fixed-effect meta-analysis with inverse variance weighting.",
                         "inference.method"=rcmetar.inference.method.metadata(),
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero."),
                         "measure"=list("Sens"="Sensitivity", "Spec"="Specificity", "DOR"="Odds Ratio", "PLR"="Positive Likelihood Ratio",
                                        "NLR"="Negative Likelihood Ratio")
                          )
}

diagnostic.fixed.inv.var.is.feasible <- function(diagnostic.data, metric){
    metric %in% c("Sens", "Spec", "PLR", "NLR", "DOR")
}

diagnostic.fixed.inv.var.overall <- function(results) {
    res <- results$Summary$MAResults
}

diagnostic.fixed.mh <- function(diagnostic.data, params){
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
    results <- NULL
    if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
        res <- get.res.for.one.diag.study(diagnostic.data, params)
        summary.disp <- list("MAResults" = res)
        results <- list("Summary"=summary.disp)
    }
    else {
        counts <- rcmetar.corrected.diagnostic.counts(diagnostic.data, params)
        res <- switch(params$measure,

            "DOR" = rma.mh(ai=counts$TP, bi=counts$FN,
                                ci=counts$FP, di=counts$TN, slab=diagnostic.data@study.names,
                                level=params$conf.level, digits=params$digits, measure="OR",
                                add=c(0, 0), to=c("none", "none")),

            "PLR" = rma.mh(ai=counts$TP, bi=counts$FN,
                                ci=counts$FP, di=counts$TN, slab=diagnostic.data@study.names,
                                level=params$conf.level, digits=params$digits, measure="RR",
                                add=c(0, 0), to=c("none", "none")),

            "NLR" = rma.mh(ai=counts$FN, bi=counts$TP,
                                ci=counts$TN, di=counts$FP, slab=diagnostic.data@study.names,
                                level=params$conf.level, digits=params$digits, measure="RR",
                                add=c(0, 0), to=c("none", "none")))

		res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
		res$study.names <- diagnostic.data@study.names
		res$study.years <- diagnostic.data@years
        model.title <- "Diagnostic Fixed-Effect Model - Mantel-Haenszel"
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        pretty.names <- diagnostic.fixed.mh.pretty.names()
        pretty.metric <- diagnostic.summary.metric.name(as.character(params$measure))
        for (count in 1:length(summary.disp$table.titles)) {
          summary.disp$table.titles[count] <- paste(" ", pretty.metric, " -", summary.disp$table.titles[count], sep="")
        }
        if ((is.null(params$write.to.file)) || params$write.to.file == TRUE) {
            results.path <- paste("./r_tmp/diag_fixed_mh_", params$measure, "_results.csv", sep="")
            write.results.to.file(diagnostic.data, params, res, outpath=results.path)
        }
        if ((is.null(params$create.plot)) || (params$create.plot == TRUE)) {
            if (length(diagnostic.data@y) == 0 || length(diagnostic.data@SE) == 0) {
                diagnostic.data <- compute.diag.point.estimates(diagnostic.data, params)
            }
            forest.path <- paste(params$fp_outpath, sep="")
            plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
            changed.params <- plot.data$changed.params
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)

            plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
            images <- c("Forest Plot"=forest.path)
            plot.names <- c("forest plot"="forest_plot")
            results <- list("images"=images,
					        "Summary"=summary.disp,
                            "plot_names"=plot.names,
                            "plot_params_paths"=plot.params.paths)
        }
        else {
            results <- list("Summary"=summary.disp)
        }
    }

	references <- rcmetar.method.references("rma.mh")
	results[["References"]] <- references

    results
}

diagnostic.fixed.mh.parameters <- function(){
    apply_adjustment_to = c("only0", "all")

    params <- list("conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply_adjustment_to)

    defaults <- list("conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order = c("conf.level", "digits", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

diagnostic.fixed.mh.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Diagnostic Fixed-Effect Mantel-Haenszel",
                         "description" = "Performs fixed-effect meta-analysis using the Mantel-Haenszel method.",
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero."),
                          "measure"=list("Sens"="Sensitivity", "Spec"="Specificity", "DOR"="Odds Ratio", "PLR"="Positive Likelihood Ratio",
                                        "NLR"="Negative Likelihood Ratio")
                          )
}

diagnostic.fixed.mh.is.feasible <- function(diagnostic.data, metric){
    metric %in% c("DOR", "PLR", "NLR")
}

diagnostic.fixed.mh.overall <- function(results) {
    res <- results$Summary$MAResults
}

diagnostic.fixed.peto <- function(diagnostic.data, params){
  if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")

  if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
    res <- get.res.for.one.diag.study(diagnostic.data, params)
    summary.disp <- list("MAResults" = res)
    results <- list("Summary"=summary.disp)
  }
  else{
    res <- rma.peto(ai=diagnostic.data@TP, bi=diagnostic.data@FN,
                    ci=diagnostic.data@FP, di=diagnostic.data@TN,
					slab=diagnostic.data@study.names,
                    level=params$conf.level,
					digits=params$digits,
                    add=c(params$adjust, 0),
					to=c(as.character(params$to), "none"))
	res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
	res$study.names <- diagnostic.data@study.names
	res$study.years <- diagnostic.data@years

    diagnostic.data@y <- res$yi
    diagnostic.data@SE <- sqrt(res$vi)

    model.title <- "Diagnostic Fixed-Effect Model - Peto"
    summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
    pretty.names <- diagnostic.fixed.peto.pretty.names()
    pretty.metric <- diagnostic.summary.metric.name(as.character(params$measure))
    for (count in 1:length(summary.disp$table.titles)) {
      summary.disp$table.titles[count] <- paste(" ", pretty.metric, " -", summary.disp$table.titles[count], sep="")
    }
    results <- list("Summary"=summary.disp)

    if (is.null(params$create.plot) || params$create.plot == TRUE ||
        is.null(params$write.to.file) || params$write.to.file == TRUE) {
      if (length(diagnostic.data@y) == 0 || length(diagnostic.data@SE) == 0) {
        diagnostic.data <- compute.bin.point.estimates(diagnostic.data, params)
      }
      if (is.null(params$write.to.file) || params$write.to.file == TRUE) {
        res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
        results.path <- paste("./r_tmp/diagnostic_fixed_peto_results.csv")
        write.results.to.file(diagnostic.data, params, res, outpath=results.path)
      }
      if (is.null(params$create.plot) || params$create.plot == TRUE) {
        metric.name <- pretty.metric.name(as.character(params$measure))
        model.title <- "Diagnostic Fixed-Effect Model - Peto\n\nMetric: Odds Ratio"
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        forest.path <- paste(params$fp_outpath, sep="")
        plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
        changed.params <- c(changed.params, params.changed.in.forest.plot)
        params <- update.changed.plot.params(params, changed.params)
        forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)
        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Forest Plot"=forest.path)
        plot.names <- c("forest plot"="forest_plot")
        results <- list("images"=images,
				        "Summary"=summary.disp,
                        "plot_names"=plot.names,
						"plot_params_paths"=plot.params.paths)
      }
    }
  }

  references <- rcmetar.method.references("rma.peto")
  results[["References"]] <- references

  results
}

diagnostic.fixed.peto.parameters <- function(){
  apply_adjustment_to = c("only0", "all")

  params <- list( "conf.level"="float", "digits"="int",
                  "adjust"="float", "to"=apply_adjustment_to)

  defaults <- list("conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

  var_order = c("conf.level", "digits", "adjust", "to")

  parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

diagnostic.fixed.peto.pretty.names <- function() {
  pretty.names <- list("pretty.name"="Diagnostic Fixed-Effect Peto",
                       "description" = "Performs fixed-effect meta-analysis using the Peto method.",
                       "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
                       "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                       "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                       "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero.")
                         )
}

diagnostic.fixed.peto.is.feasible <- function(diagnostic.data, metric){
  metric == "DOR" &&
    length(diagnostic.data@TP)==length(diagnostic.data@FN) &&
    length(diagnostic.data@FN)==length(diagnostic.data@FP) &&
    length(diagnostic.data@FP)==length(diagnostic.data@TN) &&
    length(diagnostic.data@TP) > 0
}

diagnostic.fixed.peto.overall <- function(results) {
  res <- results$Summary$MAResults
}

diagnostic.random <- function(diagnostic.data, params){
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")

    results <- NULL
    inference.method <- rcmetar.validate.inference.method(params, length(diagnostic.data@y))
    if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
        res <- get.res.for.one.diag.study(diagnostic.data, params)
        summary.disp <- list("MAResults" = res)
        results <- list("Summary"=summary.disp)
    } else {
        res<-rma.uni(yi=diagnostic.data@y, sei=diagnostic.data@SE,
                 slab=diagnostic.data@study.names,
                 method=params$rm.method, test=inference.method, level=params$conf.level,
                 digits=params$digits)

		weights <- 1 / (res$vi + res$tau2)
        res$study.weights <- weights / sum(weights)
		res$study.names <- diagnostic.data@study.names
		res$study.years <- diagnostic.data@years

        model.title <- paste("Diagnostic Random-Effects Model (k = ", res$k, ")", sep="")
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        pretty.names <- diagnostic.random.pretty.names()
        pretty.metric <- diagnostic.summary.metric.name(as.character(params$measure))
        for (count in 1:length(summary.disp$table.titles)) {
            summary.disp$table.titles[count] <- paste(pretty.metric, " -", summary.disp$table.titles[count], sep="")
        }
        if ((is.null(params$write.to.file)) || params$write.to.file == TRUE) {
            results.path <- paste("./r_tmp/diag_random_", params$measure, "_results.csv", sep="")
            write.results.to.file(diagnostic.data, params, res, outpath=results.path)
        }
        if ((is.null(params$create.plot)) || (params$create.plot == TRUE)) {
            forest.path <- paste(params$fp_outpath, sep="")
            plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
            changed.params <- plot.data$changed.params
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)

            plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
            images <- c("Forest Plot"=forest.path)
            plot.names <- c("forest plot"="forest_plot")


            results <- list("images"=images,
					        "Summary"=summary.disp,
                            "plot_names"=plot.names,
                            "plot_params_paths"=plot.params.paths)
        }
        else {
            results <- list("Summary"=summary.disp)
        }
    }

	references <- rcmetar.unique.references(c(
        rcmetar.method.references("rma.uni.random"),
        rcmetar.inference.method.references(params)))
	results[["References"]] <- references

    results
}

diagnostic.random.parameters <- function(){
    apply.adjustment.to = c("only0", "all")
    rm.method.ls <- rcmetar.random.effects.methods()
    params <- list("rm.method"=rm.method.ls, "inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply.adjustment.to)

    defaults <- list("rm.method"="DL", "inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS,
                            "adjust"=.5, "to"="only0")

    var.order <- c("rm.method", "inference.method", "conf.level", "digits", "adjust", "to")
    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var.order)
}

diagnostic.random.pretty.names <- function() {
	rm_method_names <- rcmetar.random.effects.method.names()

    pretty.names <- list("pretty.name"="Diagnostic Random-Effects",
                         "description" = "Performs random-effects meta-analysis.",
                         "rm.method"=list("pretty.name"="Random-Effects method", "description"="Method for estimating between-studies heterogeneity", "rm.method.names"=rm_method_names),
                         "inference.method"=rcmetar.inference.method.metadata(),
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Correction factor target", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero."),
                         "measure"=list("Sens"="Sensitivity", "Spec"="Specificity", "DOR"="Odds Ratio", "PLR"="Positive Likelihood Ratio",
                                        "NLR"="Negative Likelihood Ratio")
                         )
}

diagnostic.random.is.feasible <- function(diagnostic.data, metric){
    metric %in% c("Sens", "Spec", "PLR", "NLR", "DOR")
}
diagnostic.random.overall <- function(results) {
    res <- results$Summary$MAResults
}
