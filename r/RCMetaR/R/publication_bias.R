# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
#' RCMetaR implementation of the guided small-study effects analysis.
#'
#' The function is intentionally one package boundary: conversion, eligibility,
#' validation, model fitting, tests, and plot artifacts are created from the
#' same included study set.  The Python side only renders the returned report.

.small.study.eligibility <- function(om.data, params=list(), prepared=NULL) {
    if (!is(om.data, "OMData")) stop("RCMetaR data expected.")
    k <- length(om.data@study.names)
    metric <- as.character(params$metric %||% "")
    data.type <- as.character(params$data.type %||% if (is(om.data, "BinaryData")) "binary" else if (is(om.data, "ContinuousData")) "continuous" else "diagnostic")
    confidence.level <- .small.study.confidence.level(params)
    if (is.null(prepared)) {
        prepared <- tryCatch(.small.study.reconstruct(om.data, metric, params), error=function(e) list(y=om.data@y, se=om.data@SE, raw=FALSE))
    }
    # This report owns the canonical set.  Preparation, every fit, reporting,
    # and plot construction consume these indices rather than each deciding
    # which rows happen to be usable.
    included.indices <- which(is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0)
    standard.error <- prepared$se[included.indices]
    methods <- list()
    add <- function(method, available, reason="", required.inputs=character(), warnings=character(), role="none", usable.count=length(standard.error)) {
        methods[[length(methods)+1L]] <<- list(
            method=method, available=isTRUE(available), reason=reason,
            required.inputs=required.inputs, usable.studies=usable.count,
            warnings=warnings, role=role
        )
    }
    enough <- length(standard.error) >= 3L
    variance.ok <- enough && length(unique(standard.error)) > 1L
    default.k.ok <- length(standard.error) >= 10L
    classical <- variance.ok && default.k.ok
    k.warning <- if (enough && !default.k.ok) "Disabled by default below 10 usable studies." else character()
    standard.error.warning <- if (data.type == "diagnostic") character() else if (length(standard.error))
        "Observed standard-error range should be considered when interpreting asymmetry results; the exact range is reported in the analysis summary."
    else character()
    common.warning <- c(k.warning, standard.error.warning)
    variance.reason <- if (!enough) "Unavailable: fewer than 3 usable included studies." else if (!variance.ok) "Unavailable: standard-error predictor variance is zero." else if (!default.k.ok) k.warning else ""
    if (data.type == "diagnostic") {
        diag.model <- if (identical(metric, "DOR") && isTRUE(prepared$raw))
            tryCatch(.small.study.native.model(om.data, params, metric, is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0, prepared$y, prepared$se), error=function(e) NULL) else NULL
        ess <- if (!is.null(diag.model)) 4 * diag.model$n.e * diag.model$n.c / (diag.model$n.e + diag.model$n.c) else numeric()
        diag.keep <- is.finite(ess) & ess > 0 & is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
        diag.predictor <- if (length(ess)) 1 / sqrt(ess[diag.keep]) else numeric()
        diag.k <- sum(diag.keep)
        diag.default.k.ok <- diag.k >= 10L
        diag.predictor.ok <- diag.k >= 3L && length(unique(diag.predictor)) > 1L && all(is.finite(diag.predictor))
        deeks.ok <- identical(metric, "DOR") && isTRUE(prepared$raw) && diag.k >= 3L && diag.default.k.ok && diag.predictor.ok
        reason <- if (!identical(metric, "DOR")) "Unavailable: Deeks is available only for diagnostic DOR." else if (!isTRUE(prepared$raw)) "Unavailable: complete TP/FN/FP/TN counts are required; entered DOR without counts is not eligible." else if (diag.k < 3L) "Unavailable: fewer than 3 usable included studies." else if (!diag.default.k.ok) "Disabled by default below 10 usable studies." else if (!diag.predictor.ok) "Unavailable: Deeks effective-sample-size predictor variance is zero or non-finite." else ""
        add("deeks", deeks.ok, reason, c("TP", "FN", "FP", "TN", "one independent contribution per study, threshold, reader, and test", "ESS=4*n.e*n.c/(n.e+n.c)"), c(common.warning, "Deeks uses effective-sample-size geometry and native ESS weights."), if (deeks.ok) "primary" else "none", usable.count=diag.k)
    } else if (metric == "OR") {
        tau <- params$reml.tau2
        tau.available <- is.numeric(tau) && length(tau) == 1L && is.finite(tau)
        if (!tau.available && isTRUE(prepared$raw)) {
            raw.keep <- is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
            tau.fit <- tryCatch(.small.study.prepared.model(
                prepared$y[raw.keep], prepared$se[raw.keep], om.data@study.names[raw.keep], metric,
                confidence.level=.small.study.confidence.level(params)
            ), error=function(e) NULL)
            tau <- if (!is.null(tau.fit)) tau.fit$tau2 else NA_real_
            tau.available <- is.numeric(tau) && length(tau) == 1L && is.finite(tau)
        }
        or.keep <- is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
        or.model <- if (isTRUE(prepared$raw)) tryCatch(.small.study.native.model(om.data, params, metric, or.keep, prepared$y[or.keep], prepared$se[or.keep]), error=function(e) NULL) else NULL
        or.k <- if (!is.null(or.model)) as.integer(or.model$k) else 0L
        or.enough <- or.k >= 3L
        or.default.k.ok <- or.k >= 10L
        harbord.fit <- if (!is.null(or.model)) tryCatch(meta::metabias(or.model, method.bias="Harbord", k.min=3, level=.small.study.meta.level(confidence.level)), error=function(e) e) else NULL
        peters.fit <- if (!is.null(or.model)) tryCatch(meta::metabias(or.model, method.bias="Peters", k.min=3, level=.small.study.meta.level(confidence.level)), error=function(e) e) else NULL
        # Rucker must use the same finite prepared-study set as the other OR
        # methods; native ASD construction must not reintroduce double-zero rows.
        asd.keep <- if (isTRUE(prepared$raw)) which(or.keep) else integer()
        asd.fit <- if (length(asd.keep)) tryCatch(.small.study.asd.model(om.data, params, asd.keep), error=function(e) NULL) else NULL
        asd.test <- if (!is.null(asd.fit)) tryCatch(meta::metabias(asd.fit, method.bias="Thompson", k.min=3, level=.small.study.meta.level(confidence.level)), error=function(e) e) else NULL
        harbord.predictor.ok <- !inherits(harbord.fit, "error")
        peters.predictor.ok <- !inherits(peters.fit, "error")
        asd.predictor.ok <- !inherits(asd.test, "error")
        harbord.ok <- isTRUE(prepared$raw) && or.enough && or.default.k.ok && harbord.predictor.ok && tau.available && tau <= 0.1
        harbord.reason <- if (!isTRUE(prepared$raw)) "Unavailable: complete two-arm raw counts are required for Harbord." else if (!or.enough) "Unavailable: fewer than 3 usable included studies." else if (!or.default.k.ok) "Disabled by default below 10 usable studies." else if (!harbord.predictor.ok) "Unavailable: Harbord score predictor variance is zero or non-finite." else if (!tau.available) "Unavailable: REML log-OR tau^2 is unavailable; no primary fallback is selected." else if (tau > 0.1) "Unavailable: REML log-OR tau^2 is above 0.1; use R\u00fccker AS+RE." else ""
        add("harbord", harbord.ok, harbord.reason, c("two-arm counts", "REML log-OR tau^2"), common.warning, if (harbord.ok) "primary" else "none", usable.count=or.k)
        asd.k <- if (!is.null(asd.fit)) as.integer(asd.fit$k) else 0L
        asd.default.k.ok <- asd.k >= 10L
        # AS+RE is always an eligible companion once its own model and
        # predictor are estimable.  Routing controls its role (sensitivity
        # beside Harbord, primary when Harbord is unavailable), not whether a
        # valid sensitivity analysis can be requested.
        rucker.ok <- isTRUE(prepared$raw) && asd.k >= 3L && asd.default.k.ok && asd.predictor.ok && tau.available
        rucker.reason <- if (!isTRUE(prepared$raw)) "Unavailable: complete two-arm raw counts are required for R\u00fccker AS+RE." else if (asd.k < 3L) "Unavailable: fewer than 3 usable included studies." else if (!asd.default.k.ok) "Disabled by default below 10 usable studies." else if (!asd.predictor.ok) "Unavailable: ASD standard-error predictor variance is zero or non-finite." else if (!tau.available) "Unavailable: REML log-OR tau^2 is unavailable; no primary fallback is selected." else ""
        rucker.role <- if (rucker.ok && harbord.ok) "sensitivity" else if (rucker.ok) "primary" else "none"
        add("rucker-as-re", rucker.ok, rucker.reason, c("two-arm counts", "AS+RE model"), common.warning, rucker.role, usable.count=asd.k)
        peters.reason <- if (!isTRUE(prepared$raw)) "Unavailable: complete two-arm raw counts are required for Peters." else if (!or.enough) "Unavailable: fewer than 3 usable included studies." else if (!or.default.k.ok) "Disabled by default below 10 usable studies." else if (!peters.predictor.ok) "Unavailable: Peters sample-size predictor variance is zero or non-finite." else ""
        add("peters", isTRUE(prepared$raw) && or.enough && or.default.k.ok && peters.predictor.ok, peters.reason, c("two-arm counts", "Peters sample-size predictor"), common.warning, "sensitivity", usable.count=or.k)
    } else if (metric == "SMD") {
        smd.model <- if (isTRUE(prepared$raw)) tryCatch(.small.study.native.model(om.data, params, metric, is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0, prepared$y, prepared$se), error=function(e) NULL) else NULL
        pustejovsky.fit <- if (!is.null(smd.model)) tryCatch(meta::metabias(smd.model, method.bias="Pustejovsky", k.min=3, level=.small.study.meta.level(confidence.level)), error=function(e) e) else NULL
        smd.predictor.ok <- !inherits(pustejovsky.fit, "error")
        smd.k <- if (!is.null(smd.model)) as.integer(smd.model$k) else 0L
        smd.default.k.ok <- smd.k >= 10L
        ok <- isTRUE(prepared$raw) && smd.k >= 3L && smd.default.k.ok && smd.predictor.ok
        reason <- if (!isTRUE(prepared$raw)) "Unavailable: independent two-group sample sizes, means, and SDs are required." else if (smd.k < 3L) "Unavailable: fewer than 3 usable included studies." else if (!smd.default.k.ok) "Disabled by default below 10 usable studies." else if (!smd.predictor.ok) "Unavailable: Pustejovsky predictor variance is zero or non-finite." else ""
        add("pustejovsky-rodgers", ok, reason, c("independent two-group data"), common.warning, if (ok) "primary" else "none")
        egger.ok <- enough && default.k.ok && variance.ok
        egger.reason <- if (!enough) "Unavailable: fewer than 3 usable included studies." else if (!default.k.ok) k.warning else if (!variance.ok) "Unavailable: standard-error predictor variance is zero." else ""
        add("classical-egger", egger.ok, egger.reason, c("entered effect estimates", "standard errors", "effect-SE artifact caveat"), common.warning, if (egger.ok) "sensitivity" else "none")
    } else {
        add("classical-egger", classical, variance.reason, c("effect estimates", "standard errors", "standard-error-range report"), common.warning, if (classical) "primary" else "none")
        add("mixed-effects-egger", classical, variance.reason, c("effect estimates", "standard errors", "REML model", "standard-error-range report"), common.warning, if (variance.ok) "exploratory" else "none")
        add("begg-mazumdar", classical, variance.reason, c("effect estimates", "standard errors", "rank-correlation test", "standard-error-range report"), common.warning, if (variance.ok) "exploratory" else "none")
    }
    if (metric %in% c("RR", "RD", "PR", "PLN", "PLO", "PAS", "PFT")) {
        for (i in seq_along(methods)) {
            methods[[i]]$available <- FALSE
            methods[[i]]$role <- "none"
            methods[[i]]$reason <- "No automatic primary asymmetry test is configured for this effect measure."
        }
    }
    warnings <- standard.error.warning
    if (data.type == "diagnostic" && length(diag.predictor)) warnings <- c(warnings, paste0("Observed Deeks ESS predictor range: [", .small.study.exact.number(min(diag.predictor)), ", ", .small.study.exact.number(max(diag.predictor)), "]."))
    if (metric %in% c("PR", "PLN", "PLO", "PAS", "PFT")) warnings <- c(warnings, "One-arm proportion results are descriptive effect-SE artifacts; no formal automatic primary asymmetry test is configured.")
    if (metric %in% c("RR", "RD")) warnings <- c(warnings, "No automatic primary asymmetry test is configured for this effect measure; ordinary and contour plots remain descriptive.")
    if (metric == "SMD") warnings <- c(warnings, "Ordinary SMD Egger is a separate effect-SE artifact and is never an automatic primary method.")
    list(`data.type`=data.type, metric=metric, `usable.studies`=length(standard.error),
         `included.indices`=included.indices,
         `raw.data.available`=isTRUE(prepared$raw),
         `standard.error.range`=if (length(standard.error)) range(standard.error) else numeric(),
         `reml.tau2`=if (exists("tau")) as.numeric(tau) else NA_real_,
         methods=methods, warnings=warnings,
         `package.versions`=c(meta=utils::packageDescription("meta")$Version, metafor=utils::packageDescription("metafor")$Version))
}

