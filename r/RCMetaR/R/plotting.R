# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

forest.plot.p.value.label <- function(p.value, digits, missing.label="") {
    if (display.value.is.missing(p.value)) {
        return(missing.label)
    }
    formatted <- format.p.value.display(p.value, digits)
    if (p.value < 10^(-digits)) {
        return(paste("P", formatted, sep=""))
    }
    paste("P=", formatted, sep="")
}

forest.plot.heterogeneity.suffix <- function(I2, QEp) {
    parts <- c()
    if (!display.value.is.missing(I2) && nzchar(I2)) {
        parts <- c(parts, paste("I\u00b2=", I2, sep=""))
    }
    if (!display.value.is.missing(QEp) && nzchar(QEp)) {
        parts <- c(parts, QEp)
    }
    if (length(parts) == 0) {
        return("")
    }
    paste(" (", paste(parts, collapse=", "), ")", sep="")
}

create.plot.data.generic <- function(om.data, params, res, selected.cov=NULL){

    scale.str <- get.scale(params)
    transform.name <- get.transform.name(om.data)
    plot.options <- set.plot.options(params)
    if (params$measure=="PFT" && length(om.data@g1O1) > 0 && length(om.data@g1O2) > 0) {
        n <- om.data@g1O1 + om.data@g1O2
    }
	else {
		n <- NULL
	}

    digits.str <- paste("%.", params$digits, "f", sep="")

    if (params$fp_plot_lb == "[default]") {
        plot.options$plot.lb <- params$fp_plot_lb
    } else {
        plot.lb <- rcmetar.numeric.values(params$fp_plot_lb)
        plot.options$plot.lb <- rcmetar.transform.by.name(transform.name, params$measure)$calc.scale(plot.lb, n)
    }

    if (params$fp_plot_ub == "[default]")  {
        plot.options$plot.ub <- params$fp_plot_ub
    } else {
        plot.ub <- rcmetar.numeric.values(params$fp_plot_ub)
        if (scale.str == "logit") {
          plot.ub <- min(1, plot.ub)
        }
        plot.options$plot.ub <- rcmetar.transform.by.name(transform.name, params$measure)$calc.scale(plot.ub, n)
    }

    tau2 <- sprintf(digits.str, res$tau2)
    degf <- res$k - 1
    QLabel =  paste("Q(df=", degf, ")", sep="")
    if (!is.null(res$QE)) {
      QE <- sprintf(digits.str, res$QE)
    } else {
      QE <- "NA"
    }
    if (!display.value.is.missing(res$I2)) {
        I2 <- paste(round(res$I2, digits = 2), "%", sep="")
    } else {
        I2 <- ""
    }
    QEp <- forest.plot.p.value.label(res$QEp, params$digits)

    overall <- paste("Overall", forest.plot.heterogeneity.suffix(I2, QEp), sep="")
    study.names <- rcmetar.study.labels(om.data)
    plot.data <- list(label = c(rcmetar.forest.study.header.label(params$fp_col1_str), study.names, overall),
                      types = c(3, rep(0, length(om.data@study.names)), 2),
                      scale = scale.str,
                      options = plot.options)
    y.overall <- res$b[1]
    lb.overall <- res$ci.lb[1]
    ub.overall <- res$ci.ub[1]
    y <- om.data@y
    study.ci.bounds <- calc.ci.bounds(om.data, params, ni=n)
    lb <- study.ci.bounds$lb
    ub <- study.ci.bounds$ub



	transform <- rcmetar.transform.by.name(transform.name, params$measure)
	y.disp <- transform$display.scale(y, ni=n)
	lb.disp <- transform$display.scale(lb, ni=n)
	ub.disp <- transform$display.scale(ub, ni=n)

	y.overall.disp <- transform$display.scale(y.overall, ni=n)
	lb.overall.disp <- transform$display.scale(lb.overall, ni=n)
	ub.overall.disp <- transform$display.scale(ub.overall, ni=n)

    y <- c(y, y.overall)
    lb <- c(lb, lb.overall)
    ub <- c(ub, ub.overall)

    y.disp <- c(y.disp, y.overall.disp)
    lb.disp <- c(lb.disp, lb.overall.disp)
    ub.disp <- c(ub.disp, ub.overall.disp)

    effects.disp <- list(y.disp=y.disp, lb.disp=lb.disp, ub.disp=ub.disp)
    plot.data$effects.disp <- effects.disp


    if (!metric.is.log.scale(params$measure)) {
        y <- y.disp
        lb <- lb.disp
        ub <- ub.disp
    }

    effects <- list(ES = y,
                    LL = lb,
                    UL = ub)
    plot.data$effects <- effects
    plot.range <- calc.plot.range(effects, plot.options)

    if (metric.is.log.scale(params$measure)) {
        plot.range.disp.lower <- transform$display.scale(plot.range[1])
        plot.range.disp.upper <- transform$display.scale(plot.range[2])
    } else {
        plot.range.disp.lower <- plot.range[1]
        plot.range.disp.upper <- plot.range[2]
    }
    plot.data$plot.range <- plot.range
    changed.params <- plot.options$changed.params
    if (plot.options$plot.lb != plot.range.disp.lower) {
        changed.params$fp_plot_lb <- plot.range.disp.lower
    }
    if (plot.options$plot.ub != plot.range.disp.upper) {
        changed.params$fp_plot_ub <- plot.range.disp.upper
    }
    plot.data$changed.params <- changed.params

    if (!is.null(selected.cov)){
        cov.val.str <- paste("om.data@covariates$", selected.cov, sep="")
        cov.values <- om.data@covariates[[selected.cov]]
        plot.data$covariate <- list(varname = selected.cov,
                                   values = cov.values)
    }
    plot.data
}

