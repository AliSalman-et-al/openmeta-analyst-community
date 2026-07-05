#' OpenMetaR core analysis facade
#'
#' \code{openmetar.run.analysis()} is the stable package entry point for the
#' OpenMeta-Analyst application. It accepts an OpenMetaR data object and a
#' typed request, validates that the requested workflow is compatible with the
#' data class, dispatches to the existing statistical implementation, and
#' returns the standard OpenMetaR result payload.
#'
#' This facade replaces the legacy exported surface. Long-standing routines such
#' as \code{binary.random()} and \code{cum.ma.binary()} remain private
#' implementation details, while application code calls this core interface so
#' that validation, dispatch, and future compatibility changes are centralized
#' in OpenMetaR.
#'
#' @param om.data An OpenMetaR data object: \code{BinaryData},
#'   \code{ContinuousData}, or \code{DiagnosticData}.
#' @param request Optional named list with entries \code{method},
#'   \code{params}, \code{workflow}, \code{selected.cov},
#'   \code{cond.means.data}, and \code{stop.at.rma}.
#' @param method Legacy convenience argument naming the base statistical method.
#' @param params Named list or one-row data frame of method parameters.
#' @param workflow One of \code{"standard"}, \code{"cumulative"},
#'   \code{"leave-one-out"}, \code{"subgroup"}, \code{"bootstrap"}, or
#'   \code{"meta-regression"}.
#' @param selected.cov Optional \code{CovariateValues} object or covariate name
#'   used by subgroup requests.
#' @param cond.means.data Optional conditional-means payload for meta-regression.
#' @param stop.at.rma Logical flag forwarded to \code{meta.regression()}.
#'
#' @return A standard OpenMetaR result list. The list is augmented with an
#'   \code{openmetar.request} attribute containing the normalized dispatch
#'   request.
#'
#' @section Supported methods:
#' Use \code{openmetar.analysis.methods()} to inspect methods known to the core
#' dispatcher. The dispatcher still calls the package's existing method
#' implementations, including \code{metafor}-based fixed and random effects,
#' Mantel-Haenszel, Peto, bivariate diagnostic, HSROC, bootstrap, subgroup,
#' cumulative, leave-one-out, and meta-regression workflows.
#'
#' @section References:
#' Result payloads include method references from the underlying implementation.
#' Use \code{openmetar.method.references()} to inspect the statistical references
#' associated with a method family.
#'
#' @aliases openmetar.run.analysis openmetar.run.diagnostic.analyses openmetar.run.permutation openmetar.validate.analysis.request openmetar.analysis.methods openmetar.available.methods openmetar.method.parameters openmetar.method.description openmetar.set.global.conf.level openmetar.get.mult.from.conf.level openmetar.create.covariate.values openmetar.create.binary.data openmetar.create.continuous.data openmetar.create.diagnostic.data openmetar.prepare.analysis.data openmetar.impute.binary openmetar.impute.diagnostic openmetar.impute.continuous.study openmetar.impute.continuous.prepost openmetar.back.calculate.continuous openmetar.convert.scale openmetar.binary.study.effect openmetar.continuous.study.effect openmetar.diagnostic.study.effects openmetar.regenerate.plot.data openmetar.save.plot.data openmetar.draw.forest.plot openmetar.draw.regression.plot openmetar.graphics.off openmetar.method.references
#' @name openmetar-core-api
NULL

openmetar.analysis.methods <- function(data.type=NULL, workflow=NULL) {
    methods <- list(
        binary=list(
            standard=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            cumulative=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            "leave-one-out"=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            subgroup=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            bootstrap=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            "meta-regression"=c("meta.regression", "binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random")
        ),
        continuous=list(
            standard=c("continuous.fixed", "continuous.random"),
            cumulative=c("continuous.fixed", "continuous.random"),
            "leave-one-out"=c("continuous.fixed", "continuous.random"),
            subgroup=c("continuous.fixed", "continuous.random"),
            bootstrap=c("continuous.fixed", "continuous.random"),
            "meta-regression"=c("meta.regression", "continuous.fixed", "continuous.random")
        ),
        diagnostic=list(
            standard=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random", "diagnostic.hsroc", "diagnostic.bivariate.ml"),
            cumulative=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random"),
            "leave-one-out"=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random"),
            subgroup=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random"),
            "meta-regression"=c("meta.regression", "diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random")
        )
    )

    if (is.null(data.type)) {
        return(methods)
    }
    data.type <- .openmetar.match.arg(tolower(as.character(data.type)), names(methods), "data.type")
    if (is.null(workflow)) {
        return(methods[[data.type]])
    }
    workflow <- .openmetar.normalize.workflow(workflow)
    if (is.null(methods[[data.type]][[workflow]])) {
        stop(sprintf("Workflow '%s' is not supported for %s data.", workflow, data.type), call.=FALSE)
    }
    methods[[data.type]][[workflow]]
}