`%||%` <- function(x, y) if (is.null(x)) y else x

.small.study.confidence.level <- function(params=list()) {
    raw <- params$conf.level %||% 95
    if (!length(raw))
        stop("conf.level must be a finite percentage strictly between 0 and 100.")
    level <- suppressWarnings(as.numeric(raw[[1L]]))
    if (!length(level) || !is.finite(level) || level <= 0 || level >= 100)
        stop("conf.level must be a finite percentage strictly between 0 and 100.")
    level
}

.small.study.meta.level <- function(confidence.level) as.numeric(confidence.level) / 100

.small.study.confidence.label <- function(level=95, short=FALSE) {
    rendered <- trimws(formatC(as.numeric(level), format="fg", digits=4))
    rendered <- sub("\\.([0-9]*?)0+$", ".\\1", rendered)
    rendered <- sub("\\.$", "", rendered)
    if (short) paste0(rendered, "% CI") else paste0(rendered, "% confidence interval")
}

.small.study.no.test.summary <- function(eligibility, selected=character()) {
    entries <- eligibility$methods %||% list()
    if (length(selected)) {
        selected.entries <- entries[vapply(entries, function(entry) entry$method %in% selected, logical(1))]
        if (length(selected.entries)) entries <- selected.entries
    }
    threshold.entries <- entries[vapply(entries, function(entry) {
        grepl("below [0-9]+|requires at least [0-9]+|fewer than [0-9]+", as.character(entry$reason %||% ""))
    }, logical(1))]
    if (!length(threshold.entries)) return("Primary asymmetry test: none available.")
    entry <- threshold.entries[[1L]]
    reason <- as.character(entry$reason %||% "")
    threshold <- if (grepl("below [0-9]+", reason))
        sub(".*below ([0-9]+).*", "\\1", reason) else if (grepl("requires at least [0-9]+", reason))
        sub(".*requires at least ([0-9]+).*", "\\1", reason) else
        sub(".*fewer than ([0-9]+).*", "\\1", reason)
    usable <- .small.study.integer(entry$usable.studies %||% eligibility$`usable.studies`)
    paste0("No formal asymmetry test was run: ", .small.study.method.label(entry$method),
           " requires at least ", threshold, " usable studies; ", usable, " usable studies were available.")
}

.small.study.references <- function(methods, displayed.plots=character()) {
    method.keys <- c(
        "classical-egger"="publication.bias.egger",
        "mixed-effects-egger"="publication.bias.egger.mixed",
        "begg-mazumdar"="publication.bias.begg",
        "harbord"="publication.bias.harbord",
        "peters"="publication.bias.peters",
        "pustejovsky-rodgers"="publication.bias.pustejovsky",
        "rucker-as-re"="publication.bias.rucker",
        "deeks"="publication.bias.deeks"
    )
    keys <- unname(method.keys[intersect(as.character(methods), names(method.keys))])
    displayed.plots <- as.character(displayed.plots)
    if (any(grepl("Ordinary Funnel Plot|Trim-and-fill", displayed.plots)))
        keys <- c(keys, "publication.bias.funnel")
    if ("Contour Funnel Plot" %in% displayed.plots)
        keys <- c(keys, "publication.bias.contour")
    if ("Deeks Effective-Sample-Size Funnel Plot" %in% displayed.plots)
        keys <- c(keys, "publication.bias.deeks")
    if (any(grepl("Trim-and-fill", displayed.plots, fixed=TRUE)))
        keys <- c(keys, "publication.bias.trimfill")
    keys <- c(keys, "publication.bias.implementation")
    rcmetar.unique.references(unlist(lapply(unique(keys), rcmetar.method.references)))
}

.small.study.prepare <- function(om.data, params) {
    metric <- as.character(params$metric %||% "MD")
    confidence.level <- .small.study.confidence.level(params)
    diagnostic <- is(om.data, "DiagnosticData") && metric == "DOR"
    if (diagnostic) params$funnels <- "deeks"
    derived <- .small.study.reconstruct(om.data, metric, params)
    eligibility <- .small.study.eligibility(om.data, params, prepared=derived)
    # Eligibility owns the sole study-set decision for an executed analysis.
    keep <- logical(length(derived$y))
    keep[eligibility$included.indices] <- TRUE
    if (!any(keep)) stop("Small-study effects analysis requires finite effects and standard errors.")
    y <- derived$y[keep]
    se <- derived$se[keep]
    names(y) <- om.data@study.names[keep]
    prepared.model <- .small.study.prepared.model(y, se, names(y), metric, confidence.level)
    native.model <- .small.study.native.model(om.data, params, metric, keep, y, se)
    pooled <- if (metric == "OR") prepared.model else native.model
    metafor.pooled <- metafor::rma.uni(yi=y, sei=se, method="REML", level=confidence.level)
    params$reml.tau2 <- pooled$tau2 %||% NA_real_
    eligibility$`reml.tau2` <- params$reml.tau2
    eligibility$raw.data.available <- isTRUE(derived$raw)
    list(metric=metric, confidence.level=confidence.level, diagnostic=diagnostic,
         derived=derived, keep=keep, y=y, se=se, prepared.model=prepared.model,
         native.model=native.model, pooled=pooled, metafor.pooled=metafor.pooled,
        eligibility=eligibility, params=params)
}

.small.study.select.methods <- function(eligibility, params, metric, diagnostic) {
    selected <- as.character(params$tests %||% character())
    if (diagnostic) selected <- intersect(selected, "deeks")
    if (!length(selected)) {
        primary <- vapply(eligibility$methods,
                          function(x) identical(x$role, "primary") && isTRUE(x$available),
                          logical(1))
        selected <- vapply(eligibility$methods[primary], `[[`, character(1), "method")
    }
    selected
}