create.plot.data.binary <- function(binary.data, params, res, selected.cov = NULL){

    plot.data <- create.plot.data.generic(binary.data, params, res, selected.cov=selected.cov)
    if (length(binary.data@g1O1) > 0)  {

        plot.data$col3 <- list(nums = binary.data@g1O1, denoms = binary.data@g1O1 + binary.data@g1O2)
    }

    if (length(binary.data@g2O1) > 0) {
         plot.data$col4 <- list(nums = binary.data@g2O1, denoms = binary.data@g2O1 + binary.data@g2O2)
    }

    if (rcmetar.metafor.binary.default.supported(binary.data, params, selected.cov=selected.cov)) {
        plot.data <- rcmetar.build.binary.metafor.bundle(binary.data, params, res)
    }

    plot.data
}

create.plot.data.diagnostic <- function(diagnostic.data, params, res, selected.cov = NULL){

    plot.data <- create.plot.data.generic(diagnostic.data, params, res, selected.cov=selected.cov)
    plot.options <- plot.data$plot.options
    plot.options$show.y.axis <- FALSE
    changed.params <- plot.data$changed.params
    if (length(diagnostic.data@TP) > 0) {
        raw.data <- list("TP"=diagnostic.data@TP, "FN"=diagnostic.data@FN, "TN"=diagnostic.data@TN, "FP"=diagnostic.data@FP)
        terms <- compute.diagnostic.terms(raw.data, params)
        plot.data$col3 <- list(nums=terms$numerator, denoms=terms$denominator)

        metric <- params$measure
        label <- switch(metric,
        Sens = "TP/(TP + FN)",
        Spec = "TN/(FP + TN)",
        PPV =  "TP/(TP + FP)",
        NPV =  "TN/(TN + FN)",
        Acc = "(TP + TN)/Tot",
        PLR = "(TP * Di-)/(FP * Di+)",
        NLR = "(FN * Di-)/(TN * Di+)",
        DOR = "(TP * TN)/(FP * FN)")

        plot.data$options$col3.str <- label
        changed.params$fp_col3_str <- label
        plot.data$changed.params <- changed.params
    }
    if (rcmetar.metafor.diagnostic.default.supported(diagnostic.data, params, selected.cov=selected.cov)) {
        plot.data <- rcmetar.build.diagnostic.metafor.bundle(diagnostic.data, params, res)
    }
    plot.data
}

create.plot.data.continuous <- function(cont.data, params, res, selected.cov = NULL){
    plot.data <- create.plot.data.generic(cont.data, params, res, selected.cov=selected.cov)
    if (rcmetar.metafor.continuous.default.supported(cont.data, params, selected.cov=selected.cov)) {
        plot.data <- rcmetar.build.continuous.metafor.bundle(cont.data, params, res)
    }
    plot.data
}

