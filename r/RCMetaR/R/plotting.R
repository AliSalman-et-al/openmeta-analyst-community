# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# Flexible forest plotting and related display helpers.

# largely a generalization based on an example by
# Murrell P., "R graphics", Chapman & Hall
#################################################################
#   functions for creating plot data to pass to plot functions  #
#################################################################

forest.plot.p.value.label <- function(p.value, digits, missing.label="") {
    if (display.value.is.missing(p.value)) {
        return(missing.label)
    }
    formatted <- round.display(p.value, digits)
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
    # Creates a data structure that can be passed to forest.plot
    # res is the output of a call to the Metafor function rma

    scale.str <- get.scale(params)
    transform.name <- get.transform.name(om.data)
    plot.options <- set.plot.options(params)
    # Set n, the number of studies, for PFT metric.
    if (params$measure=="PFT" && length(om.data@g1O1) > 1 && length(om.data@g1O2)) {
        n <- om.data@g1O1 + om.data@g1O2  # Number of subjects
    }
	else {
		n <- NULL # not needed except for pft
	}

    if (params$fp_plot_lb == "[default]") {
        plot.options$plot.lb <- params$fp_plot_lb
    } else {
        plot.lb <- eval(parse(text=paste("c(", params$fp_plot_lb, ")", sep="")))
        plot.options$plot.lb <- eval(call(transform.name, params$measure))$calc.scale(plot.lb, n)
    }

    if (params$fp_plot_ub == "[default]")  {
        plot.options$plot.ub <- params$fp_plot_ub
    } else {
        plot.ub <- eval(parse(text=paste("c(", params$fp_plot_ub, ")", sep="")))
        if (scale.str == "logit") {
          plot.ub <- min(1, plot.ub)
        }
        plot.options$plot.ub <- eval(call(transform.name, params$measure))$calc.scale(plot.ub, n)
    }

    digits.str <- paste("%.", params$digits, "f", sep="")
    # heterogeity data
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
    # append years to study names unless year equals 0 (0 is passed to R when year is empty).
    study.names <- om.data@study.names
    years <- om.data@years
    study.names[years != 0] <- paste(study.names[years != 0], years[years != 0], sep=" ")
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

    #y.disp <- eval(call(transform.name, params$measure))$display.scale(y, n)
    #lb.disp <- eval(call(transform.name, params$measure))$display.scale(lb, n)
    #ub.disp <- eval(call(transform.name, params$measure))$display.scale(ub, n)

    #y.overall.disp <- eval(call(transform.name, params$measure))$display.scale(y.overall, n)
    #lb.overall.disp <- eval(call(transform.name, params$measure))$display.scale(lb.overall, n)
    #ub.overall.disp <- eval(call(transform.name, params$measure))$display.scale(ub.overall, n)

	y.disp <- eval(call(transform.name, params$measure))$display.scale(y, ni=n)
	lb.disp <- eval(call(transform.name, params$measure))$display.scale(lb, ni=n)
	ub.disp <- eval(call(transform.name, params$measure))$display.scale(ub, ni=n)

	y.overall.disp <- eval(call(transform.name, params$measure))$display.scale(y.overall, ni=n)
	lb.overall.disp <- eval(call(transform.name, params$measure))$display.scale(lb.overall, ni=n)
	ub.overall.disp <- eval(call(transform.name, params$measure))$display.scale(ub.overall, ni=n)

    y <- c(y, y.overall)
    lb <- c(lb, lb.overall)
    ub <- c(ub, ub.overall)

    y.disp <- c(y.disp, y.overall.disp)
    lb.disp <- c(lb.disp, lb.overall.disp)
    ub.disp <- c(ub.disp, ub.overall.disp)

    effects.disp <- list(y.disp=y.disp, lb.disp=lb.disp, ub.disp=ub.disp)
    # these values will be displayed on the plot
    plot.data$effects.disp <- effects.disp

    # If metric is log scale, effect sizes and plot range are passed to forest.plot in
    # calculation (log) scale, in order to set tick marks in log scale.
    # Otherwise, effect sizes and plot range are passed in display (untransformed) scale.

    if (!metric.is.log.scale(params$measure)) {
        # if metric not log scale, pass data in display scale - no scaling on x-axis
        y <- y.disp
        lb <- lb.disp
        ub <- ub.disp
    }

    effects <- list(ES = y,
                    LL = lb,
                    UL = ub)
    plot.data$effects <- effects
    plot.range <- calc.plot.range(effects, plot.options)
    # Calculate a reasonable range for the x-values to display in plot.

    if (metric.is.log.scale(params$measure)) {
        # Plot range is in calc scale, so put back in display scale to update params.
        plot.range.disp.lower <- eval(call(transform.name, params$measure))$display.scale(plot.range[1])
        plot.range.disp.upper <- eval(call(transform.name, params$measure))$display.scale(plot.range[2])
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
        cov.values <- eval(parse(text=cov.val.str))
        plot.data$covariate <- list(varname = selected.cov,
                                   values = cov.values)
    }
    plot.data
}