.small.study.fit.report <- function(om.data, params, prepared) {
    metric <- prepared$metric
    confidence.level <- prepared$confidence.level
    meta.level <- .small.study.meta.level(confidence.level)
    diagnostic <- prepared$diagnostic
    metric <- prepared$metric
    confidence.level <- prepared$confidence.level
    diagnostic <- prepared$diagnostic
    params <- prepared$params
    derived <- prepared$derived
    keep <- prepared$keep
    y <- prepared$y
    se <- prepared$se
    native.model <- prepared$native.model
    pooled <- prepared$pooled
    metafor.pooled <- prepared$metafor.pooled
    tau2 <- pooled$tau2 %||% NA_real_
    eligibility <- prepared$eligibility
    tests <- list(); failures <- character()
    asd.keep <- which(keep)
    selected <- .small.study.select.methods(eligibility, params, metric, diagnostic)
    for (method in selected) {
        tryCatch({
            entry <- eligibility$methods[vapply(eligibility$methods, function(x) identical(x$method, method), logical(1))][[1L]]
            if (is.null(entry) || !isTRUE(entry$available)) stop(entry$reason %||% "method is unavailable")
            k.min <- 10
            if (metric == "DOR" && method == "deeks") {
                fit.model <- native.model
                fit <- meta::metabias(fit.model, method.bias="Deeks", k.min=k.min, level=.small.study.meta.level(confidence.level))
                coefficient <- as.numeric(fit$estimate[[1L]] %||% NA_real_)
                standard.error <- as.numeric(fit$estimate[[2L]] %||% NA_real_)
                df <- as.numeric(fit$df %||% NA_real_)
                interval <- if (is.finite(coefficient) && is.finite(standard.error) && is.finite(df))
                    coefficient + c(-1, 1) * stats::qt((1 + confidence.level / 100) / 2, df) * standard.error else c(NA_real_, NA_real_)
                tests[[method]] <- list(
                    method="Deeks test (meta implementation)", role=entry$role, package="meta",
                    package.version=utils::packageDescription("meta")$Version,
                    call=paste0("meta::metabin(event.e=TP, n.e=TP+FN, event.c=FP, n.c=FP+TN, sm='OR', incr=0.5, method.incr='", .small.study.correction.method(params), "', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, "); meta::metabias(x=prepared.DOR.model, method.bias='Deeks', k.min=", k.min, ", level=", meta.level, ")"),
                    predictor="1/sqrt(ESS), ESS=4*n.e*n.c/(n.e+n.c)", weighting="native ESS weights", inference="t-based Deeks regression test",
                    model="Deeks effective-sample-size weighted regression", usable.studies=as.numeric(fit.model$k),
                    df=df, p.value=as.numeric(fit$p.value %||% NA_real_), statistic=as.numeric(fit$statistic %||% NA_real_),
                    coefficient=coefficient, standard.error=standard.error, confidence.interval=as.numeric(interval),
                    intercept=as.numeric(fit$intercept %||% NA_real_), se.intercept=as.numeric(fit$se.intercept %||% NA_real_),
                    prepared.effects=as.numeric(y), prepared.standard.errors=as.numeric(se),
                    effective.sample.size=as.numeric(4 * fit.model$n.e * fit.model$n.c / (fit.model$n.e + fit.model$n.c)),
                    deeks.predictor=as.numeric(1 / sqrt(4 * fit.model$n.e * fit.model$n.c / (fit.model$n.e + fit.model$n.c))),
                    deeks.weights=as.numeric(4 * fit.model$n.e * fit.model$n.c / (fit.model$n.e + fit.model$n.c))
                )
            } else if (method == "mixed-effects-egger") {
                fit <- metafor::regtest(y, sei=se, model="rma", predictor="sei", ret.fit=TRUE, level=confidence.level)
                model <- fit$fit
                tests[[method]] <- list(
                    method=method, role=entry$role, package="metafor",
                    package.version=utils::packageDescription("metafor")$Version,
                    call=paste0("metafor::regtest(x=prepared.effects, sei=prepared.standard.errors, model='rma', predictor='sei', ret.fit=TRUE, level=", confidence.level, ")"),
                    predictor="SE", weighting="inverse-variance weights with REML heterogeneity", inference="z test from metafor::regtest", model="REML mixed-effects meta-regression",
                    usable.studies=length(y), df=as.numeric(fit$dfs %||% NA_real_),
                    p.value=as.numeric(fit$pval), statistic=as.numeric(fit$zval),
                    coefficient=as.numeric(model$b[2]), standard.error=as.numeric(model$se[2]),
                    intercept=as.numeric(model$b[1]), se.intercept=as.numeric(model$se[1]),
                    confidence.interval=as.numeric(c(model$ci.lb[2], model$ci.ub[2])),
                    confidence.interval.intercept=as.numeric(c(model$ci.lb[1], model$ci.ub[1]))
                )
            } else if (metric == "SMD" && method == "pustejovsky-rodgers") {
                fit.model <- native.model
                fit <- meta::metabias(fit.model, method.bias="Pustejovsky", k.min=k.min, level=.small.study.meta.level(confidence.level))
                coefficient <- as.numeric(fit$estimate[[1L]] %||% NA_real_)
                standard.error <- as.numeric(fit$estimate[[2L]] %||% NA_real_)
                df <- as.numeric(fit$df %||% NA_real_)
                interval <- if (is.finite(coefficient) && is.finite(standard.error) && is.finite(df))
                    coefficient + c(-1, 1) * stats::qt((1 + confidence.level / 100) / 2, df) * standard.error else c(NA_real_, NA_real_)
                tests[[method]] <- list(
                    method=method, role=entry$role, package="meta", package.version=utils::packageDescription("meta")$Version,
                    call=paste0("meta::metacont(n.e, mean.e, sd.e, n.c, mean.c, sd.c, sm='SMD', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, "); meta::metabias(x=prepared.SMD.model, method.bias='Pustejovsky', k.min=", k.min, ", level=", meta.level, ")"),
                    predictor="sqrt(1/n.e + 1/n.c)", weighting="inverse variance from native Pustejovsky standard errors", inference="t-based Pustejovsky regression test",
                    model="Pustejovsky-Rodgers independent two-group regression", usable.studies=length(y), df=df,
                    p.value=as.numeric(fit$p.value %||% NA_real_), statistic=as.numeric(fit$statistic %||% NA_real_),
                    coefficient=coefficient, standard.error=standard.error, confidence.interval=as.numeric(interval),
                    intercept=as.numeric(fit$intercept %||% NA_real_), se.intercept=as.numeric(fit$se.intercept %||% NA_real_),
                    prepared.effects=as.numeric(y), prepared.standard.errors=as.numeric(se)
                )
            } else if (method %in% c("classical-egger", "begg-mazumdar")) {
                bias.method <- if (method == "classical-egger") "Egger" else "Begg"
                fit <- meta::metabias(pooled, method.bias=bias.method, k.min=k.min, level=.small.study.meta.level(confidence.level))
                coefficient <- as.numeric(fit$estimate[[1L]] %||% NA_real_)
                standard.error <- as.numeric(fit$estimate[[2L]] %||% NA_real_)
                df <- as.numeric(fit$df %||% NA_real_)
                interval <- if (is.finite(coefficient) && is.finite(standard.error) && is.finite(df))
                    coefficient + c(-1, 1) * stats::qt((1 + confidence.level / 100) / 2, df) * standard.error else c(NA_real_, NA_real_)
                tests[[method]] <- list(
                    method=method, role=entry$role, package="meta", package.version=utils::packageDescription("meta")$Version,
                    call=paste0("meta::metabias(x=prepared.meta.model, method.bias='", bias.method, "', k.min=", k.min, ", level=", meta.level, ")"),
                    predictor=if (method == "begg-mazumdar") "rank correlation of standardized effects and variance" else "SE",
                    weighting=if (method == "begg-mazumdar") "not applicable (Kendall rank-based test)" else "inverse variance",
                    inference=if (method == "begg-mazumdar") "z test from Kendall rank correlation" else "t-based meta::metabias test",
                    model=if (method == "begg-mazumdar") "Begg-Mazumdar rank correlation" else "multiplicative Egger regression",
                    usable.studies=length(y), df=df, p.value=as.numeric(fit$p.value %||% NA_real_),
                    statistic=as.numeric(fit$statistic %||% NA_real_), coefficient=coefficient,
                    standard.error=standard.error, confidence.interval=as.numeric(interval),
                    intercept=if (method == "classical-egger") as.numeric(fit$intercept %||% NA_real_) else NA_real_,
                    se.intercept=if (method == "classical-egger") as.numeric(fit$se.intercept %||% NA_real_) else NA_real_
                )
            } else if (metric == "OR" && method %in% c("harbord", "peters", "rucker-as-re")) {
                if (method == "rucker-as-re") {
                    fit.model <- .small.study.asd.model(om.data, params, asd.keep)
                    bias.method <- "Thompson"
                    fit.call <- paste0("meta::metabin(event.e, n.e, event.c, n.c, sm='ASD', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, ")")
                    test.call <- paste0("meta::metabias(x=prepared.ASD.model, method.bias='Thompson', k.min=", k.min, ", level=", meta.level, ")")
                } else if (method == "harbord") {
                    fit.model <- native.model
                    bias.method <- "Harbord"
                    fit.call <- paste0("meta::metabin(event.e, n.e, event.c, n.c, sm='OR', incr=0.5, method.incr='", .small.study.correction.method(params), "', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, ")")
                    test.call <- paste0("meta::metabias(x=prepared.OR.model, method.bias='Harbord', k.min=", k.min, ", level=", meta.level, ")")
                } else {
                    fit.model <- native.model
                    fit.model$TE <- y
                    fit.model$seTE <- se
                    bias.method <- "Peters"
                    fit.call <- paste0("meta::metabin(event.e, n.e, event.c, n.c, sm='OR', incr=0.5, method.incr='", .small.study.correction.method(params), "', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, ")")
                    test.call <- paste0("prepared.OR.model$TE <- prepared.effects; prepared.OR.model$seTE <- prepared.standard.errors; meta::metabias(x=prepared.OR.model, method.bias='Peters', k.min=", k.min, ", level=", meta.level, ")")
                }
                fit <- meta::metabias(fit.model, method.bias=bias.method, k.min=k.min, level=.small.study.meta.level(confidence.level))
                coefficient <- as.numeric(fit$estimate[[1L]] %||% NA_real_)
                standard.error <- as.numeric(fit$estimate[[2L]] %||% NA_real_)
                df <- as.numeric(fit$df %||% NA_real_)
                interval <- if (is.finite(coefficient) && is.finite(standard.error) && is.finite(df))
                    coefficient + c(-1, 1) * stats::qt((1 + confidence.level / 100) / 2, df) * standard.error else c(NA_real_, NA_real_)
                tests[[method]] <- list(
                    method=method, role=entry$role, package="meta", package.version=utils::packageDescription("meta")$Version,
                    call=paste0(fit.call, "; ", test.call),
                    predictor=if (method == "harbord") "Harbord Z/V on 1/sqrt(V), where V is the native score variance" else if (method == "peters") "1/(n.e+n.c), with native Peters seTE=sqrt(1/(event.e+event.c)+1/(non-events.e+non-events.c))" else "ASD effect on native ASD standard error",
                    weighting=if (method == "harbord") "native Harbord score variance V" else if (method == "peters") "1/Peters seTE^2" else "native AS+RE additive REML weights",
                    inference="t-based meta::metabias test",
                    model=if (method == "rucker-as-re") "R\u00fccker AS+RE (ASD + Thompson)" else paste0(bias.method, " native metabin model"),
                    usable.studies=if (method == "rucker-as-re") as.numeric(fit.model$k) else length(y), df=df, p.value=as.numeric(fit$p.value %||% NA_real_),
                    statistic=as.numeric(fit$statistic %||% NA_real_), coefficient=coefficient,
                    standard.error=standard.error, confidence.interval=as.numeric(interval),
                    intercept=if (method == "peters") as.numeric(fit$intercept %||% NA_real_) else NA_real_,
                    se.intercept=if (method == "peters") as.numeric(fit$se.intercept %||% NA_real_) else NA_real_,
                    prepared.effects=as.numeric(y), prepared.standard.errors=as.numeric(se),
                    routing.effects=as.numeric(y), routing.standard.errors=as.numeric(se)
                )
            } else {
                stop("unsupported selected asymmetry method: ", method)
            }
        }, error=function(e) failures <<- c(failures, paste(.small.study.method.label(method), conditionMessage(e), sep=": ")))
    }
    primary.methods <- vapply(eligibility$methods, function(x) identical(x$role, "primary") && isTRUE(x$available), logical(1))
    primary.name <- if (any(primary.methods)) vapply(eligibility$methods[primary.methods], `[[`, character(1), "method")[[1L]] else "None"
    primary.test <- if (primary.name != "None") tests[[primary.name]] else NULL
    primary.summary <- if (is.null(primary.test)) {
        if (primary.name == "None") .small.study.no.test.summary(eligibility, selected)
        else paste0("Primary asymmetry test: ", .small.study.method.label(primary.name), "; result unavailable.")
    } else {
        primary.p <- as.numeric(primary.test$p.value %||% NA_real_)
        primary.coefficient <- as.numeric(primary.test$coefficient %||% NA_real_)
        primary.interval <- as.numeric(primary.test$confidence.interval %||% c(NA_real_, NA_real_))
        if (length(primary.interval) < 2L) primary.interval <- c(primary.interval, NA_real_)[1:2]
        primary.result <- if (!is.finite(primary.p)) "p-value not available" else if (primary.p < .05)
            paste0("evidence of small-study effects (p = ", .small.study.p.value(primary.p), ")")
        else paste0("no clear evidence of small-study effects (p = ", .small.study.p.value(primary.p), ")")
        paste(c(
            paste0("Primary asymmetry test: ", .small.study.method.label(primary.name)),
            paste0("Result: ", primary.result),
            paste0("Usable studies: ", .small.study.integer(primary.test$usable.studies)),
            paste0("Estimate: ", .small.study.number(primary.coefficient),
                   " (", .small.study.confidence.label(confidence.level, short=TRUE), " ", .small.study.number(primary.interval[[1L]]),
                   " to ", .small.study.number(primary.interval[[2L]]), ")")
        ), collapse="\n")
    }
    warning.text <- paste(c(
        primary.summary,
        "Funnel plot asymmetry can reflect publication bias, heterogeneity, study design, or chance.",
        "Interpret the plots and tests together. No single result proves or rules out publication bias."
    ), collapse="\n\n")
    if (metric %in% c("PR", "PLN", "PLO", "PAS", "PFT")) warning.text <- paste(
        warning.text,
        "For one-arm proportions, the funnel plot is descriptive because the effect and its standard error are mathematically related.",
        sep="\n\n"
    )
    if (metric %in% c("RR", "RD")) warning.text <- paste(
        warning.text,
        "No automatic primary asymmetry test is available for this effect measure.",
        sep="\n\n"
    )
    if (metric == "SMD") warning.text <- paste(
        warning.text,
        "The ordinary Egger test is not selected for standardized mean differences because it can create effect-standard-error artifacts.",
        sep="\n\n"
    )
    eligibility.warnings <- unique(as.character(eligibility$warnings %||% character()))
    eligibility.warnings <- eligibility.warnings[!is.na(eligibility.warnings) & nzchar(trimws(eligibility.warnings))]
    if (length(eligibility.warnings)) warning.text <- paste(
        warning.text,
        paste(c("Analysis warnings:", paste0("- ", eligibility.warnings)), collapse="\n"),
        sep="\n\n"
    )
    trimfill <- if (isTRUE(params$trim.and.fill) && metric != "DOR" && !metric %in% c("PR", "PLN", "PLO", "PAS", "PFT"))
        .small.study.trimfill(pooled, params, metric, prepared=derived) else NULL
    extrapolation <- if (diagnostic) NULL else .small.study.extrapolation(tests, params, metric, eligibility=eligibility)
    analysis.summary <- c(
        paste0("Effect measure: ", .small.study.metric.label(metric), " (", metric, ")"),
        paste0("Studies analyzed: ", length(y)),
        paste0("Confidence level: ", .small.study.confidence.label(confidence.level)),
        paste0("Primary test: ", if (primary.name == "None") "None available" else .small.study.method.label(primary.name))
    )
    if (length(se)) analysis.summary <- c(
        analysis.summary,
        paste0(
            "Observed standard-error range: [",
            .small.study.exact.number(min(se)), ", ",
            .small.study.exact.number(max(se)), "]"
        )
    )
    if (metric == "OR") analysis.summary <- c(
        analysis.summary,
        paste0("Heterogeneity (REML tau-squared): ", .small.study.number(tau2)),
        paste0("Continuity correction: ", as.character(params$correction.policy %||% "Studies with any zero cell"))
    )
    if (metric == "DOR") analysis.summary <- c(
        analysis.summary,
        paste0("Continuity correction: ", as.character(params$correction.policy %||% "All studies if any zero exists")),
        "Plot method: Deeks funnel plot using effective sample size"
    )
    output <- list(
        Warning=warning.text,
        `Data and eligibility`=paste(analysis.summary, collapse="\n"),
        Tests=.small.study.tests.text(tests, confidence.level),
        References=character(),
        Failures=if (length(failures)) paste(failures, collapse="\n") else NULL,
        eligibility=eligibility,
        tests.data=tests,
        `Trim-and-fill data`=if (!is.null(trimfill)) trimfill else NULL
    )
    if (!diagnostic) output <- append(output, list(`Pooled comparison`=.small.study.pooled.text(pooled, metric, confidence.level)), after=3L)
    output <- c(output, list(
        `Method details`=.small.study.method.details(tests),
        `Methods not applicable`=.small.study.methods.not.applicable(eligibility)
    ))
    if (!is.null(trimfill)) output <- c(output, trimfill$text)
    if (!is.null(extrapolation)) output <- c(output, extrapolation)
    plots <- if (diagnostic && !isTRUE(derived$raw))
        list(images=character(), plot_capabilities=list(), plot_names=character(),
             plot_params_paths=list(), image_order=character(), failures=character()) else
        .small.study.plots(om.data, metafor.pooled, params, metric,
            common.center=pooled$TE.common, prepared=derived, trimfill=trimfill,
            diagnostic.model=if (diagnostic) native.model else NULL)
    trimfill.failures <- trimfill$failures %||% character()
    if (length(trimfill.failures))
        trimfill.failures <- paste0("trim-and-fill: ", trimfill.failures)
    plot.failures <- c(trimfill.failures, plots$failures %||% character())
    if (length(plot.failures))
        output$Failures <- paste(c(failures, plot.failures), collapse="\n")
    output$References <- .small.study.references(names(tests), names(plots$images))
    plots$failures <- NULL
    output <- c(output, plots)
    output
}