openmetar.available.methods <- function(data.type=NULL, om.data=NULL, metric=NULL, workflow="standard") {
    if (is.null(data.type)) {
        if (is.null(om.data)) {
            stop("data.type or om.data is required.", call.=FALSE)
        }
        data.type <- .openmetar.data.type(om.data)
    }

    methods <- openmetar.analysis.methods(data.type, workflow)
    available <- c()
    for (method in methods) {
        feasible <- TRUE
        feasible.function <- paste(method, "is.feasible", sep=".")
        if (!is.null(om.data) && exists(feasible.function, mode="function")) {
            feasible <- isTRUE(eval(call(feasible.function, om.data, metric)))
        }

        if (feasible) {
            pretty.names <- .openmetar.method.pretty.names(method)
            pretty.name <- method
            if (!is.null(pretty.names$pretty.name)) {
                pretty.name <- as.character(pretty.names$pretty.name)
            }
            available[[pretty.name]] <- method
        }
    }
    available
}

openmetar.method.parameters <- function(method) {
    .openmetar.validate.method.name(method)
    parameter.function <- paste(method, "parameters", sep=".")
    if (!exists(parameter.function, mode="function")) {
        stop(sprintf("Method '%s' does not expose parameters.", method), call.=FALSE)
    }
    parameters <- eval(call(parameter.function))
    parameters$pretty.names <- .openmetar.method.pretty.names(method)
    parameters
}

openmetar.method.description <- function(method) {
    pretty.names <- .openmetar.method.pretty.names(method)
    if (!is.null(pretty.names$description)) {
        return(as.character(pretty.names$description))
    }
    "None provided."
}

openmetar.set.global.conf.level <- function(conf.level) {
    set.global.conf.level(conf.level)
}

openmetar.get.mult.from.conf.level <- function(conf.level=get.global.conf.level()) {
    get.mult.from.conf.level(conf.level)
}

openmetar.create.covariate.values <- function(cov.name, cov.vals, cov.type, ref.var) {
    new("CovariateValues", cov.name=cov.name, cov.vals=cov.vals, cov.type=cov.type, ref.var=ref.var)
}

openmetar.create.binary.data <- function(g1O1=numeric(), g1O2=numeric(), g2O1=numeric(), g2O2=numeric(),
                                         y=numeric(), SE=numeric(), study.names=character(),
                                         years=integer(), covariates=list()) {
    new(
        "BinaryData",
        g1O1=g1O1,
        g1O2=g1O2,
        g2O1=g2O1,
        g2O2=g2O2,
        y=y,
        SE=SE,
        study.names=study.names,
        years=as.integer(years),
        covariates=covariates
    )
}

openmetar.create.continuous.data <- function(N1=numeric(), mean1=numeric(), sd1=numeric(),
                                             N2=numeric(), mean2=numeric(), sd2=numeric(),
                                             y=numeric(), SE=numeric(), study.names=character(),
                                             years=integer(), covariates=list()) {
    new(
        "ContinuousData",
        N1=N1,
        mean1=mean1,
        sd1=sd1,
        N2=N2,
        mean2=mean2,
        sd2=sd2,
        y=y,
        SE=SE,
        study.names=study.names,
        years=as.integer(years),
        covariates=covariates
    )
}

openmetar.create.diagnostic.data <- function(TP=numeric(), FN=numeric(), TN=numeric(), FP=numeric(),
                                             y=numeric(), SE=numeric(), study.names=character(),
                                             years=integer(), covariates=list()) {
    new(
        "DiagnosticData",
        TP=TP,
        FN=FN,
        TN=TN,
        FP=FP,
        y=y,
        SE=SE,
        study.names=study.names,
        years=as.integer(years),
        covariates=covariates
    )
}