create.plot.data.overall <- function(om.data, params, res, res.overall){
    scale.str <- get.scale(params)
    if (params$measure=="PFT" && length(om.data@g1O1) > 1 && length(om.data@g1O2)) {
        n <- om.data@g1O1 + om.data@g1O2
    }
	else {
	    n <- NULL
	}

    transform.name <- get.transform.name(om.data)
    plot.options <- set.plot.options(params)
    plot.options$show.col3 <- FALSE
    plot.options$show.col4 <- FALSE

    if (params$fp_plot_lb == "[default]") {
        plot.options$plot.lb <- params$fp_plot_lb
    } else {
        plot.lb <- rcmetar.numeric.values(params$fp_plot_lb)
        plot.options$plot.lb <- rcmetar.transform.by.name(transform.name, params$measure)$calc.scale(plot.lb, n)
    }
    if (params$fp_plot_ub == "[default]") {
        plot.options$plot.ub <- params$fp_plot_ub
    } else {
        plot.ub <- rcmetar.numeric.values(params$fp_plot_ub)
        plot.options$plot.ub <- rcmetar.transform.by.name(transform.name, params$measure)$calc.scale(plot.ub, n)
    }
    if (metric.is.log.scale(params$measure)) {
        plot.options$show.y.axis <- FALSE
    } else {
        plot.options$show.y.axis <- TRUE
    }

    plot.data <- list( scale = scale.str,
                       options = plot.options)
    y <- NULL
    lb <- NULL
    ub <- NULL

    for (count in 1:length(res)) {
      y <- c(y, res[[count]]$b)
      lb <- c(lb, res[[count]]$ci.lb)
      ub <- c(ub, res[[count]]$ci.ub)
    }

    transform <- rcmetar.transform.by.name(transform.name, params$measure)
    y.disp <- transform$display.scale(y, n)
    lb.disp <- transform$display.scale(lb, n)
    ub.disp <- transform$display.scale(ub, n)
    effects.disp <- list(y.disp=y.disp, lb.disp=lb.disp, ub.disp=ub.disp)
    plot.data$effects.disp <- effects.disp

    if (!metric.is.log.scale(params$measure)) {
        y <- y.disp
        lb <- lb.disp
        ub <- ub.disp
    }

    effects <- list(ES = y,
                    LL = lb,
                    UL = ub)
    plot.data$effects <- effects
    plot.range <- calc.plot.range(effects, plot.options)
    plot.data$plot.range <- plot.range
        plot.range.disp.lower <- transform$display.scale(plot.range[1], n)
        plot.range.disp.upper <- transform$display.scale(plot.range[2], n)
    changed.params <- plot.options$changed.params
    if (plot.options$plot.lb != plot.range.disp.lower) {
        changed.params$fp_plot_lb <- plot.range.disp.lower
    }
    if (plot.options$plot.ub != plot.range.disp.upper) {
        changed.params$fp_plot_ub <- plot.range.disp.upper
    }
    if (metric.is.log.scale(params$measure)) {
        plot.data$summary.est <- res.overall$b[1]
    } else {
        plot.data$summary.est <- transform$display.scale(res.overall$b[1], n)
    }
    plot.data$changed.params <- changed.params
    plot.data
}

create.plot.data.cum <- function(om.data, params, res) {
    params$show_col1 <- 'FALSE'
    res.overall <- res[[length(res)]]
    plot.data <- create.plot.data.overall(om.data, params, res, res.overall)

    study.names <- c()
    study.names <- paste("  ", om.data@study.names[1], sep="")
    for (count in 2:length(om.data@study.names)) {
        study.names <- c(study.names, paste("+ ",om.data@study.names[count], sep=""))
    }
    display_effects <- plot.data$effects.disp
    display_estimates <- display_effects$y.disp
    display_lower_bounds <- display_effects$lb.disp
    display_upper_bounds <- display_effects$ub.disp
    last.index <- length(display_estimates)
    display_estimates <- c(display_estimates, display_estimates[last.index])
    display_lower_bounds <- c(display_lower_bounds, display_lower_bounds[last.index])
    display_upper_bounds <- c(display_upper_bounds, display_upper_bounds[last.index])
    effects.disp <- list("y.disp"=display_estimates, "lb.disp"=display_lower_bounds, "ub.disp"=display_upper_bounds)
    plot.data$effects.disp <- effects.disp

    effects <- plot.data$effects
    estimates <- effects$ES
    lower_bounds <- effects$LL
    upper_bounds <- effects$UL
    last.index <- length(estimates)
    estimates <- c(estimates, estimates[last.index])
    lower_bounds <- c(lower_bounds, lower_bounds[last.index])
    upper_bounds <- c(upper_bounds, upper_bounds[last.index])
    effects <- list("ES"=estimates, "LL"=lower_bounds, "UL"=upper_bounds)
    plot.data$effects<- effects
    plot.data$types <- c(3, rep(0, length(study.names)), 4)
    study.names <- c(study.names, "")
    plot.data$label <- c(rcmetar.forest.study.header.label(params$fp_col1_str), study.names)
    plot.data
}

create.plot.data.loo <- function(om.data, params, res) {
    res.overall <- res[[1]]
    study.names <- c("Overall", paste("- ", om.data@study.names, sep=""))
    plot.data <- create.plot.data.overall(om.data, params, res, res.overall)
    plot.data$label <- c(rcmetar.forest.study.header.label(params$fp_col1_str), study.names)
    plot.data$types <- c(3, 5, rep(0, length(om.data@study.names)))
    plot.data
}