create.plot.data.binary <- function(binary.data, params, res, selected.cov = NULL){

    plot.data <- create.plot.data.generic(binary.data, params, res, selected.cov=selected.cov)
    # if we have raw data, add it to plot.data
    if (length(binary.data@g1O1) > 0)  {

        plot.data$col3 <- list(nums = binary.data@g1O1, denoms = binary.data@g1O1 + binary.data@g1O2)
    }

    if (length(binary.data@g2O1) > 0) {
         plot.data$col4 <- list(nums = binary.data@g2O1, denoms = binary.data@g2O1 + binary.data@g2O2)
    }

    if (rcmetar.metafor.binary.default.supported(binary.data, params, selected.cov=selected.cov)) {
        plot.data <- rcmetar.build.binary.metafor.bundle(binary.data, params, res, plot.data)
    }

    plot.data
}

create.plot.data.diagnostic <- function(diagnostic.data, params, res, selected.cov = NULL){

    plot.data <- create.plot.data.generic(diagnostic.data, params, res, selected.cov=selected.cov)
    plot.options <- plot.data$plot.options
    plot.options$show.y.axis <- FALSE
    changed.params <- plot.data$changed.params
    # don't show y axis in diagnostic forest plots
    # if we have raw data, add it to plot.data
    if (length(diagnostic.data@TP) > 0) {
        raw.data <- list("TP"=diagnostic.data@TP, "FN"=diagnostic.data@FN, "TN"=diagnostic.data@TN, "FP"=diagnostic.data@FP)
        terms <- compute.diagnostic.terms(raw.data, params)
        plot.data$col3 <- list(nums=terms$numerator, denoms=terms$denominator)

        metric <- params$measure
        # create label for column 3 based on metric
        label <- switch(metric,
        # sensitivity
        Sens = "TP/(TP + FN)",
        # specificity
        Spec = "TN/(FP + TN)",
        # pos. predictive value
        PPV =  "TP/(TP + FP)",
        #neg. predictive value
        NPV =  "TN/(TN + FN)",
        # accuracy
        Acc = "(TP + TN)/Tot",
        # positive likelihood ratio
        PLR = "(TP * Di-)/(FP * Di+)",
        # negative likelihood ratio
        NLR = "(FN * Di-)/(TN * Di+)",
        # diagnostic odds ratio
        DOR = "(TP * TN)/(FP * FN)")

        plot.data$options$col3.str <- label
        changed.params$fp_col3_str <- label
        plot.data$changed.params <- changed.params
    }
    if (rcmetar.metafor.diagnostic.default.supported(diagnostic.data, params, selected.cov=selected.cov)) {
        plot.data <- rcmetar.build.diagnostic.metafor.bundle(diagnostic.data, params, res, plot.data)
    }
    plot.data
}

create.plot.data.continuous <- function(cont.data, params, res, selected.cov = NULL){
    # Creates a data structure that can be passed to forest.plot
    # res is the output of a call to the Metafor function rma
    plot.data <- create.plot.data.generic(cont.data, params, res, selected.cov=selected.cov)
    if (rcmetar.metafor.continuous.default.supported(cont.data, params, selected.cov=selected.cov)) {
        plot.data <- rcmetar.build.continuous.metafor.bundle(cont.data, params, res, plot.data)
    }
    plot.data
}

