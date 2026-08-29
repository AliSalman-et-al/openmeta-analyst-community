# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

binary.logit.metrics <- c("PLO")
binary.log.metrics <- c("OR", "RR", "PLN")
binary.arcsine.metrics <- c("PAS")
binary.freeman_tukey.metrics <- c("PFT")
binary.two.arm.metrics <- c("OR", "RD", "RR", "AS", "YUQ", "YUY")
binary.one.arm.metrics <- c("PR", "PLN", "PLO", "PAS", "PFT")


compute.for.one.bin.study <- function(binary.data, params){
    if (params$measure %in% binary.one.arm.metrics) {
        res <- escalc(
            params$measure,
            xi=binary.data@g1O1,
            ni=binary.data@g1O1 + binary.data@g1O2,
            add=params$adjust,
            to=params$to
        )
        return(res)
    }
    res <- escalc(params$measure, ai=binary.data@g1O1, bi=binary.data@g1O2,
                                    ci=binary.data@g2O1, di=binary.data@g2O2,
                                    add=params$adjust, to=params$to)
    res
}

compute.bin.point.estimates <- function(binary.data, params) {
    res <- compute.for.one.bin.study(binary.data, params)
    binary.data@y <- res$yi
    binary.data@SE <- sqrt(res$vi)
    binary.data
}

binary.transform.f <- function(metric.str){
    display.scale <- function(x, ...){

        extra.args <- list(...)

        if (metric.str %in% binary.log.metrics){
            exp(x)
        } else if (metric.str %in% binary.logit.metrics){
            invlogit(x)
        } else if (metric.str %in% binary.arcsine.metrics){
            invarcsine.sqrt(x)
        } else if (metric.str %in% binary.freeman_tukey.metrics){
              ni <- extra.args[['ni']]
              if (length(x)==1) {
                  transf.ipft.hm(x, targs=list(ni=ni))
              } else {
                  transf.ipft(x, ni)
              }
        } else {
            x
        }
    }


    calc.scale <- function(x, ...){

        extra.args <- list(...)
        if (metric.str %in% binary.log.metrics){
            log(x)
        } else if (metric.str %in% binary.logit.metrics){
            logit(x)
        } else if (metric.str %in% binary.arcsine.metrics){
            arcsine.sqrt(x)
        } else if (metric.str %in% binary.freeman_tukey.metrics){
            ni <- extra.args[['ni']]
             transf.pft(x, ni)
        } else {
            x
        }
    }

    list(display.scale = display.scale, calc.scale = calc.scale)
}

get.res.for.one.binary.study <- function(binary.data, params) {
    y<-NULL
    se<-NULL
    if (is.na(binary.data@y)){
        res <- compute.for.one.bin.study(binary.data, params)
        y <- res$yi[1]
        se <- sqrt(res$vi[1])
    }
    else{
        y <- binary.data@y[1]
        se <- binary.data@SE[1]
    }
    mult <- get.mult.from.conf.level(params$conf.level)
    ub <- y + mult*se
    lb <- y - mult*se
    res <- list("b"=c(y), "ci.lb"=lb, "ci.ub"=ub, "se"=se)
    res
}




create.binary.data.array <- function(binary.data, params, res){
    tx1.name <- "tx A"
    tx2.name <- "tx B"
    digits.str <- paste("%.", params$digits, "f", sep="")
    effect.size.name <- pretty.metric.name(as.character(params$measure))
    study.ci.bounds <- calc.ci.bounds(binary.data, params)
    y.disp <- binary.transform.f(params$measure)$display.scale(binary.data@y)
    lb.disp <- binary.transform.f(params$measure)$display.scale(study.ci.bounds$lb)
    ub.disp <- binary.transform.f(params$measure)$display.scale(study.ci.bounds$ub)
    y <- sprintf(digits.str, y.disp)
    LL <- sprintf(digits.str, lb.disp)
    UL <- sprintf(digits.str, ub.disp)
    weights <- res$study.weights
    weights <- sprintf(digits.str, weights)
    weights <- format(weights, justify="right")
    event.txA <- format(binary.data@g1O1, justify="right")
    subject.txA <- format(binary.data@g1O1 + binary.data@g1O2, justify="right")

    if (params$measure %in% binary.two.arm.metrics) {
        event.txB <- format(binary.data@g2O1, justify="right")
        subject.txB <- format(binary.data@g2O1 + binary.data@g2O2, justify="right")
        raw.data <- array(c("Study", paste(binary.data@study.names, " ", binary.data@years, sep=""),
                      paste(tx1.name, " Events", sep=""), event.txA,
                      paste(tx1.name, " Subjects", sep=""), subject.txA,
                      paste(tx2.name, " Events", sep=""), event.txB,
                      paste(tx2.name, " Subjects", sep=""), subject.txB,
                      effect.size.name, y, "Lower", LL, "Upper", UL, "Weight", weights),
                      dim=c(length(binary.data@study.names) + 1, 9))
        class(raw.data) <- "summary.data"
    } else if (params$measure %in% binary.one.arm.metrics) {
        raw.data <- array(c("Study", paste(binary.data@study.names, " ", binary.data@years, sep=""),
                      paste(tx1.name, " Events", sep=""), event.txA,
                      paste(tx1.name, " Subjects", sep=""), subject.txA,
                      effect.size.name, y, "Lower", LL, "Upper", UL, "Weight", weights),
                      dim=c(length(binary.data@study.names) + 1, 7))
    }
    return(raw.data)
}