create.subgroup.plot.data.generic <- function(subgroup.data, params, data.type, selected.cov=NULL) {

    grouped.data <- subgroup.data$grouped.data
    res <- subgroup.data$results
    subgroup.list <- subgroup.data$subgroup.list
    scale.str <- get.scale(params)
    sample_sizes <- NULL
    all_study_sample_sizes <- NULL

    if (data.type == "continuous") {
      transform.name <- "continuous.transform.f"
    } else if (data.type == "diagnostic") {
      transform.name <- "diagnostic.transform.f"
    }  else if (data.type == "binary") {
      transform.name <- "binary.transform.f"
    }
    y <- NULL
    lb <- NULL
    ub <- NULL
    labels <- NULL
    types <- NULL
    mult <- get.mult.from.conf.level(params$conf.level)

    for (i in seq_along(subgroup.list)){
        subgroup_result <- res[[i]]
        subgroup_overall_effect <- subgroup_result$b[1]
        subgroup_overall_lower <- subgroup_result$ci.lb[1]
        subgroup_overall_upper <- subgroup_result$ci.ub[1]
        subgroup_effects <- grouped.data[[i]]@y
        subgroup_lower <- subgroup_effects - mult*grouped.data[[i]]@SE
        subgroup_upper <- subgroup_effects + mult*grouped.data[[i]]@SE
        if (params$measure == "PFT") {
            current_sample_sizes <- grouped.data[[i]]@g1O1 + grouped.data[[i]]@g1O2
            all_study_sample_sizes <- c(all_study_sample_sizes, current_sample_sizes)
            sample_sizes <- c(sample_sizes, current_sample_sizes, sum(current_sample_sizes))
        }
        y <- c(y, subgroup_effects, subgroup_overall_effect)
        lb <- c(lb, subgroup_lower, subgroup_overall_lower)
        ub <- c(ub, subgroup_upper, subgroup_overall_upper)

        if (!display.value.is.missing(subgroup_result$I2)) {
            I2 <- paste(round(subgroup_result$I2, digits = 2), "%", sep="")
        } else {
            I2 <- ""
        }
        QEp <- forest.plot.p.value.label(subgroup_result$QEp, params$digits)

        overall <- forest.plot.heterogeneity.suffix(I2, QEp)
        types <- c(types, rep(0, length(grouped.data[[i]]@study.names)), 1)
        labels <- c(labels, grouped.data[[i]]@study.names, paste("Subgroup ", subgroup.list[i], overall, sep=""))
    }
    overall_result <- res[[length(subgroup.list) + 1]]
    overall_effect <- overall_result$b[1]
    overall_lower <- overall_result$ci.lb[1]
    overall_upper <- overall_result$ci.ub[1]
    y <- c(y, overall_effect)
    lb <- c(lb, overall_lower)
    ub <- c(ub, overall_upper)
    if (params$measure == "PFT") {
        sample_sizes <- c(sample_sizes, sum(all_study_sample_sizes))
    }
    n <- if (params$measure == "PFT") sample_sizes else NULL
    types <- c(3,types, 2)
    if (!display.value.is.missing(overall_result$I2)) {
        I2 <- paste(round(overall_result$I2, digits = 2), "%", sep="")
    } else {
        I2 <- ""
    }
    QEp <- forest.plot.p.value.label(overall_result$QEp, params$digits)
    overall <- forest.plot.heterogeneity.suffix(I2, QEp)
    labels <- c(rcmetar.forest.study.header.label(params$fp_col1_str), labels, paste("Overall", overall, sep=""))
    plot.options <- set.plot.options(params)
    if (params$fp_plot_lb == "[default]") {
        plot.options$plot.lb <- params$fp_plot_lb
    } else {
        plot.lb <- rcmetar.numeric.values(params$fp_plot_lb)
        plot.options$plot.lb <- rcmetar.transform.by.name(transform.name, params$measure)$calc.scale(plot.lb, n)
    }
    if (params$fp_plot_ub == "[default]") {
        plot.options$plot.ub <- params$fp_plot_ub
    } else {
        plot.ub <- rcmetar.numeric.values(params$fp_plot_ub)
        plot.options$plot.ub <- rcmetar.transform.by.name(transform.name, params$measure)$calc.scale(plot.ub, n)
    }

    plot.data <- list(label = labels,
                      types=types,
                      scale = scale.str,
                      options = plot.options)
    transform <- rcmetar.transform.by.name(transform.name, params$measure)
    y.disp <- transform$display.scale(y, n)
    lb.disp <- transform$display.scale(lb, n)
    ub.disp <- transform$display.scale(ub, n)

    effects.disp <- list(y.disp=y.disp, lb.disp=lb.disp, ub.disp=ub.disp)
    plot.data$effects.disp <- effects.disp

    if (!metric.is.log.scale(params$measure)) {
        y <- y.disp
        lb <- lb.disp
        ub <- ub.disp
    }

    effects <- list(ES = y,
                    LL = lb,
                    UL = ub)

    plot.data$effects <- effects
    plot.range <- calc.plot.range(effects, plot.options)
    plot.data$plot.range <- plot.range
        plot.range.disp.lower <- transform$display.scale(plot.range[1], n)
        plot.range.disp.upper <- transform$display.scale(plot.range[2], n)
    changed.params <- plot.options$changed.params
    if (plot.options$plot.lb != plot.range.disp.lower) {
        changed.params$fp_plot_lb <- plot.range.disp.lower
    }
    if (plot.options$plot.ub != plot.range.disp.upper) {
        changed.params$fp_plot_ub <- plot.range.disp.upper
    }
    plot.data$changed.params <- changed.params

    if (!is.null(selected.cov)){
        selected_covariate <- as.character(selected.cov)
        covariate_index <- match(
            selected_covariate,
            vapply(grouped.data[[1]]@covariates, function(covariate) covariate@cov.name, character(1))
        )
        if (is.na(covariate_index)) {
            stop("Selected covariate was not found in subgroup data.", call.=FALSE)
        }
        cov.values <- unlist(lapply(
            grouped.data,
            function(data) data@covariates[[covariate_index]]@cov.vals
        ), use.names=FALSE)
        plot.data$covariate <- list(varname = selected_covariate,
                                   values = cov.values)
    }
    plot.data
}