publication.bias.effects <- function(om.data, params) {
    prepared <- .small.study.prepare(om.data, params)
    .small.study.fit.report(om.data, prepared$params, prepared)
}

.small.study.native.model <- function(om.data, params, metric, keep, y, se) {
    method.incr <- .small.study.correction.method(params)
    confidence.level <- .small.study.confidence.level(params)
    if (is(om.data, "BinaryData") && isTRUE(.small.study.has.binary.raw(om.data))) {
        return(meta::metabin(
            event.e=om.data@g1O1[keep], n.e=om.data@g1O1[keep] + om.data@g1O2[keep],
            event.c=om.data@g2O1[keep], n.c=om.data@g2O1[keep] + om.data@g2O2[keep],
            studlab=om.data@study.names[keep], sm=metric, incr=0.5,
            method.incr=method.incr, common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level)
        ))
    }
    if (is(om.data, "ContinuousData") && metric %in% c("MD", "SMD") &&
            isTRUE(.small.study.has.continuous.raw(om.data, metric))) {
        return(meta::metacont(
            n.e=om.data@N1[keep], mean.e=om.data@mean1[keep], sd.e=om.data@sd1[keep],
            n.c=om.data@N2[keep], mean.c=om.data@mean2[keep], sd.c=om.data@sd2[keep],
            studlab=om.data@study.names[keep], sm=metric, common=TRUE, random=TRUE,
            method.tau="REML", level=.small.study.meta.level(confidence.level)
        ))
    }
    if (is(om.data, "BinaryData") && metric %in% c("PR", "PLN", "PLO", "PAS", "PFT") && isTRUE(.small.study.has.one.arm.raw(om.data))) {
        return(meta::metaprop(
            event=om.data@g1O1, n=om.data@g1O1 + om.data@g1O2,
            studlab=om.data@study.names, sm=metric, method="Inverse",
            common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level)
        ))
    }
    if (is(om.data, "DiagnosticData") && identical(metric, "DOR") &&
            length(om.data@TP) == length(om.data@study.names) &&
            all(vapply(list(om.data@TP, om.data@FN, om.data@FP, om.data@TN),
                function(x) all(is.finite(x)), logical(1)))) {
        return(meta::metabin(
            event.e=om.data@TP[keep], n.e=om.data@TP[keep] + om.data@FN[keep],
            event.c=om.data@FP[keep], n.c=om.data@FP[keep] + om.data@TN[keep],
            studlab=om.data@study.names[keep], sm="OR", incr=0.5,
            method.incr=method.incr, common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level)
        ))
    }
    # Effect-only data have no raw model representation, so metagen is the
    # package-native generic model for the entered log effects.
    meta::metagen(TE=y, seTE=se, studlab=names(y), sm=metric, common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level))
}