write.bin.study.data.to.file <- function(binary.data, params, res, data.outpath) {
    effect.size.name <- pretty.metric.name(as.character(params$measure))
    y.disp <- binary.transform.f(params$measure)$display.scale(binary.data@y)
    study.ci.bounds <- calc.ci.bounds(binary.data, params)
    if (params$measure %in% binary.two.arm.metrics) {
        study.data.df <- data.frame("study.names"=paste(binary.data@study.names, " ", binary.data@years, sep=""),
                            "txA.events" = binary.data@g1O1,
                            "txA.subjects" = binary.data@g1O1 + binary.data@g1O2,
                            "txB.events" = binary.data@g2O1,
                            "txB.subjects" = binary.data@g2O1 + binary.data@g2O2,
                            "Effect.size" = binary.transform.f(params$measure)$display.scale(binary.data@y),
                            "Lower.bound" = binary.transform.f(params$measure)$display.scale(study.ci.bounds$lb),
                            "Upper.bound" = binary.transform.f(params$measure)$display.scale(study.ci.bounds$ub),
                            "Weight" = res$study.weights)
    } else if(params$measure %in% binary.one.arm.metrics) {
        study.data.df <- data.frame("study.names"=paste(binary.data@study.names, " ", binary.data@years, sep=""),
                            "txA.events" = binary.data@g1O1,
                            "txA.subjects" = binary.data@g1O1 + binary.data@g1O2,
                            "Effect.size" = binary.transform.f(params$measure)$display.scale(binary.data@y),
                            "Lower.bound" = binary.transform.f(params$measure)$display.scale(study.ci.bounds$lb),
                            "Upper.bound" = binary.transform.f(params$measure)$display.scale(study.ci.bounds$ub),
                            "Weight" = res$study.weights)
    }
    names(study.data.df)[names(study.data.df)=="Effect.size"] <- effect.size.name
    write.csv(study.data.df, file=data.outpath, row.names=FALSE)
}