create.plot.data.overall <- function(om.data, params, res, res.overall){
    scale.str <- get.scale(params)
    # Set n, the number of studies, for PFT metric.
    if (params$measure=="PFT" && length(om.data@g1O1) > 1 && length(om.data@g1O2)) {
        n <- om.data@g1O1 + om.data@g1O2  # Number of subjects
    }
	else {
	    n <- NULL
	}

    ## TO DO - don't really nead three transforms - the transform only depends on the measure.
    transform.name <- get.transform.name(om.data)
    plot.options <- set.plot.options(params)
    plot.options$show.col3 <- FALSE
    plot.options$show.col4 <- FALSE
    # currently not displaying raw data cols. for overall plots

    if (params$fp_plot_lb == "[default]") {
        plot.options$plot.lb <- params$fp_plot_lb
    } else {
        plot.lb <- eval(parse(text=paste("c(", params$fp_plot_lb, ")", sep="")))
        plot.options$plot.lb <- eval(call(transform.name, params$measure))$calc.scale(plot.lb, n)
    }
    if (params$fp_plot_ub == "[default]") {
        plot.options$plot.ub <- params$fp_plot_ub
    } else {
        plot.ub <- eval(parse(text=paste("c(", params$fp_plot_ub, ")", sep="")))
        plot.options$plot.ub <- eval(call(transform.name, params$measure))$calc.scale(plot.ub, n)
    }
    if (metric.is.log.scale(params$measure)) {
        plot.options$show.y.axis <- FALSE
        # don't show y-axis for diagnostic forest plots
    } else {
        plot.options$show.y.axis <- TRUE
    }

    plot.data <- list( scale = scale.str,
                       options = plot.options)
    # unpack data
    y <- NULL
    lb <- NULL
    ub <- NULL

    for (count in 1:length(res)) {
      y <- c(y, res[[count]]$b)
      lb <- c(lb, res[[count]]$ci.lb)
      ub <- c(ub, res[[count]]$ci.ub)
    }

    y.disp <- eval(call(transform.name, params$measure))$display.scale(y, n)
    lb.disp <- eval(call(transform.name, params$measure))$display.scale(lb, n)
    ub.disp <- eval(call(transform.name, params$measure))$display.scale(ub, n)
    effects.disp <- list(y.disp=y.disp, lb.disp=lb.disp, ub.disp=ub.disp)
    plot.data$effects.disp <- effects.disp

    if (!metric.is.log.scale(params$measure)) {
        # if metric not log scale, pass data in display scale - no scaling on x-axis
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
    # Put plot range in display scale to update params.
    plot.range.disp.lower <- eval(call(transform.name, params$measure))$display.scale(plot.range[1], n)
    plot.range.disp.upper <- eval(call(transform.name, params$measure))$display.scale(plot.range[2], n)
    changed.params <- plot.options$changed.params
    if (plot.options$plot.lb != plot.range.disp.lower) {
        changed.params$fp_plot_lb <- plot.range.disp.lower
    }
    if (plot.options$plot.ub != plot.range.disp.upper) {
        changed.params$fp_plot_ub <- plot.range.disp.upper
    }
    if (metric.is.log.scale(params$measure)) {
        plot.data$summary.est <- res.overall$b[1]
        # Pass in calc. scale if metric is log scale
    } else {
        plot.data$summary.est <- eval(call(transform.name, params$measure))$display.scale(res.overall$b[1], n)
    }
    plot.data$changed.params <- changed.params
    plot.data
}

create.plot.data.cum <- function(om.data, params, res) {
    # Wrapper for creating cumulative plot.data
    params$show_col1 <- 'FALSE'
    # don't show study names for right-hand plot
    res.overall <- res[[length(res)]]
    # Last entry of res contains overall summary
    plot.data <- create.plot.data.overall(om.data, params, res, res.overall)

    study.names <- c()
    study.names <- paste("  ", om.data@study.names[1], sep="")
    for (count in 2:length(om.data@study.names)) {
        study.names <- c(study.names, paste("+ ",om.data@study.names[count], sep=""))
    }
    # duplicate last row of data to generate an empty row in the cumulative plot.
    # This data does not get plotted! Just aligns rows with standard plot.
    effects.disp.tmp <- plot.data$effects.disp
    y.disp.tmp <- effects.disp.tmp$y.disp
    lb.disp.tmp <- effects.disp.tmp$lb.disp
    ub.disp.tmp <- effects.disp.tmp$ub.disp
    last.index <- length(y.disp.tmp)
    y.disp.tmp <- c(y.disp.tmp, y.disp.tmp[last.index])
    lb.disp.tmp <- c(lb.disp.tmp, lb.disp.tmp[last.index])
    ub.disp.tmp <- c(ub.disp.tmp, ub.disp.tmp[last.index])
    effects.disp <- list("y.disp"=y.disp.tmp, "lb.disp"=lb.disp.tmp, "ub.disp"=ub.disp.tmp)
    plot.data$effects.disp <- effects.disp

    effects.tmp <- plot.data$effects
    ES.tmp <- effects.tmp$ES
    LL.tmp <- effects.tmp$LL
    UL.tmp <- effects.tmp$UL
    last.index <- length(ES.tmp)
    ES.tmp <- c(ES.tmp, ES.tmp[last.index])
    LL.tmp <- c(LL.tmp, LL.tmp[last.index])
    UL.tmp <- c(UL.tmp, UL.tmp[last.index])
    effects <- list("ES"=ES.tmp, "LL"=LL.tmp, "UL"=UL.tmp)
    plot.data$effects<- effects
    plot.data$types <- c(3, rep(0, length(study.names)), 4)
    # type 4 does not get plotted! Generates empty row in plot.
    study.names <- c(study.names, "")
    # extra blank name to align rows with standard plot
    plot.data$label <- c(rcmetar.forest.study.header.label(params$fp_col1_str), study.names)
    plot.data
}

create.plot.data.loo <- function(om.data, params, res) {
    # wrapper for creating leave-one-out plot.data
    res.overall <- res[[1]]
    # First entry of res contains overall summary
    study.names <- c("Overall", paste("- ", om.data@study.names, sep=""))
    plot.data <- create.plot.data.overall(om.data, params, res, res.overall)
    plot.data$label <- c(rcmetar.forest.study.header.label(params$fp_col1_str), study.names)
    plot.data$types <- c(3, 5, rep(0, length(om.data@study.names)))
    plot.data
}

# create subgroup analysis plot data
create.subgroup.plot.data.generic <- function(subgroup.data, params, data.type, selected.cov=NULL) {

    grouped.data <- subgroup.data$grouped.data
    res <- subgroup.data$results
    subgroup.list <- subgroup.data$subgroup.list
    scale.str <- get.scale(params)
    # Set n, the number of studies, for PFT metric.
    if (params$measure=="PFT" && length(om.data@g1O1) > 1 && length(om.data@g1O2)) {
      n <- om.data@g1O1 + om.data@g1O2  # Number of subjects
    }
	else {
		n <- NULL
	}

    ## TO DO - don't really nead three transforms - the transform only depends on the measure.
    if (data.type == "continuous") {
      transform.name <- "continuous.transform.f"
    } else if (data.type == "diagnostic") {
      transform.name <- "diagnostic.transform.f"
    }  else if (data.type == "binary") {
      transform.name <- "binary.transform.f"
    }
    cur.res <- NULL
    y <- NULL
    lb <- NULL
    ub <- NULL
    label.col <- NULL
    types <- NULL
    mult <- get.mult.from.conf.level(params$conf.level)
    digits.str <- paste("%.", params$digits, "f", sep="")

    for (i in 1:length(subgroup.list)){
        # create plot data for each subgroup and concatenate results
        cur.res <- res[[i]]
        params.tmp <- params
        cur.y.overall <- cur.res$b[1]
        cur.lb.overall <- cur.res$ci.lb[1]
        cur.ub.overall <- cur.res$ci.ub[1]
        cur.y <- grouped.data[[i]]@y
        cur.lb <- cur.y - mult*grouped.data[[i]]@SE
        cur.ub <- cur.y + mult*grouped.data[[i]]@SE
        y <- c(y, cur.y, cur.y.overall)
        lb <- c(lb, cur.lb, cur.lb.overall)
        ub <- c(ub, cur.ub, cur.ub.overall)

         # heterogeneity data
        degf <- cur.res$k - 1
        if (!is.null(cur.res$QE)) {
            QE <- sprintf(digits.str, cur.res$QE)
        } else {
            QE <- "NA"
        }
        if (!display.value.is.missing(cur.res$I2)) {
            I2 <- paste(round(cur.res$I2, digits = 2), "%", sep="")
        } else {
            I2 <- ""
        }
        QEp <- forest.plot.p.value.label(cur.res$QEp, params$digits)

        overall <- forest.plot.heterogeneity.suffix(I2, QEp)
        types <- c(types, rep(0, length(grouped.data[[i]]@study.names)), 1)
        label.col <-c(label.col, grouped.data[[i]]@study.names, paste("Subgroup ", subgroup.list[i], overall, sep=""))
    }
    cur.res <- res[[length(subgroup.list) + 1]]
    cur.y.overall <- cur.res$b[1]
    cur.lb.overall <- cur.res$ci.lb[1]
    cur.ub.overall <- cur.res$ci.ub[1]
    y <- c(y, cur.y.overall)
    lb <- c(lb, cur.lb.overall)
    ub <- c(ub, cur.ub.overall)
    types <- c(3,types, 2)
     # heterogeneity data
    degf <- cur.res$k - 1
    if (!is.null(cur.res$QE)) {
        QE <- sprintf(digits.str, cur.res$QE)
    } else {
        QE <- "NA"
    }
    if (!display.value.is.missing(cur.res$I2)) {
        I2 <- paste(round(cur.res$I2, digits = 2), "%", sep="")
    } else {
        I2 <- ""
    }
    QEp <- forest.plot.p.value.label(cur.res$QEp, params$digits)
    overall <- forest.plot.heterogeneity.suffix(I2, QEp)
    label.col <- c(rcmetar.forest.study.header.label(params$fp_col1_str), label.col, paste("Overall", overall, sep=""))
    plot.options <- set.plot.options(params)
    if (params$fp_plot_lb == "[default]") {
        plot.options$plot.lb <- params$fp_plot_lb
    } else {
        plot.lb <- eval(parse(text=paste("c(", params$fp_plot_lb, ")", sep="")))
        plot.options$plot.lb <- eval(call(transform.name, params$measure))$calc.scale(plot.lb, n)
    }
    if (params$fp_plot_ub == "[default]") {
        plot.options$plot.ub <- params$fp_plot_ub
    } else {
        plot.ub <- eval(parse(text=paste("c(", params$fp_plot_ub, ")", sep="")))
        plot.options$plot.ub <- eval(call(transform.name, params$measure))$calc.scale(plot.ub, n)
    }

    # Subgroup plots do not draw an additional summary line here.
    plot.data <- list(label = label.col,
                      types=types,
                      scale = scale.str,
                      options = plot.options)
    y.disp <- eval(call(transform.name, params$measure))$display.scale(y, n)
    lb.disp <- eval(call(transform.name, params$measure))$display.scale(lb, n)
    ub.disp <- eval(call(transform.name, params$measure))$display.scale(ub, n)

    # these values will be displayed on the plot
    effects.disp <- list(y.disp=y.disp, lb.disp=lb.disp, ub.disp=ub.disp)
    plot.data$effects.disp <- effects.disp

    if (!metric.is.log.scale(params$measure)) {
        # if metric not log scale, pass data in display scale - no scaling on x-axis
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
    # Put plot range in display scale to update params.
    plot.range.disp.lower <- eval(call(transform.name, params$measure))$display.scale(plot.range[1], n)
    plot.range.disp.upper <- eval(call(transform.name, params$measure))$display.scale(plot.range[2], n)
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
        cov.values <- eval(parse(text=cov.val.str))
        plot.data$covariate <- list(varname = selected.cov,
                                   values = cov.values)
    }
    plot.data
}

create.subgroup.plot.data.binary <- function(subgroup.data, params) {
    grouped.data <- subgroup.data$grouped.data
    plot.data <- create.subgroup.plot.data.generic(subgroup.data, params, data.type="binary")

    # if we have raw data, add it to plot.data
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
        # create label for column 3 based on metric
        label <- switch(metric,
        # sensitivity
        Sens = "TP / (TP + FN)",
        # specificity
        Spec = "TN / (FP + TN)",
        # pos. predictive value
        PPV =  "TP / (TP + FP)",
        #neg. predictive value
        NPV =  "TN / (TN + FN)",
        # accuracy
        Acc = "(TP + TN) / Tot",
        # positive likelihood ratio
        PLR = "(TP * Di-) / (FP * Di+)",
        # negative likelihood ratio
        NLR = "(FN * Di-) / (TN * Di+)",
        # diagnostic odds ratio
        DOR = "(TP * TN) / (FP * FN")
        #data.col <- format.raw.data.col(nums = terms$numerator, denoms = terms$denominator, label = label)
        #plot.data$additional.col.data$cases = data.col
        plot.data$options$col3.str <- label
    }
    plot.data
}

