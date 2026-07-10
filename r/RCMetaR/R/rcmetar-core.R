# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

#' RCMetaR core analysis facade
#'
#' \code{rcmetar.run.analysis()} is the stable package entry point for the
#' rc-metastudio application. It accepts an RCMetaR data object and a
#' typed request, validates that the requested workflow is compatible with the
#' data class, dispatches to the existing statistical implementation, and
#' returns the standard RCMetaR result payload.
#'
#' This facade replaces broad direct exports. Long-standing routines such
#' as \code{binary.random()} and \code{cum.ma.binary()} remain private
#' implementation details, while application code calls this core interface so
#' that validation, dispatch, and future compatibility changes are centralized
#' in rcmetar.
#'
#' @param om.data An RCMetaR data object: \code{BinaryData},
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
#' @return A standard RCMetaR result list. The list is augmented with an
#'   \code{rcmetar.request} attribute containing the normalized dispatch
#'   request.
#'
#' @section Supported methods:
#' Use \code{rcmetar.analysis.methods()} to inspect methods known to the core
#' dispatcher. The dispatcher still calls the package's existing method
#' implementations, including \code{metafor}-based fixed and random effects,
#' Mantel-Haenszel, Peto, bivariate diagnostic, HSROC, bootstrap, subgroup,
#' cumulative, leave-one-out, and meta-regression workflows.
#'
#' @section References:
#' Result payloads include method references from the underlying implementation.
#' Use \code{rcmetar.method.references()} to inspect the statistical references
#' associated with a method family.
#'
#' @aliases rcmetar.run.analysis rcmetar.run.diagnostic.analyses rcmetar.run.permutation rcmetar.validate.analysis.request rcmetar.analysis.methods rcmetar.analysis.plot.capabilities rcmetar.available.methods rcmetar.method.parameters rcmetar.method.description rcmetar.set.global.conf.level rcmetar.get.mult.from.conf.level rcmetar.create.covariate.values rcmetar.create.binary.data rcmetar.create.continuous.data rcmetar.create.diagnostic.data rcmetar.prepare.analysis.data rcmetar.impute.binary rcmetar.impute.diagnostic rcmetar.impute.continuous.study rcmetar.impute.continuous.prepost rcmetar.back.calculate.continuous rcmetar.convert.scale rcmetar.binary.study.effect rcmetar.continuous.study.effect rcmetar.diagnostic.study.effects rcmetar.regenerate.plot.data rcmetar.save.plot.data rcmetar.draw.forest.plot rcmetar.draw.regression.plot rcmetar.graphics.off rcmetar.method.references
#' @name RCMetaR-core-api
NULL

rcmetar.analysis.methods <- function(data.type=NULL, workflow=NULL) {
    methods <- list(
        binary=list(
            standard=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            cumulative=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            "leave-one-out"=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            subgroup=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            bootstrap=c("binary.fixed.inv.var", "binary.fixed.mh", "binary.fixed.peto", "binary.random"),
            "meta-regression"=c("meta.regression")
        ),
        continuous=list(
            standard=c("continuous.fixed", "continuous.random"),
            cumulative=c("continuous.fixed", "continuous.random"),
            "leave-one-out"=c("continuous.fixed", "continuous.random"),
            subgroup=c("continuous.fixed", "continuous.random"),
            bootstrap=c("continuous.fixed", "continuous.random"),
            "meta-regression"=c("meta.regression")
        ),
        diagnostic=list(
            standard=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random", "diagnostic.hsroc", "diagnostic.bivariate.ml"),
            cumulative=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random"),
            "leave-one-out"=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random"),
            subgroup=c("diagnostic.fixed.inv.var", "diagnostic.fixed.mh", "diagnostic.fixed.peto", "diagnostic.random"),
            "meta-regression"=c("meta.regression")
        )
    )

    if (is.null(data.type)) {
        return(methods)
    }
    data.type <- .rcmetar.match.arg(tolower(as.character(data.type)), names(methods), "data.type")
    if (is.null(workflow)) {
        return(methods[[data.type]])
    }
    workflow <- .rcmetar.normalize.workflow(workflow)
    if (is.null(methods[[data.type]][[workflow]])) {
        stop(sprintf("Workflow '%s' is not supported for %s data.", workflow, data.type), call.=FALSE)
    }
    methods[[data.type]][[workflow]]
}