create.subgroup.plot.data.binary <- function(subgroup.data, params) {
    grouped.data <- subgroup.data$grouped.data
    plot.data <- create.subgroup.plot.data.generic(subgroup.data, params, data.type="binary")

    if (length(grouped.data[[1]]@g1O1) > 0) {

        plot.data$col3 <- list(nums = subgroup.data$col3.nums, denoms = subgroup.data$col3.denoms)
    }

    if (length(grouped.data[[1]]@g2O1) > 0) {
         plot.data$col4 <- list(nums = subgroup.data$col4.nums, denoms = subgroup.data$col4.denoms)
    }
    plot.data
}

create.subgroup.plot.data.diagnostic <- function(subgroup.data, params) {
    grouped.data <- subgroup.data$grouped.data
    plot.data <- create.subgroup.plot.data.generic(subgroup.data, params, data.type="diagnostic")
    if (length(grouped.data[[1]]@TP) > 0) {
        plot.data$col3 <- list(nums = subgroup.data$col3.nums, denoms = subgroup.data$col3.denoms)

        metric <- params$measure
        label <- switch(metric,
        Sens = "TP / (TP + FN)",
        Spec = "TN / (FP + TN)",
        PPV =  "TP / (TP + FP)",
        NPV =  "TN / (TN + FN)",
        Acc = "(TP + TN) / Tot",
        PLR = "(TP * Di-) / (FP * Di+)",
        NLR = "(FN * Di-) / (TN * Di+)",
        DOR = "(TP * TN) / (FP * FN")
        plot.data$options$col3.str <- label
    }
    plot.data
}

create.subgroup.plot.data.cont <- function(subgroup.data, params) {
    grouped.data <- subgroup.data$grouped.data
    plot.data <- create.subgroup.plot.data.generic(subgroup.data, params, data.type="continuous")
}

create.plot.data.reg <- function(reg.data, params, fitted.line, selected.cov=NULL, res=NULL) {
     if (!inherits(res, "rma")) {
         stop("Meta-regression bubble plots require a metafor rma result.", call.=FALSE)
     }
     cov.index <- 1
     if (!is.null(selected.cov)) {
         cov.names <- vapply(reg.data@covariates, function(covariate) covariate@cov.name, character(1))
         match.index <- match(as.character(selected.cov), cov.names)
         if (!is.na(match.index)) {
             cov.index <- match.index
         }
     }
     covariate <- reg.data@covariates[[cov.index]]
     rcmetar.create.metafor.bubble.bundle(
         reg.data=reg.data,
         params=params,
         res=res,
         cov.name=covariate@cov.name,
         cov.values=covariate@cov.vals,
         fitted.line=fitted.line
     )
}



set.plot.options <- function(params) {
    params <- rcmetar.normalize.plot.text.params(params)
    plot.options <- list()
    changed.params <- list()
    if (params$fp_xticks[1] == '[default]') {
        plot.options$xticks <- NA
    } else if (is.vector(params$fp_xticks)) {
        plot.options$xticks <- params$fp_xticks
    } else {
        plot.options$xticks <- rcmetar.numeric.values(params$fp_xticks)
    }
    if (params$fp_show_col1=='TRUE') {
      plot.options$show.study.col <- TRUE
    } else {
      plot.options$show.study.col <- FALSE
    }
    plot.options$col1.str <- rcmetar.forest.study.header.label(params$fp_col1_str)

    if (params$fp_show_col2=='TRUE') {
      plot.options$show.col2 <- TRUE
    } else {
      plot.options$show.col2 <- FALSE
    }
    if (params$fp_col2_str == "[default]") {
        col2.str <- paste("Estimate (", params$conf.level, "% C.I.)", sep="")
        plot.options$col2.str <- col2.str
        changed.params$fp_col2_str <- col2.str
    } else {
        plot.options$col2.str <- as.character(params$fp_col2_str)
    }

    if (params$fp_show_col3=='TRUE') {
      plot.options$show.col3 <- TRUE
    } else {
      plot.options$show.col3 <- FALSE
    }
    if (!is.null(params$fp_col3_str)) {
       plot.options$col3.str <- as.character(params$fp_col3_str)
    }
    if ((params$fp_show_col4=='TRUE') && (!as.character(params$measure) %in% c("PR", "PLN", "PLO", "PAS", "PFT"))) {
      plot.options$show.col4 <- TRUE
    } else {
      plot.options$show.col4 <- FALSE
    }
    if (!is.null(params$fp_col4_str)) {
       plot.options$col4.str <- as.character(params$fp_col4_str)
    }

    if (rcmetar.is.plot.default.text(params$fp_xlabel)) {
        xlabel <- pretty.metric.name(as.character(params$measure))
        if (metric.is.log.scale(params$measure)) {
            xlabel <- paste(xlabel, " (log scale)", sep="")
        }
        plot.options$xlabel <- xlabel
        changed.params$fp_xlabel <- xlabel
    } else {
        plot.options$xlabel <- as.character(params$fp_xlabel)
    }

    if (is.null(params$fp.title)) {
         plot.options$fp.title <- ""
    } else {
         plot.options$fp.title <- params$fp.title
    }

    if (params$fp_show_summary_line=='TRUE') {
      plot.options$show.summary.line <- TRUE
    } else {
      plot.options$show.summary.line <- FALSE
    }
    plot.options$show.y.axis <- TRUE

    plot.options$digits <- params$digits
    plot.options$changed.params <- changed.params
    plot.options
}