create.subgroup.plot.data.cont <- function(subgroup.data, params) {
    grouped.data <- subgroup.data$grouped.data
    plot.data <- create.subgroup.plot.data.generic(subgroup.data, params, data.type="continuous")
}

# create regression plot data
create.plot.data.reg <- function(reg.data, params, fitted.line, selected.cov=NULL) {
     scale.str <- get.scale(params)
     cov.name <- reg.data@covariates[[1]]@cov.name
     cov.vals <- reg.data@covariates[[1]]@cov.vals
     plot.data <- list("fitted.line" = fitted.line,
                      types = c(rep(0, length(reg.data@study.names))),
                      scale = scale.str,
                      covariate = list(varname = cov.name, values = cov.vals))
     mult <- get.mult.from.conf.level(params$conf.level)


     y <- reg.data@y
     se <- reg.data@SE
     effects <- list(ES = y,
                    se = se)
     plot.data$effects <- effects

     ###
     # Plot sizing defaults can move into params when exposed by the UI.
     plot.data$sym.size <- 1
     plot.data$lcol <- "darkred"
     plot.data$lweight <- 3
     plot.data$lpattern <- "dotted"
     plot.data$plotregion <- "n"
     plot.data$mcolor <- "darkgreen"
     plot.data$regline <- TRUE

     plot.data
}