openmetar.prepare.analysis.data <- function(om.data, params) {
    params <- .openmetar.as.params.list(params)
    data.type <- .openmetar.data.type(om.data)
    switch(
        data.type,
        binary=compute.bin.point.estimates(om.data, params),
        continuous={
            effect <- compute.for.one.cont.study(om.data, params)
            om.data@y <- effect$yi
            om.data@SE <- sqrt(effect$vi)
            om.data
        },
        diagnostic=compute.diag.point.estimates(om.data, params)
    )
}

openmetar.impute.binary <- function(binary.data) {
    gimpute.bin.data(binary.data)
}

openmetar.impute.diagnostic <- function(diagnostic.data) {
    gimpute.diagnostic.data(diagnostic.data)
}

openmetar.impute.continuous.study <- function(continuous.data, alpha) {
    args <- .openmetar.data.frame.row.args(continuous.data)
    args$alpha <- alpha
    do.call(fillin.cont.1spell, args)
}

openmetar.impute.continuous.prepost <- function(continuous.data, correlation, alpha) {
    args <- .openmetar.data.frame.row.args(continuous.data)
    args$correlation <- correlation
    args$alpha <- alpha
    do.call(fillin.cont.AminusB, args)
}

openmetar.back.calculate.continuous <- function(group1.data, group2.data, effect.data, conf.level) {
    gimpute.cont.data(group1.data, group2.data, effect.data, validate.conf.level(conf.level))
}

openmetar.convert.scale <- function(x, metric, data.type, convert.to="display.scale", n1=NULL) {
    data.type <- .openmetar.match.arg(tolower(as.character(data.type)), c("binary", "continuous", "diagnostic"), "data.type")
    transform.function <- switch(
        data.type,
        binary=binary.transform.f(metric),
        continuous=continuous.transform.f(metric),
        diagnostic=diagnostic.transform.f(metric)
    )
    if (is.null(x)) {
        return(NULL)
    }
    if (identical(metric, "PFT")) {
        return(transform.function[[convert.to]](x=x, ni=n1))
    }
    transform.function[[convert.to]](x)
}

openmetar.binary.study.effect <- function(e1, n1, e2=NULL, n2=NULL, two.arm=TRUE, metric="OR", conf.level=95) {
    conf.level <- validate.conf.level(conf.level)
    if (isTRUE(two.arm)) {
        effect <- escalc(measure=metric, ai=c(e1), n1i=c(n1), ci=c(e2), n2i=c(n2))
    } else {
        effect <- escalc(measure=metric, xi=c(e1), ni=c(n1))
    }
    point.estimate <- effect[1, 1]
    se <- sqrt(effect[1, 2])
    mult <- abs(stats::qnorm((1 - conf.level / 100) / 2))
    calc.scale <- c(point.estimate, point.estimate - mult * se, point.estimate + mult * se)
    list(
        calc_scale=calc.scale,
        display_scale=openmetar.convert.scale(calc.scale, metric, "binary", n1=n1)
    )
}

openmetar.continuous.study.effect <- function(n1, m1, sd1, se1=NULL, n2=NULL, m2=NULL, sd2=NULL, se2=NULL,
                                              metric="MD", two.arm=TRUE, conf.level=95) {
    conf.level <- validate.conf.level(conf.level)
    if (isTRUE(two.arm)) {
        if (!is.null(se1) && !is.null(se2) && metric == "MD") {
            point.estimate <- m1 - m2
            se <- sqrt(sum(c(se1, se2)^2))
        } else {
            effect <- escalc(metric, n1i=c(n1), n2i=c(n2), m1i=c(m1), m2i=c(m2), sd1i=c(sd1), sd2i=c(sd2))
            point.estimate <- effect[1, 1]
            se <- sqrt(effect[1, 2])
        }
    } else {
        point.estimate <- m1
        se <- sd1 / sqrt(n1)
    }
    mult <- abs(stats::qnorm((1 - conf.level / 100) / 2))
    calc.scale <- c(point.estimate, point.estimate - mult * se, point.estimate + mult * se)
    list(
        calc_scale=calc.scale,
        display_scale=openmetar.convert.scale(calc.scale, metric, "continuous")
    )
}