calc.plot.range <- function(effects, plot.options) {
    effect.size.min <- min(effects$ES)
    effect.size.max <- max(effects$ES)
    user.lb <- plot.options$plot.lb
    user.ub <- plot.options$plot.ub
    if (user.lb != "[default]") {
        if (user.lb > effect.size.min) {
          user.lb <- "[default]"
        }
    }
    if (user.ub != "[default]") {
        if (plot.options$plot.ub < effect.size.max) {
          user.ub <- "[default]"
        }
    }
    plot.range <- c()
    if (user.lb == "[default]" || user.ub == "[default]") {
        effect.size.width <- effect.size.max - effect.size.min

        effects.max <- max(effects$UL)
        effects.min <- min(effects$LL)
        arrow.factor <- 2
        plot.ub <- min(effects.max, effect.size.max + arrow.factor * effect.size.width)
        plot.lb <- max(effects.min, effect.size.min - arrow.factor * effect.size.width)

        plot.range <- c(plot.lb, plot.ub)
    }
    if (user.lb != "[default]") {
        plot.range[1] <- user.lb
    }
    if (user.ub != "[default]") {
        plot.range[2] <- user.ub
    }
    plot.range
}

pretty.metric.name <- function(metric) {
  metric.names <- list(
    OR = "Odds Ratio",
    RD = "Risk Difference",
    MD = "Mean Difference",
    SMD = "Standardized Mean Difference",
    RR = "Risk Ratio",
    AS = "Arcsine Difference",
    PR = "Proportion",
    PLN = "Natural Logarithm transformed Proportion",
    PLO = "Logit Proportion",
    PAS = "Arcsine transformed Proportion",
    PFT  = "Freeman-Tukey transformed Proportion",
    PETO = "Peto",
    YUQ = "Yule's Q",
    YUY = "Yule's Y",
    Sens = "Sensitivity",
    Spec = "Specificity",
    PPV =  "Positive Predictive Value",
    NPV =  "Negative Predictive Value",
    Acc = "Accuracy",
    PLR = "Positive Likelihood Ratio",
    NLR = "Negative Likelihood Ratio",
    DOR = "Diagnostic Odds Ratio",
    TXMean = "TX Mean",
    GEN = "Generic Effect")

  metric.key <- gsub("[[:space:].]+", "", trimws(metric))
  metric.name <- metric.names[[metric.key]]
  if (is.null(metric.name) && metric %in% unlist(metric.names, use.names=FALSE)) {
    metric.name <- metric
  }

  metric.name
}


meta.regression.plot <- function(plot.data, outpath, ...) {
    if (!rcmetar.is.metafor.bubble.bundle(plot.data)) {
        stop("Meta-regression bubble plots require a metafor-backed plot bundle.", call.=FALSE)
    }
    rcmetar.draw.metafor.bubble(plot.data, outpath)
}

sroc.plot <- function(plot.data, outpath){
	png(filename=rcmetar.scratch.path("INTER"))

    lcol <- "blue"
    sym.size <- .03
    lweight = 1
    lpatern = "solid"
    plotregion = "n"
    fitted.line <- plot.data$fitted.line
    weighted <- plot.data$weighted
    TPR <- plot.data$TPR
    FPR <- plot.data$FPR
    xlab="1 - Specificity"
    ylab="Sensitivity"
    s.range <- plot.data$s.range
    if (length(grep(".png", outpath)) != 0){
        png(filename=outpath, height=5, width=5, units="in", res=144)
    } else {
        pdf(file=outpath, height=5, width=5)
    }
    plot(y = NULL, x=NULL, xlim=c(0, 1),
                           ylim=c(0, 1),
                           xlab=xlab,
                           ylab=ylab,
                           asp=1,
                           type='n')
    symbols(y = plot.data$TPR, x = plot.data$FPR,
              bty = plotregion, circles=rep(1, length(TPR)), col = "black", inches=sym.size, add=TRUE)

    s.vals <- seq(from = s.range$min, to = s.range$max, by=.001)
    reg.line.vals <- fitted.line$intercept + fitted.line$slope * s.vals
    std.err <- plot.data$std.err
    mult <- plot.data$mult
    upper.ci.vals <- reg.line.vals + mult * std.err
    lower.ci.vals <- reg.line.vals - mult * std.err
    reg.line.vals.trans <- invlogit((s.vals + reg.line.vals) / 2)
    s.vals.trans <- invlogit((s.vals - reg.line.vals) / 2)

    lines(s.vals.trans, reg.line.vals.trans, col = lcol, lwd = lweight, lty = lpatern)
    upper.ci.vals.trans <- invlogit((s.vals + upper.ci.vals))
    lower.ci.vals.trans <- invlogit((s.vals + lower.ci.vals))
    graphics.off()
}