set.plot.options <- function(params) {
    # set default plot options
    plot.options <- list()
    changed.params <- list()
    # xticks is a vector of tick marks for the x-axis
    if (params$fp_xticks[1] == '[default]') {
        plot.options$xticks <- NA
    } else if (is.vector(params$fp_xticks)) {
        # params was saved from a previous run and plot is being edited.
        plot.options$xticks <- params$fp_xticks
    } else {
        # params being passed in from GUI - convert to a vector.
        plot.options$xticks <- eval(parse(text=paste("c(", params$fp_xticks, ")", sep="")))
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
      # don't show col. 4 if metric is one-arm.
      plot.options$show.col4 <- TRUE
    } else {
      plot.options$show.col4 <- FALSE
    }
    if (!is.null(params$fp_col4_str)) {
       plot.options$col4.str <- as.character(params$fp_col4_str)
    }

    # xlabel is the label for the x-axis
    if (params$fp_xlabel == "[default]") {
        xlabel <- pretty.metric.name(as.character(params$measure))
        if (metric.is.log.scale(params$measure)) {
            xlabel <- paste(xlabel, " (log scale)", sep="")
        }
        plot.options$xlabel <- xlabel
        changed.params$fp_xlabel <- xlabel
    } else {
        plot.options$xlabel <- as.character(params$fp_xlabel)
    }

    # fp.title is the title for forest plot
    # Use a blank title unless the caller supplies one.
    if (is.null(params$fp.title)) {
         plot.options$fp.title <- ""
    } else {
         plot.options$fp.title <- params$fp.title
    }

    # if show.summary.line is TRUE, a vertical dashed line is displayed at the
    # overall summary.
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
    # Calculate lower and upper bounds for x-values of plotted data
    # if user has not supplied them (or user's bounds don't include all effect sizes).
    effect.size.min <- min(effects$ES)
    # Smallest value for which we accept user's input for plot lower bound.
    # User's lower bound must be less than all effect sizes.
    effect.size.max <- max(effects$ES)
    # Largest user input for plot upper bound. All effect sizes must be less than this value.
    user.lb <- plot.options$plot.lb
    user.ub <- plot.options$plot.ub
    if (user.lb != "[default]") {
        # Check whether user's lb is OK
        if (user.lb > effect.size.min) {
          # not OK
          user.lb <- "[default]"
        }
    }
    if (user.ub != "[default]") {
        # Check whether user's lb is OK
        if (plot.options$plot.ub < effect.size.max) {
          # not OK
          user.ub <- "[default]"
        }
    }
    plot.range <- c()
    if (user.lb == "[default]" || user.ub == "[default]") {
        # If user has not supplied both lower and upper bounds (that meet the requirements), compute bounds.
        # This is a heuristic to determine a reasonable range for the displayed values -
        # confidence intervals that exceed this range are truncated and left or right arrows are displayed instead of the full CI.
        effect.size.width <- effect.size.max - effect.size.min

        effects.max <- max(effects$UL)
        effects.min <- min(effects$LL)
        arrow.factor <- 2
        # Confidence intervals extend at most arrow.factor times effect.size.width beyond (effect.size.min, effect.size.max)
        plot.ub <- min(effects.max, effect.size.max + arrow.factor * effect.size.width)
        plot.lb <- max(effects.min, effect.size.min - arrow.factor * effect.size.width)

        plot.range <- c(plot.lb, plot.ub)
    }
    if (user.lb != "[default]") {
        # If the user's lb input is OK, set lower bound of range equal it.
        plot.range[1] <- user.lb
    }
    if (user.ub != "[default]") {
        # If the user's ub input is OK, set upper bound of range equal it.
        plot.range[2] <- user.ub
    }
    plot.range
}