openmetar.diagnostic.study.effects <- function(tp, fn, fp, tn, metrics=c("Spec", "Sens"), conf.level=95) {
    conf.level <- validate.conf.level(conf.level)
    diagnostic.data <- new("DiagnosticData", TP=c(tp), FN=c(fn), TN=c(tn), FP=c(fp))
    effects <- list()
    for (metric in metrics) {
        result <- get.res.for.one.diag.study(
            diagnostic.data,
            list(to="only0", measure=metric, conf.level=conf.level, adjust=0.5)
        )
        calc.scale <- c(result$b[[1]], result$ci.lb[[1]], result$ci.ub[[1]])
        effects[[metric]] <- list(
            calc_scale=calc.scale,
            display_scale=openmetar.convert.scale(calc.scale, metric, "diagnostic")
        )
    }
    effects
}

openmetar.regenerate.plot.data <- function(om.data, res, params) {
    data.type <- .openmetar.data.type(om.data)
    switch(
        data.type,
        binary=create.plot.data.binary(om.data, params, res),
        continuous=create.plot.data.continuous(om.data, params, res),
        diagnostic=create.plot.data.diagnostic(om.data, params, res)
    )
}

openmetar.save.plot.data <- function(plot.data, out.path=NULL) {
    save.plot.data(plot.data, out.path)
}

openmetar.draw.forest.plot <- function(plot.data, outpath, side.by.side=FALSE) {
    if (isTRUE(side.by.side)) {
        return(two.forest.plots(plot.data, outpath))
    }
    forest.plot(plot.data, outpath)
}

openmetar.draw.regression.plot <- function(plot.data, outpath) {
    meta.regression.plot(plot.data, outpath)
}

openmetar.graphics.off <- function() {
    grDevices::graphics.off()
}

openmetar.run.analysis <- function(om.data, request=NULL, method=NULL, params=list(), workflow="standard",
                                   selected.cov=NULL, cond.means.data=NULL, stop.at.rma=FALSE) {
    request <- openmetar.validate.analysis.request(
        om.data=om.data,
        request=request,
        method=method,
        params=params,
        workflow=workflow,
        selected.cov=selected.cov,
        cond.means.data=cond.means.data,
        stop.at.rma=stop.at.rma
    )

    result <- switch(
        request$workflow,
        standard=.openmetar.dispatch.standard(om.data, request),
        cumulative=.openmetar.dispatch.meta.workflow(om.data, request),
        "leave-one-out"=.openmetar.dispatch.meta.workflow(om.data, request),
        subgroup=.openmetar.dispatch.meta.workflow(om.data, request),
        bootstrap=bootstrap(request$method, om.data, request$params, request$cond.means.data),
        "meta-regression"=meta.regression(om.data, request$params, request$cond.means.data, request$stop.at.rma)
    )

    .openmetar.attach.request(result, request)
}

openmetar.run.diagnostic.analyses <- function(diagnostic.data, methods, params.list, workflow="standard", selected.cov=NULL) {
    if (!("DiagnosticData" %in% class(diagnostic.data))) {
        stop("DiagnosticData object expected.", call.=FALSE)
    }
    if (length(methods) != length(params.list)) {
        stop("Diagnostic methods and parameter lists must have the same length.", call.=FALSE)
    }

    workflow <- .openmetar.normalize.workflow(workflow)
    if (!(workflow %in% c("standard", "cumulative", "leave-one-out", "subgroup"))) {
        stop(sprintf("Diagnostic multi-analysis does not support workflow '%s'.", workflow), call.=FALSE)
    }

    params.list <- lapply(params.list, .openmetar.as.params.list)
    for (i in seq_along(methods)) {
        openmetar.validate.analysis.request(
            diagnostic.data,
            method=methods[[i]],
            params=params.list[[i]],
            workflow=workflow,
            selected.cov=selected.cov
        )
    }

    result <- switch(
        workflow,
        standard=multiple.diagnostic(methods, params.list, diagnostic.data),
        cumulative=multiple.cum.ma.diagnostic(methods, params.list, diagnostic.data),
        "leave-one-out"=multiple.loo.diagnostic(methods, params.list, diagnostic.data),
        subgroup=multiple.subgroup.diagnostic(methods, params.list, diagnostic.data)
    )

    attr(result, "openmetar.request") <- list(
        data.type="diagnostic",
        methods=as.character(methods),
        params.list=params.list,
        workflow=workflow
    )
    result
}