binary.fixed.inv.var <- function(binary.data, params){
    if (!("BinaryData" %in% class(binary.data)))
        stop("Binary data expected.")

    results <- NULL
    input.params <- params
    inference.method <- rcmetar.validate.inference.method(params, length(binary.data@y))

    if (length(binary.data@g1O1) == 1 || length(binary.data@y) == 1){
        res <- get.res.for.one.binary.study(binary.data, params)
        results <- list("Summary"=res,
                        "res"=res)
    } else {
        res<-rma.uni(yi=binary.data@y, sei=binary.data@SE, slab=binary.data@study.names,
                                level=params$conf.level, digits=params$digits, method="FE", test=inference.method, add=c(params$adjust,params$adjust),
                                to=c(as.character(params$to), as.character(params$to)))
        pure.res <- res
        metric.name <- pretty.metric.name(as.character(params$measure))
        model.title <- paste("Binary Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep="")
        summary.disp <- create.summary.disp(binary.data, params, res, model.title)
        forest.path <- paste(params$fp_outpath, sep="")
        plot.data <- create.plot.data.binary(binary.data, params, res)
        changed.params <- plot.data$changed.params


		forest.plot.params.path <- ""
		if (is.null(params$supress.output) || !params$supress.output) {
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            forest.plot.params.path <- save.data(binary.data, res, params, plot.data)
		}


        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Forest Plot"=forest.path)
        plot.names <- c("forest plot"="forest_plot")
        pure.res$weights <- weights(res)
        results <- list("input_data"=binary.data,
                        "input_params"=input.params,
                        "images"=images,
                        "Summary"=capture.output.and.collapse(summary.disp),
                        "plot_names"=plot.names,
                        "plot_params_paths"=plot.params.paths,
                        "res"=pure.res,
                        "res.info"=binary.fixed.inv.var.value.info(),
                        "Weights"=weights(res))
    }

    results[["References"]] <- rcmetar.unique.references(c(
        rcmetar.method.references("rma.uni.fixed"),
        rcmetar.inference.method.references(params)))
    results
}

binary.fixed.inv.var.value.info <- function() {
    rma.uni.value.info()
}

binary.fixed.inv.var.is.feasible.for.funnel <- function() {
    TRUE
}

binary.fixed.inv.var.parameters <- function(){
    apply_adjustment_to = c("only0", "all")

    params <- list("inference.method"=rcmetar.inference.methods(), "conf.level"="float",
                   "digits"="int",
                   "adjust"="float",
                   "to"=apply_adjustment_to)

    defaults <- list("inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order = c("inference.method", "conf.level", "digits", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

binary.fixed.inv.var.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Binary Fixed-Effect Inverse Variance",
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

binary.fixed.inv.var.overall <- function(results) {
    res <- results$res
}

binary.fixed.mh <- function(binary.data, params){
    if (!("BinaryData" %in% class(binary.data)))
        stop("Binary data expected.")

    results <- NULL
    input.params <- params

    if (length(binary.data@g1O1) == 1 || length(binary.data@y) == 1){
        res <- get.res.for.one.binary.study(binary.data, params)
        results <- list("Summary"=res,
                        "res"=res)
    } else {
        res<-rma.mh(ai=binary.data@g1O1, bi=binary.data@g1O2,
                    ci=binary.data@g2O1, di=binary.data@g2O2,
                    slab=binary.data@study.names,
                    level=params$conf.level,
                    digits=params$digits,
                    measure=params$measure,
                    add=c(params$adjust, 0),
                    to=c(as.character(params$to), "none"))
        pure.res <- res
        if (is.null(binary.data@y) || is.null(binary.data@SE)) {
            binary.data <- compute.bin.point.estimates(binary.data, params)
        }
        metric.name <- pretty.metric.name(as.character(params$measure))
        model.title <- paste("Binary Fixed-Effect Model - Mantel-Haenszel\n\nMetric: ", metric.name, sep="")
        summary.disp <- create.summary.disp(binary.data, params, res, model.title)
        forest.path <- paste(params$fp_outpath, sep="")
        plot.data <- create.plot.data.binary(binary.data, params, res)
        changed.params <- plot.data$changed.params

		forest.plot.params.path <- ""
		if (is.null(params$supress.output) || !params$supress.output) {
	        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
	        changed.params <- c(changed.params, params.changed.in.forest.plot)
	        params <- update.changed.plot.params(params, changed.params)
	        forest.plot.params.path <- save.data(binary.data, res, params, plot.data)
		}




        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Forest Plot"=forest.path)
        plot.names <- c("forest plot"="forest_plot")
        pure.res$weights <- weights(res)
        results <- list("input_data"=binary.data,
                        "input_params"=input.params,
                        "images"=images,
                        "Summary"=capture.output.and.collapse(summary.disp),
                        "plot_names"=plot.names,
                        "plot_params_paths"=plot.params.paths,
                        "res"=pure.res,
                        "res.info"=binary.fixed.mh.value.info(),
                        "Weights"=weights(res))


    }

    results[["References"]] <- rcmetar.method.references("rma.mh")

    results
}


binary.fixed.mh.value.info <- function() {
    list(
        b        = list(type="vector", description='estimated coefficients of the model.'),
        se       = list(type="vector", description='standard errors of the coefficients.'),
        zval     = list(type="vector", description='test statistics of the coefficients.'),
        pval     = list(type="vector", description='p-values for the test statistics.'),
        ci.lb    = list(type="vector", description='lower bound of the confidence intervals for the coefficients.'),
        ci.ub    = list(type="vector", description='upper bound of the confidence intervals for the coefficients.'),
        QE       = list(type="vector", description='test statistic for the test of (residual) heterogeneity.'),
        QEp      = list(type="vector", description='p-value for the test of (residual) heterogeneity.'),
        MH       = list(type="vector", description='Cochran-Mantel-Haenszel test statistic (measure="OR") or Mantel-Haenszel test statistic (measure="IRR").'),
        MHp      = list(type="vector", description='corresponding p-value'),
        TA       = list(type="vector", description="Tarone's heterogeneity test statistic (only when measure=\"OR\")."),
        TAp      = list(type="vector", description='corresponding p-value (only when measure="OR").'),
        k        = list(type="vector", description='number of tables included in the analysis.'),
        yi       = list(type="vector", description='the vector of outcomes'),
        vi       = list(type="vector", description='the corresponding sample variances'),
        fit.stats= list(type="data.frame", description='a list with the log-likelihood, deviance, AIC, BIC, and AICc values under the unrestricted and restricted likelihood.'),

        weights = list(type="vector", description="weights in % given to the observed effects")
)
}

binary.fixed.mh.parameters <- function(){
    apply_adjustment_to = c("only0", "all")

    params <- list("conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply_adjustment_to)

    defaults <- list("conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order = c("conf.level", "digits", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

binary.fixed.mh.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Binary Fixed-Effect Mantel-Haenszel",
                         "description" = "Performs fixed-effect meta-analysis using the Mantel-Haenszel method.",
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero.")
                          )
}


binary.fixed.mh.is.feasible <- function(binary.data, metric){
    length(binary.data@g1O1)==length(binary.data@g1O2) &&
    length(binary.data@g1O2)==length(binary.data@g2O1) &&
    length(binary.data@g2O1)==length(binary.data@g2O2) &&
         length(binary.data@g1O1) > 0
}

binary.fixed.mh.is.feasible.for.funnel <- function() {
    FALSE
}

binary.fixed.mh.overall <- function(results) {
    res <- results$res
}

binary.fixed.peto <- function(binary.data, params) {
    if (!("BinaryData" %in% class(binary.data)))
        stop("Binary data expected.")

    input.params <- params

    if (length(binary.data@g1O1) == 1) {
        res <- get.res.for.one.binary.study(binary.data, params)
        results <- list("Summary"=res,
                        "res"=res)
    } else {
           res <- rma.peto(ai=binary.data@g1O1, bi=binary.data@g1O2,
                        ci=binary.data@g2O1, di=binary.data@g2O2,
                        slab=binary.data@study.names,
                        level=params$conf.level,
                        digits=params$digits,
                        add=c(params$adjust,params$adjust),
                        to=c(as.character(params$to), as.character(params$to)),
                        drop00 = FALSE)
        pure.res <- res
        binary.data@y <- res$yi
        binary.data@SE <- sqrt(res$vi)

        if (is.null(binary.data@y) || is.null(binary.data@SE)) {
            binary.data <- compute.bin.point.estimates(binary.data, params)
        }

        metric.name <- pretty.metric.name(as.character(params$measure))
        model.title <- "Binary Fixed-Effect Model - Peto\n\nMetric: Odds Ratio"
        summary.disp <- create.summary.disp(binary.data, params, res, model.title)
        forest.path <- paste(params$fp_outpath, sep="")
        plot.data <- create.plot.data.binary(binary.data, params, res)
        changed.params <- plot.data$changed.params

		forest.plot.params.path <- ""
		if (is.null(params$supress.output) || !params$supress.output) {
	        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
	        changed.params <- c(changed.params, params.changed.in.forest.plot)
	        params <- update.changed.plot.params(params, changed.params)
	        forest.plot.params.path <- save.data(binary.data, res, params, plot.data)
		}



        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Forest Plot"=forest.path)
        plot.names <- c("forest plot"="forest_plot")
        pure.res$weights <- weights(res)
        results <- list("input_data"=binary.data,
                        "input_params"=input.params,
                        "images"=images,
                        "Summary"=capture.output.and.collapse(summary.disp),
                        "plot_names"=plot.names,
                        "plot_params_paths"=plot.params.paths,
                        "res"=pure.res,
                        "res.info"=binary.fixed.peto.value.info(),
                        "Weights"=weights(res))
    }

    results[["References"]] <- rcmetar.method.references("rma.peto")
    results
}

binary.fixed.peto.value.info <- function() {
    list(
            b        = list(type="vector", description='estimated coefficients of the model.'),
            se       = list(type="vector", description='standard errors of the coefficients.'),
            zval     = list(type="vector", description='test statistics of the coefficients.'),
            pval     = list(type="vector", description='p-values for the test statistics.'),
            ci.lb    = list(type="vector", description='lower bound of the confidence intervals for the coefficients.'),
            ci.ub    = list(type="vector", description='upper bound of the confidence intervals for the coefficients.'),
            QE       = list(type="vector", description='test statistic for the test of heterogeneity.'),
            QEp      = list(type="vector", description='p-value for the test of heterogeneity.'),
            k        = list(type="vector", description='number of tables included in the analysis'),
            yi       = list(type="vector", description='the vector of outcomes'),
            vi       = list(type="vector", description='the corresponding sample variances'),
            fit.stats= list(type="data.frame", description='a list with the log-likelihood, deviance, AIC, BIC, and AICc values under the unrestricted and restricted likelihood.'),

            weights = list(type="vector", description="weights in % given to the observed effects")
    )
}

binary.fixed.peto.parameters <- function(){
    apply_adjustment_to = c("only0", "all")

    params <- list("conf.level"="float", "digits"="int",
                   "adjust"="float", "to"=apply_adjustment_to)

    defaults <- list("conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order = c("conf.level", "digits", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

binary.fixed.peto.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Binary Fixed-Effect Peto",
                         "description" = "Performs fixed-effect meta-analysis using the Peto method.",
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero.")
                         )
}

binary.fixed.peto.is.feasible <- function(binary.data, metric){
    metric == "OR" &&
    length(binary.data@g1O1)==length(binary.data@g1O2) &&
    length(binary.data@g1O2)==length(binary.data@g2O1) &&
    length(binary.data@g2O1)==length(binary.data@g2O2) &&
         length(binary.data@g1O1) > 0
}

binary.fixed.peto.is.feasible.for.funnel <- function() {
    FALSE
}

binary.fixed.peto.overall <- function(results) {
    res <- results$res
}


binary.random <- function(binary.data, params) {
    if (!("BinaryData" %in% class(binary.data))) stop("Binary data expected.")

    results <- NULL
    input.params <- params
    inference.method <- rcmetar.validate.inference.method(params, length(binary.data@y))

    if (length(binary.data@g1O1) == 1 || length(binary.data@y) == 1){
        res <- get.res.for.one.binary.study(binary.data, params)
        results <- list("Summary"=res,
                        "res"=res)
    } else {
        res<-rma.uni(yi=binary.data@y, sei=binary.data@SE,
                     slab=binary.data@study.names,
                     method=params$rm.method, test=inference.method, level=params$conf.level,
                     digits=params$digits,
                     add=c(params$adjust,params$adjust),
                     to=as.character(params$to))
        pure.res <- res
        if (is.null(binary.data@y) || is.null(binary.data@SE)) {
            binary.data <- compute.bin.point.estimates(binary.data, params)
        }
        metric.name <- pretty.metric.name(as.character(params$measure))
        model.title <- paste("Binary Random-Effects Model\n\nMetric: ", metric.name, sep="")

        summary.disp <- create.summary.disp(binary.data, params, res, model.title)

        forest.path <- paste(params$fp_outpath, sep="")
        plot.data <- create.plot.data.binary(binary.data, params, res)
        changed.params <- plot.data$changed.params

		forest.plot.params.path <- ""
		if (is.null(params$supress.output) || !params$supress.output) {
	        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
	        changed.params <- c(changed.params, params.changed.in.forest.plot)
	        params <- update.changed.plot.params(params, changed.params)
	        forest.plot.params.path <- save.data(binary.data, res, params, plot.data)
		}


        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Forest Plot"=forest.path)
        plot.names <- c("forest plot"="forest_plot")
        pure.res$weights <- weights(res)
        results <- list("input_data"=binary.data,
                        "input_params"=input.params,
                        "images"=images,
                        "Summary"=capture.output.and.collapse(summary.disp),
                        "plot_names"=plot.names,
                        "plot_params_paths"=plot.params.paths,
                        "res"=pure.res,
                        "res.info"=binary.random.value.info(),
                        "Weights"=weights(res))
    }

    results[["References"]] <- rcmetar.unique.references(c(
        rcmetar.method.references("rma.uni.random"),
        rcmetar.inference.method.references(params)))
    results
}

binary.random.value.info <- function() {
    rma.uni.value.info()
}

binary.random.is.feasible.for.funnel <- function () {
    TRUE
}


binary.random.parameters <- function(){
    apply_adjustment_to = c("only0", "all")
    rm_method_ls <- rcmetar.random.effects.methods()
    params <- list("rm.method"=rm_method_ls, "inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int",
                   "adjust"="float", "to"=apply_adjustment_to)

    defaults <- list("rm.method"="DL", "inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order <- c("rm.method", "inference.method", "conf.level", "digits", "adjust", "to")
    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

binary.random.pretty.names <- function() {
    rm_method_names <- rcmetar.random.effects.method.names()

    pretty.names <- list("pretty.name"="Binary Random-Effects",
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

binary.random.overall <- function(results) {
    res <- results$res
}