.small.study.prepared.model <- function(y, se, study.names, metric, confidence.level=95) {
    meta::metagen(
        TE=y, seTE=se, studlab=study.names, sm=metric,
        common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level)
    )
}

.small.study.correction.method <- function(params) {
    switch(as.character(params$correction.policy %||% ""),
        "Studies with any zero cell"="only0",
        "All studies"="all",
        "All studies if any zero exists"="if0all",
        "only0")
}

.small.study.asd.model <- function(om.data, params, keep) {
    if (!is(om.data, "BinaryData")) stop("R\u00fccker AS+RE requires binary two-arm data.")
    confidence.level <- .small.study.confidence.level(params)
    meta::metabin(
        event.e=om.data@g1O1[keep], n.e=om.data@g1O1[keep] + om.data@g1O2[keep],
        event.c=om.data@g2O1[keep], n.c=om.data@g2O1[keep] + om.data@g2O2[keep],
        studlab=om.data@study.names[keep], sm="ASD", common=TRUE, random=TRUE,
        method.tau="REML", level=.small.study.meta.level(confidence.level)
    )
}

.small.study.has.binary.raw <- function(om.data) {
    n <- length(om.data@study.names)
    n > 0 && all(vapply(list(om.data@g1O1, om.data@g1O2, om.data@g2O1, om.data@g2O2),
        function(x) length(x) == n && all(is.finite(x)), logical(1)))
}

.small.study.has.one.arm.raw <- function(om.data) {
    n <- length(om.data@study.names)
    is(om.data, "BinaryData") && n > 0 &&
        all(vapply(list(om.data@g1O1, om.data@g1O2), function(x) length(x) == n && all(is.finite(x)), logical(1)))
}

.small.study.has.continuous.raw <- function(om.data, metric) {
    n <- length(om.data@study.names)
    basic <- n > 0 && all(vapply(list(om.data@N1, om.data@mean1, om.data@sd1),
        function(x) length(x) == n && all(is.finite(x)), logical(1)))
    if (identical(metric, "TXMean")) basic else basic &&
        all(vapply(list(om.data@N2, om.data@mean2, om.data@sd2),
            function(x) length(x) == n && all(is.finite(x)), logical(1)))
}

.small.study.reconstruct <- function(om.data, metric, params) {
    n <- length(om.data@study.names)
    confidence.level <- .small.study.confidence.level(params)
    y <- if (length(om.data@y) == n) om.data@y else rep(NA_real_, n)
    se <- if (length(om.data@SE) == n) om.data@SE else rep(NA_real_, n)
    raw <- FALSE
    if (is(om.data, "BinaryData") && metric %in% c("OR", "RR", "RD") && all(vapply(list(om.data@g1O1, om.data@g1O2, om.data@g2O1, om.data@g2O2), function(x) length(x) == n && all(is.finite(x)), logical(1)))) {
        a <- om.data@g1O1; b <- om.data@g1O2; c <- om.data@g2O1; d <- om.data@g2O2
        double.zero <- if (identical(metric, "OR")) ((a == 0 & c == 0) | (b == 0 & d == 0)) else rep(FALSE, length(a))
        policy <- as.character(params$correction.policy %||% "")
        zero <- (a == 0 | b == 0 | c == 0 | d == 0)
        apply.correction <- if (policy == "All studies") rep(TRUE, length(y)) else if (policy == "All studies if any zero exists" && any(zero)) rep(TRUE, length(y)) else if (policy == "Studies with any zero cell") zero else rep(FALSE, length(y))
        for (index in which(apply.correction)) { a[index] <- a[index] + .5; b[index] <- b[index] + .5; c[index] <- c[index] + .5; d[index] <- d[index] + .5 }
        n1 <- a + b; n2 <- c + d
        if (metric == "OR") {
            y <- log((a*d)/(b*c)); se <- sqrt(1/a + 1/b + 1/c + 1/d)
            y[double.zero] <- NA_real_; se[double.zero] <- NA_real_
        }
        if (metric == "RR") { y <- log((a/n1)/(c/n2)); se <- sqrt(1/a - 1/n1 + 1/c - 1/n2) }
        if (metric == "RD") { y <- a/n1-c/n2; se <- sqrt(a*b/n1^3+c*d/n2^3) }
        raw <- TRUE
    }
    if (is(om.data, "ContinuousData") && metric %in% c("MD", "SMD") && isTRUE(.small.study.has.continuous.raw(om.data, metric))) {
        model <- meta::metacont(
            n.e=om.data@N1, mean.e=om.data@mean1, sd.e=om.data@sd1,
            n.c=om.data@N2, mean.c=om.data@mean2, sd.c=om.data@sd2,
            studlab=om.data@study.names, sm=metric, common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level)
        )
        y <- model$TE
        se <- model$seTE
        raw <- TRUE
    }
    if (is(om.data, "BinaryData") && metric %in% c("PR", "PLN", "PLO", "PAS", "PFT") && isTRUE(.small.study.has.one.arm.raw(om.data))) {
        model <- meta::metaprop(
            event=om.data@g1O1, n=om.data@g1O1 + om.data@g1O2,
            studlab=om.data@study.names, sm=metric, method="Inverse",
            common=TRUE, random=TRUE, method.tau="REML", level=.small.study.meta.level(confidence.level)
        )
        y <- model$TE
        se <- model$seTE
        raw <- TRUE
    }
    if (is(om.data, "DiagnosticData") && all(vapply(list(om.data@TP, om.data@FN, om.data@FP, om.data@TN), function(x) length(x) == n && all(is.finite(x)), logical(1))) && metric == "DOR") {
        a <- om.data@TP; b <- om.data@FN; c <- om.data@FP; d <- om.data@TN
        zero <- (a == 0 | b == 0 | c == 0 | d == 0)
        policy <- as.character(params$correction.policy %||% "")
        apply.correction <- if (policy == "All studies") rep(TRUE, length(y)) else if (policy == "All studies if any zero exists" && any(zero)) rep(TRUE, length(y)) else if (policy == "Studies with any zero cell") zero else rep(FALSE, length(y))
        for (index in which(apply.correction)) { a[index] <- a[index] + .5; b[index] <- b[index] + .5; c[index] <- c[index] + .5; d[index] <- d[index] + .5 }
        y <- log((a*d)/(b*c)); se <- sqrt(1/a + 1/b + 1/c + 1/d); raw <- TRUE
    }
    list(y=y, se=se, raw=raw)
}

.small.study.tests.text <- function(tests, confidence.level=95) {
    if (!length(tests)) return("No formal small-study effects test produced a result.")
    paste(vapply(tests, function(x) {
        interval <- x$confidence.interval %||% c(NA_real_, NA_real_)
        p.value <- as.numeric(x$p.value %||% NA_real_)
        conclusion <- if (!is.finite(p.value)) {
            "The test did not return a p-value."
        } else if (p.value < .05) {
            paste0("Evidence of small-study effects (p = ", .small.study.p.value(p.value), ").")
        } else {
            paste0("No clear evidence of small-study effects (p = ", .small.study.p.value(p.value), ").")
        }
        role <- as.character(x$role %||% "")
        heading <- paste0(
            .small.study.method.label(x$method),
            if (role == "primary") " (primary)" else if (nzchar(role)) " (additional)" else ""
        )
        lines <- c(
            heading,
            paste0("  Studies: ", .small.study.integer(x$usable.studies)),
            paste0("  Result: ", conclusion)
        )
        statistic <- suppressWarnings(as.numeric(x$statistic %||% NA_real_))
        if (length(statistic) && is.finite(statistic[[1L]])) lines <- c(
            lines,
            paste0("  Test statistic: ", .small.study.number(statistic))
        )
        coefficient <- suppressWarnings(as.numeric(x$coefficient %||% NA_real_))
        if (length(coefficient) && is.finite(coefficient[[1L]])) lines <- c(
            lines,
            paste0(
                "  Coefficient: ", .small.study.number(coefficient),
                " (SE ", .small.study.number(x$standard.error),
                "; ", .small.study.confidence.label(confidence.level, short=TRUE), " ", .small.study.number(interval[[1L]]),
                " to ", .small.study.number(interval[[2L]]), ")"
            )
        )
        if (length(x$model) && nzchar(.small.study.text(x$model, ""))) lines <- c(
            lines,
            paste0("  Model: ", .small.study.text(x$model, ""))
        )
        paste(lines, collapse="\n")
    }, character(1)), collapse="\n\n")
}