pretty.metric.name <- function(metric) {
  # labels for plot axes
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
    # pos. predictive value
    PPV =  "Positive Predictive Value",
    #neg. predictive value
    NPV =  "Negative Predictive Value",
    # accuracy
    Acc = "Accuracy",
    # positive likelihood ratio
    PLR = "Positive Likelihood Ratio",
    # negative likelihood ratio
    NLR = "Negative Likelihood Ratio",
    # diagnostic odds ratio
    DOR = "Diagnostic Odds Ratio",
    # tx mean is already pretty.
    TXMean = "TX Mean",
    # Generic Effect
    GEN = "Generic Effect")

  metric.key <- gsub("[[:space:].]+", "", trimws(metric))
  metric.name <- metric.names[[metric.key]]
  if (is.null(metric.name) && metric %in% unlist(metric.names, use.names=FALSE)) {
    metric.name <- metric
  }

  metric.name
}

###################################
#   functions for creating plots  #
###################################

#######################################
#       meta-regression scatter       #
#######################################
meta.regression.plot <- function(plot.data, outpath, ...) {
	png(filename=rcmetar.scratch.path("INTER")) # to fix windows popping out at you issue

    lweight = 1
    lpattern = "solid"
    lcol = "blue"
    ES <- plot.data$effects$ES
    se <- plot.data$effects$se
    # make the data data.frame
    data.reg <- data.frame(plot.data$effects, types=plot.data$types)
    # data for plot (only keep the studies - not the summaries)
    data.reg <- subset(data.reg, types==0)
    cov.name <- plot.data$covariate$varname
    cov.values <- plot.data$covariate$values
    x.range.min <- min(cov.values)
    x.range.max <- max(cov.values)
    x.range <- x.range.max - x.range.min
    x.min <- x.range.min - (x.range / 5)
    x.max <- x.range.max + (x.range / 5)
    y.range.min <- min(ES)
    y.range.max <- max(ES)
    y.range <- y.range.max - y.range.min
    y.min <- y.range.min - (y.range / 5)
    y.max <- y.range.max + (y.range / 5)

    if (length(grep(".png", outpath)) != 0){
        png(filename=outpath, width=10 , height=5, units="in", res=144)
    } else {
        pdf(file=outpath, width=10 , height=5)
    }

    plot(y = data.reg$ES, x=cov.values,
                          xlim=c(x.min, x.max),
                          ylim=c(y.min, y.max),
                          xlab=plot.data$xlabel,
                          ylab=plot.data$ylabel, type='n')
    symbols(y = data.reg$ES, x=cov.values,
                circles = 1 / data.reg$se,
                inches=.3,
                bty=plot.data$plotregion, add=TRUE)
    if (plot.data$regline)  {
       x<-c(x.range.min, x.range.max)
       y<-c (plot.data$fitted.line$intercept +
                x.range.min*plot.data$fitted.line$slope, plot.data$fitted.line$intercept +
                x.range.max*plot.data$fitted.line$slope)
       lines(x, y, col=lcol, lwd=lweight, lty=lpattern)
    }
    # write the plot data out to disk
    graphics.off()
}