openmetar.run.permutation <- function(data, method="DL", mods=NULL, level=95, digits=4, iter=1000,
                                      exact=FALSE, retpermdist=FALSE, ...) {
    if (!is.data.frame(data)) {
        stop("Permutation data must be a data frame.", call.=FALSE)
    }
    required <- c("yi", "vi", "slab")
    missing <- setdiff(required, names(data))
    if (length(missing) > 0) {
        stop(sprintf("Permutation data missing required columns: %s.", paste(missing, collapse=", ")), call.=FALSE)
    }
    if (is.null(mods)) {
        return(permuted.ma(data, method=method, level=level, digits=digits, iter=iter,
                           exact=exact, retpermdist=retpermdist, ...))
    }
    permuted.meta.reg(data, method=method, mods=mods, level=level, digits=digits, iter=iter,
                      exact=exact, retpermdist=retpermdist, ...)
}

openmetar.validate.analysis.request <- function(om.data, request=NULL, method=NULL, params=list(), workflow="standard",
                                                selected.cov=NULL, cond.means.data=NULL, stop.at.rma=FALSE) {
    if (!is.null(request)) {
        if (!is.list(request)) {
            stop("Analysis request must be a named list.", call.=FALSE)
        }
        method <- .openmetar.request.value(request, "method", method)
        params <- .openmetar.request.value(request, "params", params)
        workflow <- .openmetar.request.value(request, "workflow", workflow)
        selected.cov <- .openmetar.request.value(request, "selected.cov", selected.cov)
        cond.means.data <- .openmetar.request.value(request, "cond.means.data", cond.means.data)
        stop.at.rma <- .openmetar.request.value(request, "stop.at.rma", stop.at.rma)
    }

    data.type <- .openmetar.data.type(om.data)
    workflow <- .openmetar.normalize.workflow(workflow)
    params <- .openmetar.as.params.list(params)
    method <- as.character(method)
    if (length(method) != 1 || is.na(method) || !nzchar(method)) {
        stop("Analysis request must include one method name.", call.=FALSE)
    }

    supported <- openmetar.analysis.methods(data.type, workflow)
    if (!(method %in% supported)) {
        stop(
            sprintf(
                "Method '%s' is not supported for %s data with workflow '%s'. Supported methods: %s.",
                method, data.type, workflow, paste(supported, collapse=", ")
            ),
            call.=FALSE
        )
    }
    if (!exists(method, mode="function")) {
        stop(sprintf("Method implementation '%s' is not available.", method), call.=FALSE)
    }

    if (!is.null(params$conf.level)) {
        validate.conf.level(params$conf.level)
    }
    if (!is.null(params$measure) && !nzchar(as.character(params$measure))) {
        stop("Parameter 'measure' must not be empty.", call.=FALSE)
    }

    if (workflow == "subgroup") {
        selected.cov <- .openmetar.resolve.selected.cov(om.data, selected.cov, params)
    }

    list(
        data.type=data.type,
        method=method,
        params=params,
        workflow=workflow,
        selected.cov=selected.cov,
        cond.means.data=cond.means.data,
        stop.at.rma=isTRUE(stop.at.rma)
    )
}

.openmetar.dispatch.standard <- function(om.data, request) {
    eval(call(request$method, om.data, request$params))
}

.openmetar.dispatch.meta.workflow <- function(om.data, request) {
    meta.function <- .openmetar.meta.workflow.function(request$data.type, request$workflow)
    if (request$data.type == "diagnostic" && request$workflow == "subgroup") {
        return(eval(call(meta.function, request$method, om.data, request$params, request$selected.cov)))
    }
    eval(call(meta.function, request$method, om.data, request$params))
}

.openmetar.meta.workflow.function <- function(data.type, workflow) {
    functions <- list(
        binary=list(cumulative="cum.ma.binary", "leave-one-out"="loo.ma.binary", subgroup="subgroup.ma.binary"),
        continuous=list(cumulative="cum.ma.continuous", "leave-one-out"="loo.ma.continuous", subgroup="subgroup.ma.continuous"),
        diagnostic=list(cumulative="cum.ma.diagnostic", "leave-one-out"="loo.ma.diagnostic", subgroup="subgroup.ma.diagnostic")
    )
    function.name <- functions[[data.type]][[workflow]]
    if (is.null(function.name)) {
        stop(sprintf("Workflow '%s' is not supported for %s data.", workflow, data.type), call.=FALSE)
    }
    function.name
}