.small.study.method.details <- function(tests) {
    if (!length(tests)) return("No formal method details are available.")
    paste(vapply(tests, function(x) {
        p.value <- suppressWarnings(as.numeric(x$p.value %||% NA_real_))
        lines <- c(
            .small.study.method.label(x$method),
            paste0("  Package: ", .small.study.text(x$package, "not recorded"), " ", .small.study.text(x$package.version, "")),
            paste0("  Predictor: ", .small.study.text(x$predictor, "not recorded")),
            paste0("  Weighting: ", .small.study.text(x$weighting, "not recorded")),
            paste0("  Inference: ", .small.study.text(x$inference %||% x$model, "not recorded")),
            paste0("  Degrees of freedom: ", .small.study.number(x$df %||% NA_real_)),
            paste0("  Exact p-value: ", .small.study.exact.number(p.value)),
            paste0("  Call: ", .small.study.text(x$call, "not recorded"))
        )
        paste(lines, collapse="\n")
    }, character(1)), collapse="\n\n")
}

.small.study.methods.not.applicable <- function(eligibility) {
    methods <- eligibility$methods[vapply(eligibility$methods, function(x) !isTRUE(x$available), logical(1))]
    if (!length(methods)) return("No additional methods were marked not applicable.")
    paste(vapply(methods, function(x) paste0(
        .small.study.method.label(x$method), ": ", .small.study.text(x$reason, "Not applicable.")
    ), character(1)), collapse="\n")
}

.small.study.pooled.text <- function(pooled, metric, confidence.level=95) {
    common <- c(pooled$TE.common, pooled$lower.common, pooled$upper.common)
    random <- c(pooled$TE.random, pooled$lower.random, pooled$upper.random)
    if (metric %in% c("OR", "RR")) {
        common <- exp(common)
        random <- exp(random)
    }
    paste(c(
        "Common effect",
        paste0("  Estimate: ", .small.study.number(common[[1L]])),
        paste0("  ", .small.study.confidence.label(confidence.level), ": ", .small.study.number(common[[2L]]), " to ", .small.study.number(common[[3L]])),
        "",
        "Random effects (REML)",
        paste0("  Estimate: ", .small.study.number(random[[1L]])),
        paste0("  ", .small.study.confidence.label(confidence.level), ": ", .small.study.number(random[[2L]]), " to ", .small.study.number(random[[3L]])),
        "",
        "These are model comparisons, not estimates corrected for publication bias."
    ), collapse="\n")
}

.small.study.text <- function(value, fallback="Not available") {
    if (is.null(value) || !length(value)) return(fallback)
    value <- trimws(as.character(value[[1L]]))
    if (is.na(value) || !nzchar(value) || value %in% c("NA", "NaN", "Inf", "-Inf")) fallback else value
}

.small.study.integer <- function(value) {
    numeric.value <- suppressWarnings(as.numeric(value))
    if (!length(numeric.value) || !is.finite(numeric.value[[1L]])) return("Not available")
    trimws(formatC(round(numeric.value[[1L]]), format="d"))
}

.small.study.exact.number <- function(value) {
    numeric.value <- suppressWarnings(as.numeric(value))
    if (!length(numeric.value) || !is.finite(numeric.value[[1L]])) return("Not available")
    trimws(formatC(numeric.value[[1L]], format="fg", digits=8))
}

.small.study.number <- function(value) {
    value <- suppressWarnings(as.numeric(value))
    if (!length(value) || !is.finite(value[[1L]])) return("Not available")
    rendered <- trimws(formatC(value[[1L]], format="fg", digits=4, flag="#"))
    sub("\\.$", "", rendered)
}

.small.study.p.value <- function(value) {
    value <- suppressWarnings(as.numeric(value))
    if (!length(value) || !is.finite(value[[1L]])) return("not available")
    if (value[[1L]] < .001) return("< 0.001")
    trimws(formatC(value[[1L]], format="f", digits=3))
}

.small.study.method.label <- function(method) {
    labels <- c(
        `classical-egger`="Classical Egger test",
        `mixed-effects-egger`="Mixed-effects Egger test",
        `begg-mazumdar`="Begg-Mazumdar test",
        harbord="Harbord test",
        peters="Peters test",
        `pustejovsky-rodgers`="Pustejovsky-Rodgers test",
        `rucker-as-re`="R\u00fccker AS+RE test",
        deeks="Deeks test"
    )
    raw <- as.character(method)
    if (!length(raw) || is.na(raw[[1L]]) || !nzchar(raw[[1L]])) return("Unknown method")
    label <- unname(labels[raw[[1L]]])
    if (!length(label) || is.na(label[[1L]])) raw[[1L]] else label[[1L]]
}

.small.study.metric.label <- function(metric) {
    labels <- c(
        OR="Odds ratio", RR="Risk ratio", RD="Risk difference",
        MD="Mean difference", SMD="Standardized mean difference",
        DOR="Diagnostic odds ratio", PR="Proportion", PLN="Log proportion",
        PLO="Logit proportion", PAS="Arcsine proportion",
        PFT="Freeman-Tukey proportion"
    )
    raw <- as.character(metric)
    if (!length(raw) || is.na(raw[[1L]]) || !nzchar(raw[[1L]])) return("Unknown metric")
    label <- unname(labels[raw[[1L]]])
    if (!length(label) || is.na(label[[1L]])) raw[[1L]] else label[[1L]]
}

.small.study.plots <- function(om.data, pooled, params, metric, common.center=0, prepared=NULL, trimfill=NULL, diagnostic.model=NULL) {
    if (is.null(prepared)) prepared <- .small.study.reconstruct(om.data, metric, params)
    plot.data <- om.data
    plot.data@y <- prepared$y
    plot.data@SE <- prepared$se
    kinds <- as.character(params$funnels %||% "ordinary")
    paths <- character(); caps <- list(); plot.names <- character(); ppaths <- list()
    plot.failures <- character()
    setting <- function(name, index, default) {
        value <- params[[name]]
        if (is.null(value) || !length(value)) return(default)
        value[[min(index, length(value))]]
    }
    for (index in seq_along(kinds)) {
        kind <- kinds[[index]]
        title <- if (kind == "ordinary") "Ordinary Funnel Plot" else if (kind == "deeks") "Deeks Effective-Sample-Size Funnel Plot" else "Contour Funnel Plot"
        path <- tempfile(pattern=paste0("small-study-", kind, "-"), fileext=".png")
        xlab <- as.character(setting(
            "funnel.xlab", index,
            if (kind == "deeks") "1/sqrt(ESS)" else if (metric %in% c("OR", "RR")) paste0(metric, " (back-transformed scale)") else metric
        ))
        ylab <- as.character(setting("funnel.ylab", index, if (kind == "deeks") "Log diagnostic odds ratio" else "Standard error"))
        run.params <- params
        run.params$funnel.kind <- kind
        run.params$funnel.index <- index
        run.params$funnel.center <- common.center
        run.params$prepared.effects <- prepared$y
        run.params$prepared.standard.errors <- prepared$se
        run.params$funnel.xlab <- xlab
        run.params$funnel.ylab <- ylab
        if (kind == "deeks") {
            if (!is(om.data, "DiagnosticData")) stop("Deeks funnel requires diagnostic data.")
            if (is.null(diagnostic.model)) stop("Deeks funnel requires a prepared diagnostic model.")
            effective <- 4 * diagnostic.model$n.e * diagnostic.model$n.c / (diagnostic.model$n.e + diagnostic.model$n.c)
            keep.deeks <- is.finite(effective) & effective > 0 & is.finite(prepared$y)
            run.params$deeks.ess <- effective[keep.deeks]
            run.params$deeks.predictor <- 1 / sqrt(effective[keep.deeks])
            run.params$deeks.weights <- effective[keep.deeks]
            # Store the fitted line, not merely its inputs.  Regeneration is
            # presentation-only and must not run a second regression.
            deeks.line <- stats::lm(prepared$y[keep.deeks] ~ run.params$deeks.predictor,
                                    weights=run.params$deeks.weights)
            run.params$deeks.line <- c(intercept=unname(stats::coef(deeks.line)[[1L]]),
                                       slope=unname(stats::coef(deeks.line)[[2L]]))
            run.params$deeks.correction.policy <- as.character(params$correction.policy %||% "All studies if any zero exists")
        }
        rendered <- tryCatch({
            rcmetar.regenerate.small.study.funnel(plot.data, pooled, run.params, path)
            TRUE
        }, error=function(e) {
            plot.failures <<- c(plot.failures, paste0(title, ": ", conditionMessage(e)))
            FALSE
        })
        if (!isTRUE(rendered)) next
        paths[[title]] <- path
        plot.kind <- if (kind == "ordinary") "funnel" else if (kind == "contour") "contour_funnel" else "deeks_funnel"
        caps[[title]] <- list(plot_kind=plot.kind, editable=TRUE, styleable=TRUE, composition="single", regenerator="funnel")
        plot.names <- c(plot.names, stats::setNames(plot.kind, tolower(title)))
        base <- sub("\\.png$", "", path)
        .small.study.save(plot.data, pooled, run.params, base)
        ppaths[[title]] <- base
    }
    if (!is.null(trimfill) && length(trimfill$scenarios)) {
        for (scenario.name in names(trimfill$scenarios)) {
            scenario <- trimfill$scenarios[[scenario.name]]
            path <- tempfile(pattern="small-study-trimfill-", fileext=".png")
            augmented.data <- plot.data
            augmented.data@y <- scenario$augmented.effects
            augmented.data@SE <- scenario$augmented.standard.errors
            augmented.data@study.names <- scenario$study.labels
            run.params <- params
            run.params$funnel.kind <- "trimfill"
            run.params$funnel.index <- 1L
            run.params$trimfill.scenario <- scenario.name
            run.params$trim.and.fill.estimator <- scenario$estimator
            run.params$trim.and.fill.side <- scenario$side
            run.params$trim.and.fill.model <- scenario$model
            run.params$funnel.center <- scenario$display.center
            run.params$prepared.effects <- scenario$augmented.effects
            run.params$prepared.standard.errors <- scenario$augmented.standard.errors
            run.params$funnel.xlab <- as.character(setting(
                "funnel.xlab", 1L,
                if (metric %in% c("OR", "RR")) paste0(metric, " (back-transformed scale)") else metric
            ))
            run.params$funnel.ylab <- as.character(setting("funnel.ylab", 1L, "Standard error"))
            rendered <- tryCatch({
                rcmetar.regenerate.small.study.funnel(augmented.data, scenario$fit, run.params, path)
                TRUE
            }, error=function(e) {
                plot.failures <<- c(plot.failures, paste0(scenario.name, " plot: ", conditionMessage(e)))
                FALSE
            })
            if (!isTRUE(rendered)) next
            paths[[scenario.name]] <- path
            caps[[scenario.name]] <- list(plot_kind="trimfill_funnel", editable=TRUE, styleable=TRUE, composition="single", regenerator="funnel")
            plot.names <- c(plot.names, stats::setNames("trimfill_funnel", tolower(scenario.name)))
            base <- sub("\\.png$", "", path)
            .small.study.save(augmented.data, scenario$fit, run.params, base)
            ppaths[[scenario.name]] <- base
        }
    }
    list(images=paths, plot_capabilities=caps, plot_names=plot.names,
         plot_params_paths=ppaths, image_order=names(paths), failures=plot.failures)
}