######################################
#          Diagnostic SROC           #
######################################
sroc.plot <- function(plot.data, outpath){
	png(filename=rcmetar.scratch.path("INTER")) # to fix windows popping out at you issue

    # draw an SROC plot.
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

    # create regression line values
    s.vals <- seq(from = s.range$min, to = s.range$max, by=.001)
    reg.line.vals <- fitted.line$intercept + fitted.line$slope * s.vals
    std.err <- plot.data$std.err
    mult <- plot.data$mult
    upper.ci.vals <- reg.line.vals + mult * std.err
    lower.ci.vals <- reg.line.vals - mult * std.err
    # transform regression line coords to TPR by 1 - FPR coords
    reg.line.vals.trans <- invlogit((s.vals + reg.line.vals) / 2)
    s.vals.trans <- invlogit((s.vals - reg.line.vals) / 2)

    lines(s.vals.trans, reg.line.vals.trans, col = lcol, lwd = lweight, lty = lpatern)
    upper.ci.vals.trans <- invlogit((s.vals + upper.ci.vals))
    lower.ci.vals.trans <- invlogit((s.vals + lower.ci.vals))
    graphics.off()
}

################################################
#   Diagnostic PPV and NPV by Prevalence       #
################################################

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
#######################################################
#  Functions for formatting data for display in plots #
#######################################################