.openmetar.data.type <- function(om.data) {
    if ("BinaryData" %in% class(om.data)) return("binary")
    if ("ContinuousData" %in% class(om.data)) return("continuous")
    if ("DiagnosticData" %in% class(om.data)) return("diagnostic")
    stop("OpenMetaR data object expected: BinaryData, ContinuousData, or DiagnosticData.", call.=FALSE)
}

.openmetar.normalize.workflow <- function(workflow) {
    aliases <- c(
        standard="standard",
        basic="standard",
        cumulative="cumulative",
        "cum.ma"="cumulative",
        "leave-one-out"="leave-one-out",
        loo="leave-one-out",
        "loo.ma"="leave-one-out",
        subgroup="subgroup",
        "subgroup.ma"="subgroup",
        bootstrap="bootstrap",
        "meta-regression"="meta-regression",
        "meta.regression"="meta-regression"
    )
    workflow <- tolower(as.character(workflow))
    if (length(workflow) != 1 || !(workflow %in% names(aliases))) {
        stop(
            sprintf(
                "Unknown analysis workflow '%s'. Expected one of: %s.",
                paste(workflow, collapse=", "), paste(unique(unname(aliases)), collapse=", ")
            ),
            call.=FALSE
        )
    }
    unname(aliases[[workflow]])
}

.openmetar.resolve.selected.cov <- function(om.data, selected.cov, params) {
    if (!is.null(selected.cov) && ("CovariateValues" %in% class(selected.cov))) {
        return(selected.cov)
    }

    cov.name <- selected.cov
    if (is.null(cov.name) && !is.null(params$cov_name)) {
        cov.name <- params$cov_name
    }
    cov.name <- as.character(cov.name)
    if (length(cov.name) != 1 || is.na(cov.name) || !nzchar(cov.name)) {
        stop("Subgroup analysis requires 'cov_name' or a selected CovariateValues object.", call.=FALSE)
    }

    covariate <- get.cov(om.data, cov.name)
    if (is.null(covariate)) {
        stop(sprintf("Covariate '%s' was not found in the analysis data.", cov.name), call.=FALSE)
    }
    covariate
}

.openmetar.as.params.list <- function(params) {
    if (is.null(params)) {
        return(list())
    }
    if (is.data.frame(params)) {
        params <- as.list(params)
        params <- lapply(params, function(x) if (length(x) == 1) x[[1]] else x)
    }
    if (!is.list(params)) {
        stop("Analysis parameters must be a named list or data frame.", call.=FALSE)
    }
    if (is.null(names(params)) || any(!nzchar(names(params)))) {
        stop("Analysis parameters must be named.", call.=FALSE)
    }
    params
}

.openmetar.data.frame.row.args <- function(data) {
    if (!is.data.frame(data)) {
        stop("A data frame is required.", call.=FALSE)
    }
    if (nrow(data) < 1) {
        stop("A data frame with at least one row is required.", call.=FALSE)
    }
    args <- as.list(data[1, , drop=FALSE])
    lapply(args, function(value) value[[1]])
}

.openmetar.request.value <- function(request, name, default) {
    if (name %in% names(request)) {
        return(request[[name]])
    }
    default
}

.openmetar.match.arg <- function(value, choices, argument.name) {
    if (length(value) != 1 || !(value %in% choices)) {
        stop(sprintf("Unknown %s '%s'. Expected one of: %s.", argument.name, paste(value, collapse=", "), paste(choices, collapse=", ")), call.=FALSE)
    }
    value
}

.openmetar.validate.method.name <- function(method) {
    method <- as.character(method)
    if (length(method) != 1 || is.na(method) || !nzchar(method)) {
        stop("A single method name is required.", call.=FALSE)
    }
    known.methods <- unique(unlist(openmetar.analysis.methods(), use.names=FALSE))
    if (!(method %in% known.methods)) {
        stop(sprintf("Unknown OpenMetaR analysis method '%s'.", method), call.=FALSE)
    }
    method
}

.openmetar.method.pretty.names <- function(method) {
    method <- .openmetar.validate.method.name(method)
    pretty.function <- paste(method, "pretty.names", sep=".")
    if (exists(pretty.function, mode="function")) {
        return(eval(call(pretty.function)))
    }
    list(pretty.name=method, description="None provided.")
}

.openmetar.attach.request <- function(result, request) {
    if (is.list(result)) {
        attr(result, "openmetar.request") <- request
    }
    result
}