.small.study.save <- function(data.object, result.object, params.object, base) {
    om.data <- data.object
    res <- result.object
    params <- params.object
    save(om.data, file=paste0(base, ".data"))
    save(res, file=paste0(base, ".res"))
    save(params, file=paste0(base, ".params"))
}

.small.study.trimfill <- function(pooled, params, metric, prepared=NULL) {
    confidence.level <- .small.study.confidence.level(params)
    meta.level <- .small.study.meta.level(confidence.level)
    estimator <- toupper(as.character(params$trim.and.fill.estimator %||% "L0"))
    if (!estimator %in% c("L0", "R0")) stop("trim-and-fill estimator must be L0 or R0")
    type <- if (estimator == "R0") "R" else "L"
    side <- as.character(params$trim.and.fill.side %||% "auto")
    if (!side %in% c("auto", "left", "right")) stop("trim-and-fill side must be auto, left, or right")
    model <- as.character(params$trim.and.fill.model %||% "random")
    if (!model %in% c("random", "common")) stop("trim-and-fill model must be random or common")
    common <- identical(model, "common")
    bilateral <- side == "auto" && metric %in% c("OR", "SMD")
    requested <- if (bilateral) list(left=TRUE, right=FALSE) else if (side == "auto") list(auto=NULL) else setNames(list(side == "left"), side)
    scenarios <- list(); failures <- character(); text <- list()
    run <- function(name, left.arg) {
        tryCatch({
            fit <- if (is.null(left.arg)) {
                meta::trimfill(pooled, ma.common=common, type=type, common=common, random=!common, level=.small.study.meta.level(confidence.level))
            } else {
                meta::trimfill(pooled, left=left.arg, ma.common=common, type=type, common=common, random=!common, level=.small.study.meta.level(confidence.level))
            }
            display.center <- if (common) fit$TE.common else fit$TE.random
            labels <- as.character(fit$studlab)
            scenario <- list(
                fit=fit, estimator=estimator, side=if (is.null(left.arg)) "auto" else if (left.arg) "left" else "right",
                model=model, side.rule=if (is.null(left.arg)) "automatic side (meta package)" else paste0(name, " scenario"),
                augmented.effects=as.numeric(fit$TE), augmented.standard.errors=as.numeric(fit$seTE),
                study.labels=labels, imputed.k0=as.integer(fit$k0), display.center=as.numeric(display.center),
                point.size=as.numeric((params$funnel.point.size %||% params$point.size %||% 1)[[1L]]),
                label.policy=as.character((params$funnel.label.policy %||% "none")[[1L]]),
                package.version=utils::packageDescription("meta")$Version
            )
            call <- paste0("meta::trimfill(x=prepared.meta.model, ma.common=", common,
                           ", type='", type, "', common=", common, ", random=", !common, ", level=", meta.level,
                           if (!is.null(left.arg)) paste0(", left=", left.arg) else "", ")")
            title <- if (bilateral) paste0("Trim-and-fill ", name) else "Trim-and-fill"
            estimate <- if (common) fit$TE.common else fit$TE.random
            lower <- if (common) fit$lower.common else fit$lower.random
            upper <- if (common) fit$upper.common else fit$upper.random
            if (metric %in% c("OR", "RR")) {
                estimate <- exp(estimate)
                lower <- exp(lower)
                upper <- exp(upper)
            }
            text[[title]] <<- paste(c(
                paste0("Estimated missing studies: ", .small.study.integer(scenario$imputed.k0)),
                paste0("Side: ", if (is.null(left.arg)) "Selected automatically" else tools::toTitleCase(name)),
                paste0("Estimator: ", estimator),
                paste0("Model: ", if (common) "Common effect" else "Random effects (REML)"),
                paste0(
                    "Estimate after imputation: ", .small.study.number(estimate),
                    " (", .small.study.confidence.label(confidence.level, short=TRUE), " ", .small.study.number(lower), " to ", .small.study.number(upper), ")"
                ),
                "",
                "Treat this as a sensitivity analysis, not a corrected or more valid result."
            ), collapse="\n")
            scenario$call <- call
            scenarios[[title]] <<- scenario
        }, error=function(e) failures <<- c(failures, paste(name, conditionMessage(e), sep=": ")))
    }
    for (name in names(requested)) run(name, requested[[name]])
    list(text=text, scenarios=scenarios, failures=failures, estimator=estimator, model=model,
         side.rule=if (bilateral) "separate left/right scenarios" else if (side == "auto") "automatic side" else paste0("explicit ", side),
         package.version=utils::packageDescription("meta")$Version)
}

.small.study.extrapolation <- function(tests, params, metric, eligibility=NULL) {
    if (!isTRUE(params$extrapolation)) return(NULL)
    confidence.level <- .small.study.confidence.level(params)
    if (metric == "DOR") return(list(Extrapolation="Unavailable: infinite-precision extrapolation is not defined for diagnostic analyses."))
    if (length(params$moderators %||% character())) return(list(Extrapolation="Unavailable: infinite-precision extrapolation requires no additional moderators."))
    supported <- c("classical-egger", "mixed-effects-egger", "peters")
    rows <- list(); reasons <- character()
    for (method in names(tests)) {
        test <- tests[[method]]
        if (!method %in% supported) next
        k <- as.numeric(test$usable.studies %||% 0)
        if (k < 10) { reasons <- c(reasons, paste0(.small.study.method.label(method), ": requires at least 10 usable studies.")); next }
        intercept <- as.numeric(test$intercept %||% NA_real_)
        se.intercept <- as.numeric(test$se.intercept %||% NA_real_)
        df <- as.numeric(test$df %||% NA_real_)
        if (!is.finite(intercept) || !is.finite(se.intercept)) { reasons <- c(reasons, paste0(.small.study.method.label(method), ": fitted intercept was unavailable.")); next }
        stored.ci <- as.numeric(test$confidence.interval.intercept %||% c(NA_real_, NA_real_))
        ci <- if (length(stored.ci) == 2L && all(is.finite(stored.ci))) stored.ci else if (is.finite(df))
            intercept + c(-1, 1) * stats::qt((1 + confidence.level / 100) / 2, df) * se.intercept else
            intercept + c(-1, 1) * stats::qnorm((1 + confidence.level / 100) / 2) * se.intercept
        rows[[method]] <- paste(c(
            .small.study.method.label(method),
            paste0("  Studies: ", .small.study.integer(k)),
            paste0(
                "  Estimate at infinite precision: ", .small.study.number(intercept),
                " (", .small.study.confidence.label(confidence.level, short=TRUE), " ", .small.study.number(ci[[1L]]),
                " to ", .small.study.number(ci[[2L]]), ")"
            )
        ), collapse="\n")
    }
    if (!length(rows)) {
        reasons <- c("Infinite-precision extrapolation requires at least 10 usable studies and a successful supported fit.", reasons)
        rows <- list(reason="No supported successful classical Egger, mixed-effects Egger, or Peters fit qualified for extrapolation.")
    }
    list(Extrapolation=paste(c(
        "This exploratory estimate describes the fitted effect at infinite precision. It is not bias-adjusted.",
        "",
        unlist(rows),
        reasons
    ), collapse="\n"))
}