compute.ppv <- function(sens, spec, prev) {
  npv <- sens * prev / (sens * prev + (1 - spec) * (1 - prev))
}

compute.npv <- function(sens, spec, prev) {
  ppv <- spec * (1 - prev) / (spec * (1 - prev) + (1 - sens) * prev)
}

plot.ppv.npv.by.prev <- function(diagnostic.data, params) {
  params$measure <- "Sens"
  diagnostic.data.sens <- compute.diag.point.estimates(diagnostic.data, params)
  params$measure <- "Spec"
  diagnostic.data.spec <- compute.diag.point.estimates(diagnostic.data, params)
  params$measure <- "NPV"
  diagnostic.data.npv <- compute.diag.point.estimates(diagnostic.data, params)
  params$measure <- "PPV"
  diagnostic.data.ppv <- compute.diag.point.estimates(diagnostic.data, params)

  prev <- ((diagnostic.data@TP + diagnostic.data@FN) /
              (diagnostic.data@TP + diagnostic.data@FN + diagnostic.data@FP + diagnostic.data@TN))
  prev.min <- min(prev)
  prev.max <- max(prev)
  npv <- diagnostic.data.npv@y
  npv <- diagnostic.transform.f("NPV")$display.scale(npv)
  ppv <- diagnostic.data.ppv@y
  ppv <- diagnostic.transform.f("PPV")$display.scale(ppv)

  plot(0:1, 0:1, type="n",main="PPV and NPV by Prevalence", xlab="Prevalence", ylab="")
  points(prev, npv, col=3,)
  points(prev, ppv, col=4)
  legend("right", c("Negative predictive value", "Positive predictive value"), bty="n", col=c(3,4), text.col=c(3,4), pch=c(1,1))

  res.sens <- rma.uni(yi=diagnostic.data.sens@y, sei=diagnostic.data.sens@SE,
                     slab=diagnostic.data.sens@study.names,
                     method="FE", level=params$conf.level,
                     digits=params$digits)
  res.spec <- rma.uni(yi=diagnostic.data.spec@y, sei=diagnostic.data.spec@SE,
                     slab=diagnostic.data.spec@study.names,
                     method="FE", level=params$conf.level,
                     digits=params$digits)
  sens.est <- diagnostic.transform.f("Sens")$display.scale(res.sens$b[1])
  spec.est <- diagnostic.transform.f("Spec")$display.scale(res.spec$b[1])
  prev.overall <- seq(from=prev.min, to=prev.max, by=.01)
  sens.overall <- rep(sens.est, length(prev.overall))
  spec.overall <- rep(spec.est, length(prev.overall))
  npv.overall <- compute.npv(sens.overall, spec.overall, prev.overall)
  ppv.overall <- compute.ppv(sens.overall, spec.overall, prev.overall)
  lines(prev.overall, npv.overall, col=3)
  lines(prev.overall, ppv.overall, col=4)
}

format.data.cols <- function(plot.data) {
  options <- plot.data$options
  types <- plot.data$types
  if (options$show.col2==TRUE) {

        y.disp <- plot.data$effects.disp$y.disp
        lb.disp <- plot.data$effects.disp$lb.disp
        ub.disp <- plot.data$effects.disp$ub.disp
        effect.sizes <- format.effect.sizes(y=y.disp, lb=lb.disp, ub=ub.disp, options)
        effect.size.label <- create.effect.size.label(effect.sizes, options)
        effect.size.col <- c(effect.size.label,
                             paste(effect.sizes$y.display, effect.sizes$lb.display, ",",
                                   effect.sizes$ub.display, ")", sep = ""))
        effect.size.col[types==4] <- ""
        plot.data$additional.col.data$es <- effect.size.col
  }
  if ((options$show.col3==TRUE) && (!is.null(plot.data$col3))) {
        label <- options$col3.str
        data.col <- format.raw.data.col(nums = plot.data$col3$nums, denoms = plot.data$col3$denoms, label = label, types=types)
        plot.data$additional.col.data$cases = data.col
  }
  if ((options$show.col4==TRUE) && (!is.null(plot.data$col4))) {
        label <- options$col4.str
        data.col <- format.raw.data.col(nums = plot.data$col4$nums, denoms = plot.data$col4$denoms, label = label, types=types)
        plot.data$additional.col.data$controls = data.col
  }
  plot.data
}