format.data.cols <- function(plot.data) {
  # formats data columns for display on forest plot
  options <- plot.data$options
  types <- plot.data$types
  if (options$show.col2==TRUE) {

        y.disp <- plot.data$effects.disp$y.disp
        lb.disp <- plot.data$effects.disp$lb.disp
        ub.disp <- plot.data$effects.disp$ub.disp
        effect.sizes <- format.effect.sizes(y=y.disp, lb=lb.disp, ub=ub.disp, options)
        # first row contains headers, so add label
        effect.size.label <- create.effect.size.label(effect.sizes, options)
        effect.size.col <- c(effect.size.label,
                             paste(effect.sizes$y.display, effect.sizes$lb.display, ",",
                                   effect.sizes$ub.display, ")", sep = ""))
        # replace data for type 4 rows with empty strings. Type 4 rows are empty rows in the forest plot (for vertical alignment only).
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
  # format column by padding entries with spaces for alignment
  digits <- options$digits
  y.display <- sprintf(paste("%.", digits,"f", sep=""), y)
  lb.display <- sprintf(paste("%.", digits,"f", sep=""), lb)
  ub.display <- sprintf(paste("%.", digits,"f", sep=""), ub)

  # for ub, add an extra space to positive numbers for alignment (negative numbers display minus sign)
  if (length(ub.display[ub.display >= 0])) {
    ub.display[ub.display >= 0] <- mapply(pad.with.spaces, ub.display[ub.display >= 0], begin.num=1, end.num=0)
  }
  # format results by padding with spaces to align columns
  ub.max.chars <- max(nchar(ub.display))
  ub.extra.space <- ub.max.chars - nchar(ub.display)
  ub.display <- mapply(pad.with.spaces, ub.display, begin.num = ub.extra.space, end.num=0)
  # for ub, add an extra space to positive numbers for alignment (negative numbers display minus sign)
  if (length(ub.display[ub.display >= 0])) {
    ub.display[ub.display >= 0] <- mapply(pad.with.spaces, ub.display[ub.display >= 0], begin.num=1, end.num=0)
  }
  # if ub has any negative entries, add an extra space to separate entry from preceding ","
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
   # Add label to effect.size.column and align the comma if the label
   # is of the form ES(LL, UL), with the data entries below it. Since the default label
   # is no longer of that form, this function could be removed.
   col2.label <- as.character(options$col2.str)
   # if label contains ",", pad label to align columns
   label.info <- check.label(label = col2.label, split.str = ",")
   max.chars <- max(nchar(effect.sizes$ub.display)) + 1
   # add 1 because a space is added before each ub entry.
   if (label.info$contains.symbol == TRUE) {
     # Label contains "," so pad label to align ","
     # we're assuming that there is a single space after ","
     col2.label.padded <- pad.with.spaces(col2.label, begin.num=0, end.num = max.chars - label.info$end.string.length)
   } else {
     # label doesn't contain "," so pad label to center over column
     col2.width <- max(nchar(effect.sizes$y.disp) + nchar(effect.sizes$lb.disp) + nchar(effect.sizes$ub.disp))
     if (col2.width > nchar(col2.label)) {
       # width of data greater than the length of col. label
       col2.label.padded <- pad.with.spaces(col2.label, begin.num=0, end.num = floor((col2.width - nchar(col2.label)) / 2))
     } else {
       # don't pad with spaces
       col2.label.padded <- col2.label
     }
   }
   col2.label.padded
}

format.raw.data.col <- function(nums, denoms, label, types) {
    # format raw data columns to align forward slashes
    types.short <- types[types %in% c(0,1)]
    # remove types 3 (labels) and 2 (overall total) if present
    nums.total <- sum(nums[types.short==0])
    denoms.total <- sum(denoms[types.short==0])
    # only sum over types==0 (individual studies)
    max.chars <- nchar(denoms.total) + 1
    # add 1 because a space is added before each denom.
    overall.row <- paste(nums.total, "/", denoms.total, sep = "")
    label.info <- check.label(label, split.str = "/")
    if (label.info$contains.symbol == TRUE) {
        # pad label or denoms.total to align "/"
        # we're assuming that there is a single space after "/".
        end.string.length <- label.info$end.string.length
        label.padded <- pad.with.spaces(label, begin.num=0, end.num = max.chars - end.string.length - 1)
        overall.row <- pad.with.spaces(overall.row, begin.num=0, end.num = end.string.length - max.chars)
        max.chars <- max(max.chars, end.string.length)
    }  else {
      # pad label to center above column
      label.padded <- pad.with.spaces(label, begin.num=0, end.num = floor((nchar(overall.row) - nchar(label)) / 2))
    }
    # pad data row to align forward slashes
    denoms <- mapply(pad.with.spaces, denoms, begin.num=0, end.num = max.chars - (nchar(denoms) + 1))
    # add 1 to nchar(denoms) because a space is added before each denom
    data.column = c(label.padded, paste(nums, "/", denoms, sep = ""), overall.row)
    data.column
}

check.label <- function(label, split.str) {
    # utility for format.effect.size.col and format.raw.data.col
    # check column labels for split.symbol and return length of string that follows split.str
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
    # calculates radii of symbols for a meta-regression plot
    # using a scaling function f(x) = C * x^e.
    # inv.var is a vector of inverse variances,
    # max.symbol.size is the maximum size for a symbol, and max.ratio is the maximum ratio of symbol sizes.
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