rcmetar.available.methods <- function(data.type=NULL, om.data=NULL, metric=NULL, workflow="standard") {
    if (is.null(data.type)) {
        if (is.null(om.data)) {
            stop("data.type or om.data is required.", call.=FALSE)
        }
        data.type <- .rcmetar.data.type(om.data)
    }

    methods <- rcmetar.analysis.methods(data.type, workflow)
    available <- c()
    for (method in methods) {
        feasible <- TRUE
        feasible.function <- paste(method, "is.feasible", sep=".")
        if (!is.null(om.data) && exists(feasible.function, mode="function")) {
            feasible <- isTRUE(eval(call(feasible.function, om.data, metric)))
        }

        if (feasible) {
            pretty.names <- .rcmetar.method.pretty.names(method)
            pretty.name <- method
            if (!is.null(pretty.names$pretty.name)) {
                pretty.name <- as.character(pretty.names$pretty.name)
            }
            available[[pretty.name]] <- method
        }
    }
    available
}

rcmetar.method.parameters <- function(method) {
    .rcmetar.validate.method.name(method)
    parameter.function <- paste(method, "parameters", sep=".")
    if (!exists(parameter.function, mode="function")) {
        stop(sprintf("Method '%s' does not expose parameters.", method), call.=FALSE)
    }
    parameters <- eval(call(parameter.function))
    parameters$pretty.names <- .rcmetar.method.pretty.names(method)
    parameters
}

rcmetar.method.description <- function(method) {
    pretty.names <- .rcmetar.method.pretty.names(method)
    if (!is.null(pretty.names$description)) {
        return(as.character(pretty.names$description))
    }
    "None provided."
}

rcmetar.analysis.plot.capabilities <- function(data.type, method, workflow="standard") {
    method <- .rcmetar.validate.method.name(method)
    data.type <- .rcmetar.match.arg(tolower(as.character(data.type)), c("binary", "continuous", "diagnostic"), "data.type")
    workflow <- .rcmetar.normalize.workflow(workflow)
    if (!(method %in% rcmetar.analysis.methods(data.type, workflow))) {
        stop(sprintf("Method '%s' is not available for %s %s analysis.", method, data.type, workflow), call.=FALSE)
    }

    descriptor <- function(plot.kind) {
        .rcmetar.plot.descriptor.for.kind(plot.kind, has.params=TRUE)
    }
    if (workflow == "cumulative") return(list(descriptor("cumulative_forest")))
    if (workflow == "leave-one-out") return(list(descriptor("leave_one_out_forest")))
    if (workflow == "subgroup") return(list(descriptor("subgroup_forest")))
    if (workflow == "bootstrap") return(list(descriptor("other")))
    if (workflow == "meta-regression") return(list(descriptor("regression")))
    if (method == "diagnostic.hsroc") {
        return(list(
            descriptor("sroc"),
            descriptor("forest")
        ))
    }
    if (method == "diagnostic.bivariate.ml") {
        return(list(
            descriptor("roc"),
            descriptor("forest")
        ))
    }
    list(descriptor("forest"))
}

rcmetar.set.global.conf.level <- function(conf.level) {
    set.global.conf.level(conf.level)
}

rcmetar.get.mult.from.conf.level <- function(conf.level=get.global.conf.level()) {
    get.mult.from.conf.level(conf.level)
}

rcmetar.create.covariate.values <- function(cov.name, cov.vals, cov.type, ref.var) {
    new("CovariateValues", cov.name=cov.name, cov.vals=cov.vals, cov.type=cov.type, ref.var=ref.var)
}