rcmetar.run.small.study.effects <- function(om.data, params=list()) {
    if (!requireNamespace("meta", quietly=TRUE)) stop("RCMetaR requires meta 8.5-0 for small-study effects methods.")
    if (!identical(as.character(utils::packageDescription("meta")$Version), "8.5-0")) stop("RCMetaR requires meta 8.5-0; installed version differs.")
    data.type <- as.character(params$data.type %||% if (is(om.data, "DiagnosticData")) "diagnostic" else "")
    metric <- as.character(params$metric %||% "")
    if (data.type == "diagnostic" && metric != "DOR") stop("diagnostic small-study effects analysis is DOR-only")
    if (data.type == "diagnostic" && metric == "DOR" && is.null(params$correction.policy))
        params$correction.policy <- "All studies if any zero exists"
    eligibility <- .small.study.eligibility(om.data, params)
    if (isTRUE(params$preview)) return(list(eligibility=eligibility))
    publication.bias.effects(om.data, params)
}

rcmetar.regenerate.small.study.funnel <- function(om.data, res, params, output.path=NULL) {
    path <- output.path %||% tempfile(pattern="small-study-funnel-", fileext=".png")
    extension <- tolower(tools::file_ext(path))
    y <- om.data@y; se <- om.data@SE; keep <- is.finite(y) & is.finite(se) & se > 0
    kind <- as.character(params$funnel.kind %||% "ordinary")
    funnel.index <- suppressWarnings(as.integer(params$funnel.index %||% 1L))
    if (!length(funnel.index) || !is.finite(funnel.index[[1L]]) || funnel.index[[1L]] < 1L)
        funnel.index <- 1L else funnel.index <- funnel.index[[1L]]
    value <- function(name, default) {
        item <- params[[name]]
        if (is.null(item) || !length(item)) default else item[[min(funnel.index, length(item))]]
    }
    point.size <- as.numeric(value("funnel.point.size", value("point.size", 1)))
    point.symbol <- as.integer(value("funnel.point.symbol", 19))
    point.color <- as.character(value("funnel.point.color", value("point.color", "black")))
    reference.color <- as.character(value("funnel.reference.color", "steelblue"))
    region.color <- as.character(value("funnel.region.color", "grey90"))
    background.color <- as.character(value("funnel.background.color", "white"))
    show.reference <- isTRUE(value("funnel.reference.visible", TRUE))
    show.regression <- isTRUE(value("funnel.regression.visible", TRUE))
    show.pooled <- isTRUE(value("funnel.pooled.overlay.visible", TRUE))
    show.region <- isTRUE(value("funnel.sampling.region.visible", TRUE))
    sampling.level <- as.numeric(value("funnel.sampling.conf.level", value("conf.level", 95)))
    include.tau2 <- isTRUE(value("funnel.include.tau2", FALSE))
    label.policy <- as.character(value("funnel.label.policy", "none"))
    xlab <- as.character(value("funnel.xlab", if (as.character(value("metric", "")) %in% c("OR", "RR")) paste0(value("metric", "Effect"), " (back-transformed scale)") else value("metric", "Effect")))
    ylab <- as.character(value("funnel.ylab", "Standard error"))
    if (identical(kind, "deeks")) {
        xlab <- as.character(value("funnel.xlab", "1/sqrt(ESS)"))
        ylab <- as.character(value("funnel.ylab", "Log diagnostic odds ratio"))
    }
    xlim <- suppressWarnings(as.numeric(c(value("funnel.xlim.lower", NA_real_), value("funnel.xlim.upper", NA_real_))))
    if (length(xlim) != 2L || any(!is.finite(xlim)) || xlim[[1L]] >= xlim[[2L]]) xlim <- NULL
    at <- suppressWarnings(as.numeric(strsplit(as.character(value("funnel.xticks", "")), ",", fixed=TRUE)[[1L]]))
    if (!length(at) || any(!is.finite(at))) at <- NULL
    if (extension == "pdf") {
        grDevices::pdf(path, width=1000/120, height=800/120, bg=background.color)
    } else if (extension == "svg") {
        grDevices::svg(path, width=1000/120, height=800/120, bg=background.color)
    } else if (extension %in% c("tif", "tiff")) {
        grDevices::tiff(path, width=1000, height=800, res=120, compression="lzw", bg=background.color)
    } else {
        grDevices::png(path, width=1000, height=800, res=120, bg=background.color)
    }
    on.exit(grDevices::dev.off(), add=TRUE)
    if (identical(kind, "deeks") && is(om.data, "DiagnosticData")) {
        effective <- as.numeric(params$deeks.ess %||% numeric())
        predictor <- as.numeric(params$deeks.predictor %||% numeric())
        keep <- is.finite(y) & is.finite(se) & se > 0
        if (length(effective) != sum(keep)) stop("persisted Deeks effective sample sizes do not match prepared effects")
        plot(predictor, y[keep], xlab=xlab, ylab=ylab, xlim=xlim, xaxt=if (is.null(at)) "s" else "n", pch=point.symbol, cex=point.size, col=point.color, bg=point.color)
        if (!is.null(at)) axis(1, at=at)
        line <- as.numeric(params$deeks.line %||% c(NA_real_, NA_real_))
        if (show.regression && length(line) == 2L && all(is.finite(line))) {
            abline(a=line[[1L]], b=line[[2L]], col=reference.color)
        }
        if (label.policy == "all") text(predictor, y[keep], labels=om.data@study.names[keep], pos=4, cex=.7)
    } else if (identical(kind, "trimfill")) {
        keep <- is.finite(y) & is.finite(se) & se > 0
        model <- metafor::rma.uni(yi=y[keep], sei=se[keep], method="REML")
        center <- as.numeric(params$funnel.center %||% 0)
        ratio <- as.character(params$metric %||% "") %in% c("OR", "RR")
        funnel.args <- list(
            refline=if (show.reference && show.pooled) center else NULL, yaxis="sei",
            level=sampling.level, addtau2=include.tau2, xlab=xlab, ylab=ylab,
            atransf=if (ratio) exp else NULL, pch=point.symbol,
            cex=point.size, col=point.color, bg=point.color,
            back=background.color, shade=if (show.region) region.color else NA,
            colref=reference.color,
            colci=if (show.region) reference.color else NA,
            label=identical(label.policy, "all")
        )
        if (!is.null(xlim)) funnel.args$xlim <- xlim
        if (!is.null(at)) funnel.args$at <- at
        do.call(metafor::funnel, c(list(model), funnel.args))
        if (identical(label.policy, "outside-pseudo-confidence-region")) {
            outside <- abs(y-center) > stats::qnorm((1 + sampling.level/100)/2) * se
            text(y[outside], se[outside], labels=om.data@study.names[outside], pos=4, cex=.7)
        }
    } else if (identical(kind, "contour")) {
        model <- if (inherits(res, "rma")) res else metafor::rma.uni(yi=y[keep], sei=se[keep], method="REML")
        center <- as.numeric(params$funnel.center %||% 0)
        levels <- as.numeric(strsplit(as.character(value("funnel.contour.levels", "90,95,99")), ",", fixed=TRUE)[[1]])
        levels <- levels[is.finite(levels) & levels > 0 & levels < 100]
        if (!length(levels)) levels <- c(90, 95, 99)
        funnel.args <- list(refline=if (show.reference) 0 else NULL, level=levels, yaxis="sei", addtau2=include.tau2,
                            xlab=xlab, ylab=ylab, pch=point.symbol,
                            cex=point.size, col=point.color, bg=point.color,
                            back=background.color, shade=region.color,
                            colref=reference.color, colci=reference.color,
                            label=identical(label.policy, "all"))
        if (!is.null(xlim)) funnel.args$xlim <- xlim
        if (!is.null(at)) funnel.args$at <- at
        do.call(metafor::funnel, c(list(model), funnel.args))
        if (identical(label.policy, "outside-pseudo-confidence-region")) {
            outside <- abs(y) > stats::qnorm((1 + sampling.level/100)/2) * se
            text(y[outside], se[outside], labels=om.data@study.names[outside], pos=4, cex=.7)
        }
        if (show.pooled) abline(v=center, col=reference.color, lwd=2, lty=2)
        legend("topright", legend=c(paste0(levels, "% null contours"), if (show.pooled) "Pooled display"), bty="n")
    } else {
        center <- as.numeric(params$funnel.center %||% 0)
        ratio <- as.character(params$metric %||% "") %in% c("OR", "RR")
        funnel.args <- list(
            refline=if (show.reference && show.pooled) center else NULL,
            yaxis="sei", level=sampling.level, addtau2=include.tau2,
            xlab=xlab, ylab=ylab, atransf=if (ratio) exp else NULL,
            pch=point.symbol, cex=point.size, col=point.color,
            bg=point.color, back=background.color,
            shade=if (show.region) region.color else NA,
            colref=reference.color,
            colci=if (show.region) reference.color else NA,
            label=identical(label.policy, "all")
        )
        if (!is.null(xlim)) funnel.args$xlim <- xlim
        if (!is.null(at)) funnel.args$at <- at
        model <- if (inherits(res, "rma")) res else metafor::rma.uni(yi=y[keep], sei=se[keep], method="REML")
        do.call(metafor::funnel, c(list(model), funnel.args))
        if (identical(label.policy, "outside-pseudo-confidence-region")) {
            outside <- abs(y-center) > stats::qnorm((1 + sampling.level/100)/2) * se
            text(y[outside], se[outside], labels=om.data@study.names[outside], pos=4, cex=.7)
        }
    }
    path
}