format.effect.sizes <- function(y, lb, ub, options) {
  digits <- options$digits
  y.display <- sprintf(paste("%.", digits,"f", sep=""), y)
  lb.display <- sprintf(paste("%.", digits,"f", sep=""), lb)
  ub.display <- sprintf(paste("%.", digits,"f", sep=""), ub)

  if (length(ub.display[ub.display >= 0])) {
    ub.display[ub.display >= 0] <- mapply(pad.with.spaces, ub.display[ub.display >= 0], begin.num=1, end.num=0)
  }
  ub.max.chars <- max(nchar(ub.display))
  ub.extra.space <- ub.max.chars - nchar(ub.display)
  ub.display <- mapply(pad.with.spaces, ub.display, begin.num = ub.extra.space, end.num=0)
  if (length(ub.display[ub.display >= 0])) {
    ub.display[ub.display >= 0] <- mapply(pad.with.spaces, ub.display[ub.display >= 0], begin.num=1, end.num=0)
  }
  if (min(ub) < 0) {
    ub.display <- paste(" ", ub.display, sep="")
  }
  lb.display <- paste(" (", lb.display, sep="")
  lb.max.chars <- max(nchar(lb.display))
  lb.extra.space <- lb.max.chars - nchar(lb.display)
  lb.display <- mapply(pad.with.spaces, lb.display, begin.num = lb.extra.space, end.num=0)
  effect.sizes <- list("y.display"=y.display, "lb.display"=lb.display, "ub.display"=ub.display)
}

create.effect.size.label <- function(effect.sizes, options) {
   col2.label <- as.character(options$col2.str)
   label.info <- check.label(label = col2.label, split.str = ",")
   max.chars <- max(nchar(effect.sizes$ub.display)) + 1
   if (label.info$contains.symbol == TRUE) {
     col2.label.padded <- pad.with.spaces(col2.label, begin.num=0, end.num = max.chars - label.info$end.string.length)
   } else {
     col2.width <- max(nchar(effect.sizes$y.disp) + nchar(effect.sizes$lb.disp) + nchar(effect.sizes$ub.disp))
     if (col2.width > nchar(col2.label)) {
       col2.label.padded <- pad.with.spaces(col2.label, begin.num=0, end.num = floor((col2.width - nchar(col2.label)) / 2))
     } else {
       col2.label.padded <- col2.label
     }
   }
   col2.label.padded
}

format.raw.data.col <- function(nums, denoms, label, types) {
    types.short <- types[types %in% c(0,1)]
    nums.total <- sum(nums[types.short==0])
    denoms.total <- sum(denoms[types.short==0])
    max.chars <- nchar(denoms.total) + 1
    overall.row <- paste(nums.total, "/", denoms.total, sep = "")
    label.info <- check.label(label, split.str = "/")
    if (label.info$contains.symbol == TRUE) {
        end.string.length <- label.info$end.string.length
        label.padded <- pad.with.spaces(label, begin.num=0, end.num = max.chars - end.string.length - 1)
        overall.row <- pad.with.spaces(overall.row, begin.num=0, end.num = end.string.length - max.chars)
        max.chars <- max(max.chars, end.string.length)
    }  else {
      label.padded <- pad.with.spaces(label, begin.num=0, end.num = floor((nchar(overall.row) - nchar(label)) / 2))
    }
    denoms <- mapply(pad.with.spaces, denoms, begin.num=0, end.num = max.chars - (nchar(denoms) + 1))
    data.column = c(label.padded, paste(nums, "/", denoms, sep = ""), overall.row)
    data.column
}

check.label <- function(label, split.str) {
    split.label <- strsplit(label, split.str)
    split.label.length <- length(split.label[[1]])
    label.info <- list("contains.symbol"=FALSE, "end.string.length"=0)
    if (split.label.length > 1) {
       label.info$contains.symbol <- TRUE
       label.info$end.string.length <- nchar(split.label[[1]][split.label.length])
    }
    label.info
}

calculate.radii <- function(plot.data, inv.var, max.symbol.size, max.ratio) {
    ES <- plot.data$effects$ES
    inv.var <- (plot.data$effects$se)^2
    cov.values <- plot.data$covariate$values
    x.range.min <- min(cov.values)
    x.range.max <- max(cov.values)
    x.range <- x.range.max - x.range.min
    y.range.min <- min(ES)
    y.range.max <- max(ES)
    y.range <- y.range.max - y.range.min
    min.range <- min(x.range, y.range)
    inv.var.min <- min(inv.var)
    inv.var.max <- max(inv.var)
    inv.var.ratio <- inv.var.max / inv.var.min
    radius.max <- min.range / 10
    radii <- (radius.max / inv.var.max) * inv.var
}