rcmetar.create.binary.data <- function(g1O1=numeric(), g1O2=numeric(), g2O1=numeric(), g2O2=numeric(),
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

rcmetar.create.continuous.data <- function(N1=numeric(), mean1=numeric(), sd1=numeric(),
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

rcmetar.create.diagnostic.data <- function(TP=numeric(), FN=numeric(), TN=numeric(), FP=numeric(),
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

rcmetar.prepare.analysis.data <- function(om.data, params) {
    params <- .rcmetar.as.params.list(params)
    data.type <- .rcmetar.data.type(om.data)
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

rcmetar.impute.binary <- function(binary.data) {
    gimpute.bin.data(binary.data)
}

rcmetar.impute.diagnostic <- function(diagnostic.data) {
    gimpute.diagnostic.data(diagnostic.data)
}

rcmetar.impute.continuous.study <- function(continuous.data, alpha) {
    args <- .rcmetar.data.frame.row.args(continuous.data)
    args$alpha <- alpha
    do.call(fillin.cont.1spell, args)
}

rcmetar.impute.continuous.prepost <- function(continuous.data, correlation, alpha) {
    args <- .rcmetar.data.frame.row.args(continuous.data)
    args$correlation <- correlation
    args$alpha <- alpha
    do.call(fillin.cont.AminusB, args)
}

rcmetar.back.calculate.continuous <- function(group1.data, group2.data, effect.data, conf.level) {
    gimpute.cont.data(group1.data, group2.data, effect.data, validate.conf.level(conf.level))
}

rcmetar.convert.scale <- function(x, metric, data.type, convert.to="display.scale", n1=NULL) {
    data.type <- .rcmetar.match.arg(tolower(as.character(data.type)), c("binary", "continuous", "diagnostic"), "data.type")
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

rcmetar.binary.study.effect <- function(e1, n1, e2=NULL, n2=NULL, two.arm=TRUE, metric="OR", conf.level=95) {
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
        display_scale=rcmetar.convert.scale(calc.scale, metric, "binary", n1=n1)
    )
}

rcmetar.continuous.study.effect <- function(n1, m1, sd1, se1=NULL, n2=NULL, m2=NULL, sd2=NULL, se2=NULL,
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
        display_scale=rcmetar.convert.scale(calc.scale, metric, "continuous")
    )
}

rcmetar.diagnostic.study.effects <- function(tp, fn, fp, tn, metrics=c("Spec", "Sens"), conf.level=95) {
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
            display_scale=rcmetar.convert.scale(calc.scale, metric, "diagnostic")
        )
    }
    effects
}

rcmetar.regenerate.plot.data <- function(om.data, res, params) {
    if (inherits(res, "rcmetar_forest_regeneration_state")) {
        res <- rcmetar.validate.forest.regeneration.state(res)
        variant <- as.character(res$variant)
        if (identical(variant, "cumulative") || identical(variant, "leave-one-out")) {
            return(rcmetar.build.sequential.metafor.bundle(
                om.data, params, res$results, variant, res$labels
            ))
        }
        if (identical(variant, "subgroup")) {
            return(rcmetar.build.subgroup.metafor.bundle(
                om.data, params, res$subgroup_data
            ))
        }
    }
    data.type <- .rcmetar.data.type(om.data)
    switch(
        data.type,
        binary=create.plot.data.binary(om.data, params, res),
        continuous=create.plot.data.continuous(om.data, params, res),
        diagnostic=create.plot.data.diagnostic(om.data, params, res)
    )
}

rcmetar.regenerate.regression.plot.data <- function(om.data, res, params) {
    if (!inherits(res, "rma")) {
        stop("Meta-regression bubble plots require a metafor rma result.", call.=FALSE)
    }
    coefficients <- as.numeric(res$b)
    fitted.line <- list(
        intercept=coefficients[[1]],
        slope=if (length(coefficients) >= 2) coefficients[[2]] else 0
    )
    create.plot.data.reg(om.data, params, fitted.line, res=res)
}

rcmetar.save.plot.data <- function(plot.data, out.path=NULL) {
    save.plot.data(plot.data, out.path)
}

rcmetar.draw.forest.plot <- function(plot.data, outpath) {
    if (rcmetar.is.metafor.forest.bundle(plot.data)) {
        return(rcmetar.draw.metafor.forest(plot.data, outpath))
    }
    stop("Forest plot data must be a metafor render bundle.", call.=FALSE)
}

rcmetar.draw.regression.plot <- function(plot.data, outpath) {
    meta.regression.plot(plot.data, outpath)
}

rcmetar.graphics.off <- function() {
    grDevices::graphics.off()
}

rcmetar.run.analysis <- function(om.data, request=NULL, method=NULL, params=list(), workflow="standard",
                                   selected.cov=NULL, cond.means.data=NULL, stop.at.rma=FALSE) {
    request <- rcmetar.validate.analysis.request(
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
        standard=.rcmetar.dispatch.standard(om.data, request),
        cumulative=.rcmetar.dispatch.meta.workflow(om.data, request),
        "leave-one-out"=.rcmetar.dispatch.meta.workflow(om.data, request),
        subgroup=.rcmetar.dispatch.meta.workflow(om.data, request),
        bootstrap=bootstrap(request$method, om.data, request$params, request$cond.means.data),
        "meta-regression"=meta.regression(om.data, request$params, request$cond.means.data, request$stop.at.rma)
    )

    result <- .rcmetar.attach.plot.display.artifacts(result, request)
    result <- .rcmetar.attach.plot.capabilities(result, request)
    .rcmetar.attach.request(result, request)
}

rcmetar.run.diagnostic.analyses <- function(diagnostic.data, methods, params.list, workflow="standard", selected.cov=NULL) {
    if (!("DiagnosticData" %in% class(diagnostic.data))) {
        stop("DiagnosticData object expected.", call.=FALSE)
    }
    if (length(methods) != length(params.list)) {
        stop("Diagnostic methods and parameter lists must have the same length.", call.=FALSE)
    }

    workflow <- .rcmetar.normalize.workflow(workflow)
    if (!(workflow %in% c("standard", "cumulative", "leave-one-out", "subgroup"))) {
        stop(sprintf("Diagnostic multi-analysis does not support workflow '%s'.", workflow), call.=FALSE)
    }

    params.list <- lapply(params.list, .rcmetar.as.params.list)
    for (i in seq_along(methods)) {
        rcmetar.validate.analysis.request(
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

    result.request <- list(
        data.type="diagnostic",
        methods=as.character(methods),
        params.list=params.list,
        workflow=workflow
    )
    result <- .rcmetar.attach.plot.display.artifacts(result, result.request)
    result <- .rcmetar.attach.plot.capabilities(result, result.request)
    attr(result, "rcmetar.request") <- result.request
    result
}

rcmetar.run.permutation <- function(data, method="DL", mods=NULL, level=95, digits=4, iter=1000,
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

rcmetar.validate.analysis.request <- function(om.data, request=NULL, method=NULL, params=list(), workflow="standard",
                                                selected.cov=NULL, cond.means.data=NULL, stop.at.rma=FALSE) {
    if (!is.null(request)) {
        if (!is.list(request)) {
            stop("Analysis request must be a named list.", call.=FALSE)
        }
        method <- .rcmetar.request.value(request, "method", method)
        params <- .rcmetar.request.value(request, "params", params)
        workflow <- .rcmetar.request.value(request, "workflow", workflow)
        selected.cov <- .rcmetar.request.value(request, "selected.cov", selected.cov)
        cond.means.data <- .rcmetar.request.value(request, "cond.means.data", cond.means.data)
        stop.at.rma <- .rcmetar.request.value(request, "stop.at.rma", stop.at.rma)
    }

    data.type <- .rcmetar.data.type(om.data)
    workflow <- .rcmetar.normalize.workflow(workflow)
    params <- .rcmetar.as.params.list(params)
    method <- as.character(method)
    if (length(method) != 1 || is.na(method) || !nzchar(method)) {
        stop("Analysis request must include one method name.", call.=FALSE)
    }

    supported <- rcmetar.analysis.methods(data.type, workflow)
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
        selected.cov <- .rcmetar.resolve.selected.cov(om.data, selected.cov, params)
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

.rcmetar.dispatch.standard <- function(om.data, request) {
    eval(call(request$method, om.data, request$params))
}

.rcmetar.dispatch.meta.workflow <- function(om.data, request) {
    meta.function <- .rcmetar.meta.workflow.function(request$data.type, request$workflow)
    if (request$data.type == "diagnostic" && request$workflow == "subgroup") {
        return(eval(call(meta.function, request$method, om.data, request$params, request$selected.cov)))
    }
    eval(call(meta.function, request$method, om.data, request$params))
}

.rcmetar.meta.workflow.function <- function(data.type, workflow) {
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

.rcmetar.data.type <- function(om.data) {
    if ("BinaryData" %in% class(om.data)) return("binary")
    if ("ContinuousData" %in% class(om.data)) return("continuous")
    if ("DiagnosticData" %in% class(om.data)) return("diagnostic")
    stop("RCMetaR data object expected: BinaryData, ContinuousData, or DiagnosticData.", call.=FALSE)
}

.rcmetar.normalize.workflow <- function(workflow) {
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

.rcmetar.resolve.selected.cov <- function(om.data, selected.cov, params) {
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

.rcmetar.as.params.list <- function(params) {
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

.rcmetar.data.frame.row.args <- function(data) {
    if (!is.data.frame(data)) {
        stop("A data frame is required.", call.=FALSE)
    }
    if (nrow(data) < 1) {
        stop("A data frame with at least one row is required.", call.=FALSE)
    }
    args <- as.list(data[1, , drop=FALSE])
    lapply(args, function(value) value[[1]])
}

.rcmetar.request.value <- function(request, name, default) {
    if (name %in% names(request)) {
        return(request[[name]])
    }
    default
}

.rcmetar.match.arg <- function(value, choices, argument.name) {
    if (length(value) != 1 || !(value %in% choices)) {
        stop(sprintf("Unknown %s '%s'. Expected one of: %s.", argument.name, paste(value, collapse=", "), paste(choices, collapse=", ")), call.=FALSE)
    }
    value
}

.rcmetar.validate.method.name <- function(method) {
    method <- as.character(method)
    if (length(method) != 1 || is.na(method) || !nzchar(method)) {
        stop("A single method name is required.", call.=FALSE)
    }
    known.methods <- unique(unlist(rcmetar.analysis.methods(), use.names=FALSE))
    if (!(method %in% known.methods)) {
        stop(sprintf("Unknown RCMetaR analysis method '%s'.", method), call.=FALSE)
    }
    method
}

.rcmetar.method.pretty.names <- function(method) {
    method <- .rcmetar.validate.method.name(method)
    pretty.function <- paste(method, "pretty.names", sep=".")
    if (exists(pretty.function, mode="function")) {
        return(eval(call(pretty.function)))
    }
    list(pretty.name=method, description="None provided.")
}

.rcmetar.attach.request <- function(result, request) {
    if (is.list(result)) {
        attr(result, "rcmetar.request") <- request
    }
    result
}

.rcmetar.request.plot.path.pairs <- function(request) {
    params.list <- if (!is.null(request$params.list)) request$params.list else list(request$params)
    pairs <- list()
    for (params in params.list) {
        for (prefix in c("fp", "bp")) {
            output.path <- rcmetar.plot.scalar_path(
                params[[paste0(prefix, "_outpath")]]
            )
            display.path <- rcmetar.plot.scalar_path(
                params[[paste0(prefix, "_display_path")]]
            )
            if (!is.null(output.path) && !is.null(display.path)) {
                pairs[[length(pairs) + 1]] <- list(
                    output=output.path,
                    display=display.path
                )
            }
        }
    }
    pairs
}

.rcmetar.attach.plot.display.artifacts <- function(result, request) {
    if (!is.list(result) || is.null(result$images) || length(result$images) == 0) {
        return(result)
    }
    pairs <- .rcmetar.request.plot.path.pairs(request)
    display.images <- character(0)
    for (title in names(result$images)) {
        image.path <- result$images[[title]]
        for (pair in pairs) {
            if (rcmetar.plot.paths.equal(image.path, pair$output) && file.exists(pair$display)) {
                display.images[[title]] <- pair$display
                break
            }
        }
    }
    if (length(display.images) > 0) {
        result$display_images <- display.images
    }
    result
}

.rcmetar.attach.plot.capabilities <- function(result, request) {
    if (!is.list(result) || is.null(result$images) || length(result$images) == 0) {
        return(result)
    }
    image.names <- names(result$images)
    if (is.null(image.names) || any(!nzchar(image.names))) {
        stop("Every RCMetaR plot artifact must have a non-empty title.", call.=FALSE)
    }
    if (is.null(result$plot_capabilities)) {
        result$plot_capabilities <- setNames(
            lapply(
                image.names,
                function(title) .rcmetar.homogeneous.plot.capability(result, request, title)
            ),
            image.names
        )
    }
    if (!setequal(names(result$plot_capabilities), image.names)) {
        stop("Plot capability descriptors must match the returned plot artifacts.", call.=FALSE)
    }
    result
}

.rcmetar.homogeneous.plot.capability <- function(result, request, title) {
    workflow <- as.character(request$workflow[[1]])
    methods <- if (!is.null(request$methods)) request$methods else request$method
    methods <- as.character(methods)

    plot.kind <- switch(
        workflow,
        cumulative="cumulative_forest",
        "leave-one-out"="leave_one_out_forest",
        subgroup="subgroup_forest",
        bootstrap="other",
        "meta-regression"="regression",
        standard={
            if (length(methods) != 1 || methods %in% c("diagnostic.hsroc", "diagnostic.bivariate.ml")) {
                stop("Heterogeneous diagnostic plot producers must declare their own capabilities.", call.=FALSE)
            }
            "forest"
        },
        stop(sprintf("No plot capability contract for workflow '%s'.", workflow), call.=FALSE)
    )
    params.paths <- result$plot_params_paths
    params.path <- if (
        !is.null(params.paths) &&
        !is.null(names(params.paths)) &&
        title %in% names(params.paths)
    ) params.paths[[title]] else NULL
    has.params <- length(params.path) == 1 &&
        !is.na(params.path) &&
        nzchar(as.character(params.path))
    .rcmetar.plot.descriptor.for.kind(plot.kind, has.params)
}

.rcmetar.plot.kind.capabilities <- function() {
    list(
        forest=list(styleable=TRUE, regenerator="forest", option.groups=TRUE),
        cumulative_forest=list(styleable=TRUE, regenerator="forest", option.groups=TRUE),
        leave_one_out_forest=list(styleable=TRUE, regenerator="forest", option.groups=TRUE),
        subgroup_forest=list(styleable=TRUE, regenerator="forest", option.groups=TRUE),
        regression=list(styleable=TRUE, regenerator="regression", option.groups=TRUE),
        roc=list(styleable=FALSE, regenerator="none", option.groups=FALSE),
        sroc=list(styleable=FALSE, regenerator="none", option.groups=FALSE),
        other=list(styleable=FALSE, regenerator="none", option.groups=FALSE)
    )
}

.rcmetar.plot.kind.capability <- function(plot.kind) {
    capabilities <- .rcmetar.plot.kind.capabilities()
    capability <- capabilities[[plot.kind]]
    if (is.null(capability)) {
        stop(sprintf("No plot capability contract for plot kind '%s'.", plot.kind), call.=FALSE)
    }
    capability
}

.rcmetar.plot.descriptor.for.kind <- function(plot.kind, has.params) {
    capability <- .rcmetar.plot.kind.capability(plot.kind)
    editable <- isTRUE(has.params) &&
        capability$regenerator != "none" &&
        isTRUE(capability$option.groups)
    .rcmetar.plot.descriptor(
        plot.kind,
        editable,
        capability$styleable,
        capability$regenerator
    )
}

.rcmetar.plot.descriptor <- function(plot.kind, editable, styleable, regenerator) {
    list(
        plot_kind=plot.kind,
        editable=isTRUE(editable),
        styleable=isTRUE(styleable),
        composition="single",
        regenerator=regenerator
    )
}
