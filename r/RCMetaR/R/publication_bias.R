# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
#' RCMetaR implementation of the guided small-study effects analysis.
#'
#' The function is intentionally one package boundary: conversion, eligibility,
#' validation, model fitting, tests, and plot artifacts are created from the
#' same included study set.  The Python side only renders the returned report.

.small.study.method <- function(method, available, reason="", required.inputs=character(),
                                warnings=character(), role="none", usable.count=0L) {
    list(method=method, available=isTRUE(available), reason=reason,
         required.inputs=required.inputs, usable.studies=usable.count,
         warnings=warnings, role=role)
}

.small.study.first.reason <- function(conditions, messages) {
    failed <- which(!vapply(conditions, isTRUE, logical(1)))
    if (length(failed)) messages[[failed[[1L]]]] else ""
}

.small.study.common.eligibility <- function(standard.error, data.type) {
    enough <- length(standard.error) >= 3L
    variance.ok <- enough && length(unique(standard.error)) > 1L
    default.k.ok <- length(standard.error) >= 10L
    k.warning <- if (enough && !default.k.ok)
        "Disabled by default below 10 usable studies." else character()
    se.warning <- if (data.type != "diagnostic" && length(standard.error))
        "Observed standard-error range should be considered when interpreting asymmetry results; the exact range is reported in the analysis summary."
    else character()
    reason <- .small.study.first.reason(
        list(enough, variance.ok, default.k.ok),
        list("Unavailable: fewer than 3 usable included studies.",
             "Unavailable: standard-error predictor variance is zero.",
             k.warning)
    )
    list(enough=enough, variance.ok=variance.ok, default.k.ok=default.k.ok,
         available=variance.ok && default.k.ok, k.warning=k.warning,
         se.warning=se.warning, warnings=c(k.warning, se.warning), reason=reason)
}

.small.study.diagnostic.eligibility <- function(om.data, params, prepared, metric, common) {
    model <- NULL
    if (identical(metric, "DOR") && isTRUE(prepared$raw)) {
        keep <- is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
        model <- tryCatch(
            .small.study.native.model(om.data, params, metric, keep, prepared$y, prepared$se),
            error=function(e) NULL
        )
    }
    ess <- if (is.null(model)) numeric() else 4 * model$n.e * model$n.c / (model$n.e + model$n.c)
    keep <- is.finite(ess) & ess > 0 & is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
    predictor <- if (length(ess)) 1 / sqrt(ess[keep]) else numeric()
    count <- sum(keep)
    predictor.ok <- count >= 3L && length(unique(predictor)) > 1L && all(is.finite(predictor))
    available <- identical(metric, "DOR") && isTRUE(prepared$raw) && count >= 10L && predictor.ok
    reason <- .small.study.first.reason(
        list(identical(metric, "DOR"), isTRUE(prepared$raw), count >= 3L,
             count >= 10L, predictor.ok),
        list("Unavailable: Deeks is available only for diagnostic DOR.",
             "Unavailable: complete TP/FN/FP/TN counts are required; entered DOR without counts is not eligible.",
             "Unavailable: fewer than 3 usable included studies.",
             "Disabled by default below 10 usable studies.",
             "Unavailable: Deeks effective-sample-size predictor variance is zero or non-finite.")
    )
    method <- .small.study.method(
        "deeks", available, reason,
        c("TP", "FN", "FP", "TN", "one independent contribution per study, threshold, reader, and test", "ESS=4*n.e*n.c/(n.e+n.c)"),
        c(common$warnings, "Deeks uses effective-sample-size geometry and native ESS weights."),
        if (available) "primary" else "none", count
    )
    list(methods=list(method), predictor=predictor, tau=NA_real_)
}

.small.study.or.models <- function(om.data, params, prepared, metric, confidence.level) {
    keep <- is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
    tau <- params$reml.tau2
    tau.available <- is.numeric(tau) && length(tau) == 1L && is.finite(tau)
    if (!tau.available && isTRUE(prepared$raw)) {
        tau.fit <- tryCatch(.small.study.prepared.model(
            prepared$y[keep], prepared$se[keep], om.data@study.names[keep], metric,
            confidence.level=confidence.level
        ), error=function(e) NULL)
        tau <- if (is.null(tau.fit)) NA_real_ else tau.fit$tau2
        tau.available <- is.numeric(tau) && length(tau) == 1L && is.finite(tau)
    }
    model <- if (isTRUE(prepared$raw)) tryCatch(
        .small.study.native.model(om.data, params, metric, keep, prepared$y[keep], prepared$se[keep]),
        error=function(e) NULL
    ) else NULL
    asd.keep <- if (isTRUE(prepared$raw)) which(keep) else integer()
    asd <- if (length(asd.keep)) tryCatch(
        .small.study.asd.model(om.data, params, asd.keep), error=function(e) NULL
    ) else NULL
    list(model=model, asd=asd, tau=tau, tau.available=tau.available)
}

.small.study.metabias.available <- function(model, method, confidence.level) {
    if (is.null(model)) return(FALSE)
    fit <- tryCatch(meta::metabias(
        model, method.bias=method, k.min=3,
        level=.small.study.meta.level(confidence.level)
    ), error=function(e) e)
    !inherits(fit, "error")
}

.small.study.or.eligibility <- function(om.data, params, prepared, metric, common,
                                        confidence.level) {
    models <- .small.study.or.models(om.data, params, prepared, metric, confidence.level)
    count <- if (is.null(models$model)) 0L else as.integer(models$model$k)
    asd.count <- if (is.null(models$asd)) 0L else as.integer(models$asd$k)
    harbord.predictor <- .small.study.metabias.available(models$model, "Harbord", confidence.level)
    peters.predictor <- .small.study.metabias.available(models$model, "Peters", confidence.level)
    asd.predictor <- .small.study.metabias.available(models$asd, "Thompson", confidence.level)
    harbord.conditions <- list(isTRUE(prepared$raw), count >= 3L, count >= 10L,
                               harbord.predictor, models$tau.available, models$tau <= 0.1)
    harbord <- all(vapply(harbord.conditions, isTRUE, logical(1)))
    harbord.reason <- .small.study.first.reason(harbord.conditions, list(
        "Unavailable: complete two-arm raw counts are required for Harbord.",
        "Unavailable: fewer than 3 usable included studies.",
        "Disabled by default below 10 usable studies.",
        "Unavailable: Harbord score predictor variance is zero or non-finite.",
        "Unavailable: REML log-OR tau^2 is unavailable; no primary fallback is selected.",
        "Unavailable: REML log-OR tau^2 is above 0.1; use R\u00fccker AS+RE."))
    rucker.conditions <- list(isTRUE(prepared$raw), asd.count >= 3L, asd.count >= 10L,
                              asd.predictor, models$tau.available)
    rucker <- all(vapply(rucker.conditions, isTRUE, logical(1)))
    rucker.reason <- .small.study.first.reason(rucker.conditions, list(
        "Unavailable: complete two-arm raw counts are required for R\u00fccker AS+RE.",
        "Unavailable: fewer than 3 usable included studies.",
        "Disabled by default below 10 usable studies.",
        "Unavailable: ASD standard-error predictor variance is zero or non-finite.",
        "Unavailable: REML log-OR tau^2 is unavailable; no primary fallback is selected."))
    peters.conditions <- list(isTRUE(prepared$raw), count >= 3L, count >= 10L, peters.predictor)
    peters <- all(vapply(peters.conditions, isTRUE, logical(1)))
    peters.reason <- .small.study.first.reason(peters.conditions, list(
        "Unavailable: complete two-arm raw counts are required for Peters.",
        "Unavailable: fewer than 3 usable included studies.",
        "Disabled by default below 10 usable studies.",
        "Unavailable: Peters sample-size predictor variance is zero or non-finite."))
    methods <- list(
        .small.study.method("harbord", harbord, harbord.reason,
                            c("two-arm counts", "REML log-OR tau^2"), common$warnings,
                            if (harbord) "primary" else "none", count),
        .small.study.method("rucker-as-re", rucker, rucker.reason,
                            c("two-arm counts", "AS+RE model"), common$warnings,
                            if (rucker && harbord) "sensitivity" else if (rucker) "primary" else "none", asd.count),
        .small.study.method("peters", peters, peters.reason,
                            c("two-arm counts", "Peters sample-size predictor"), common$warnings,
                            "sensitivity", count)
    )
    list(methods=methods, predictor=numeric(), tau=models$tau)
}

.small.study.smd.eligibility <- function(om.data, params, prepared, metric, common,
                                         confidence.level) {
    keep <- is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0
    model <- if (isTRUE(prepared$raw)) tryCatch(
        .small.study.native.model(om.data, params, metric, keep, prepared$y, prepared$se),
        error=function(e) NULL
    ) else NULL
    count <- if (is.null(model)) 0L else as.integer(model$k)
    predictor <- .small.study.metabias.available(model, "Pustejovsky", confidence.level)
    conditions <- list(isTRUE(prepared$raw), count >= 3L, count >= 10L, predictor)
    available <- all(vapply(conditions, isTRUE, logical(1)))
    reason <- .small.study.first.reason(conditions, list(
        "Unavailable: independent two-group sample sizes, means, and SDs are required.",
        "Unavailable: fewer than 3 usable included studies.",
        "Disabled by default below 10 usable studies.",
        "Unavailable: Pustejovsky predictor variance is zero or non-finite."))
    egger <- common$enough && common$default.k.ok && common$variance.ok
    egger.reason <- .small.study.first.reason(
        list(common$enough, common$default.k.ok, common$variance.ok),
        list("Unavailable: fewer than 3 usable included studies.", common$k.warning,
             "Unavailable: standard-error predictor variance is zero."))
    usable <- length(prepared$se[keep])
    methods <- list(
        .small.study.method("pustejovsky-rodgers", available, reason,
                            "independent two-group data", common$warnings,
                            if (available) "primary" else "none", usable),
        .small.study.method("classical-egger", egger, egger.reason,
                            c("entered effect estimates", "standard errors", "effect-SE artifact caveat"),
                            common$warnings, if (egger) "sensitivity" else "none",
                            length(prepared$se[keep]))
    )
    list(methods=methods, predictor=numeric(), tau=NA_real_)
}

.small.study.default.eligibility <- function(common, count) {
    role <- if (common$variance.ok) "exploratory" else "none"
    inputs <- c("effect estimates", "standard errors")
    list(methods=list(
        .small.study.method("classical-egger", common$available, common$reason,
                            c(inputs, "standard-error-range report"), common$warnings,
                            if (common$available) "primary" else "none", count),
        .small.study.method("mixed-effects-egger", common$available, common$reason,
                            c(inputs, "REML model", "standard-error-range report"), common$warnings,
                            role, count),
        .small.study.method("begg-mazumdar", common$available, common$reason,
                            c(inputs, "rank-correlation test", "standard-error-range report"),
                            common$warnings, role, count)
    ), predictor=numeric(), tau=NA_real_)
}

.small.study.disable.unsupported.methods <- function(methods, metric) {
    if (!(metric %in% c("RR", "RD", "PR", "PLN", "PLO", "PAS", "PFT"))) return(methods)
    lapply(methods, function(method) {
        method$available <- FALSE
        method$role <- "none"
        method$reason <- "No automatic primary asymmetry test is configured for this effect measure."
        method
    })
}

.small.study.eligibility.warnings <- function(metric, data.type, se.warning, predictor) {
    warnings <- se.warning
    if (data.type == "diagnostic" && length(predictor)) warnings <- c(
        warnings, paste0("Observed Deeks ESS predictor range: [",
                         .small.study.exact.number(min(predictor)), ", ",
                         .small.study.exact.number(max(predictor)), "]."))
    if (metric %in% c("PR", "PLN", "PLO", "PAS", "PFT")) warnings <- c(
        warnings, "One-arm proportion results are descriptive effect-SE artifacts; no formal automatic primary asymmetry test is configured.")
    if (metric %in% c("RR", "RD")) warnings <- c(
        warnings, "No automatic primary asymmetry test is configured for this effect measure; ordinary and contour plots remain descriptive.")
    if (metric == "SMD") warnings <- c(
        warnings, "Ordinary SMD Egger is a separate effect-SE artifact and is never an automatic primary method.")
    warnings
}

.small.study.eligibility <- function(om.data, params=list(), prepared=NULL) {
    if (!is(om.data, "OMData")) stop("RCMetaR data expected.")
    metric <- as.character(params$metric %||% "")
    data.type <- as.character(params$data.type %||% if (is(om.data, "BinaryData"))
        "binary" else if (is(om.data, "ContinuousData")) "continuous" else "diagnostic")
    confidence.level <- .small.study.confidence.level(params)
    if (is.null(prepared)) prepared <- tryCatch(
        .small.study.reconstruct(om.data, metric, params),
        error=function(e) list(y=om.data@y, se=om.data@SE, raw=FALSE)
    )
    included <- which(is.finite(prepared$y) & is.finite(prepared$se) & prepared$se > 0)
    standard.error <- prepared$se[included]
    common <- .small.study.common.eligibility(standard.error, data.type)
    routed <- if (data.type == "diagnostic")
        .small.study.diagnostic.eligibility(om.data, params, prepared, metric, common)
    else if (metric == "OR")
        .small.study.or.eligibility(om.data, params, prepared, metric, common, confidence.level)
    else if (metric == "SMD")
        .small.study.smd.eligibility(om.data, params, prepared, metric, common, confidence.level)
    else .small.study.default.eligibility(common, length(standard.error))
    methods <- .small.study.disable.unsupported.methods(routed$methods, metric)
    warnings <- .small.study.eligibility.warnings(
        metric, data.type, common$se.warning, routed$predictor)
    list(`data.type`=data.type, metric=metric, `usable.studies`=length(standard.error),
         `included.indices`=included, `raw.data.available`=isTRUE(prepared$raw),
         `standard.error.range`=if (length(standard.error)) range(standard.error) else numeric(),
         `reml.tau2`=as.numeric(routed$tau), methods=methods, warnings=warnings,
         `package.versions`=c(meta=utils::packageDescription("meta")$Version,
                              metafor=utils::packageDescription("metafor")$Version))
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

.small.study.test.interval <- function(fit, confidence.level) {
    coefficient <- as.numeric(fit$estimate[[1L]] %||% NA_real_)
    standard.error <- as.numeric(fit$estimate[[2L]] %||% NA_real_)
    df <- as.numeric(fit$df %||% NA_real_)
    interval <- if (is.finite(coefficient) && is.finite(standard.error) && is.finite(df))
        coefficient + c(-1, 1) * stats::qt((1 + confidence.level / 100) / 2, df) * standard.error else c(NA_real_, NA_real_)
    list(coefficient=coefficient, standard.error=standard.error, df=df,
         interval=as.numeric(interval))
}

.small.study.fit.deeks <- function(prepared, entry, k.min) {
    params <- prepared$params
    confidence.level <- prepared$confidence.level
    fit.model <- prepared$native.model
    fit <- meta::metabias(fit.model, method.bias="Deeks", k.min=k.min,
                         level=.small.study.meta.level(confidence.level))
    estimate <- .small.study.test.interval(fit, confidence.level)
    ess <- 4 * fit.model$n.e * fit.model$n.c / (fit.model$n.e + fit.model$n.c)
    list(
        method="Deeks test (meta implementation)", role=entry$role, package="meta",
        package.version=utils::packageDescription("meta")$Version,
        call=paste0("meta::metabin(event.e=TP, n.e=TP+FN, event.c=FP, n.c=FP+TN, sm='OR', incr=0.5, method.incr='", .small.study.correction.method(params), "', common=TRUE, random=TRUE, method.tau='REML', level=", .small.study.meta.level(confidence.level), "); meta::metabias(x=prepared.DOR.model, method.bias='Deeks', k.min=", k.min, ", level=", .small.study.meta.level(confidence.level), ")"),
        predictor="1/sqrt(ESS), ESS=4*n.e*n.c/(n.e+n.c)", weighting="native ESS weights",
        inference="t-based Deeks regression test", model="Deeks effective-sample-size weighted regression",
        usable.studies=as.numeric(fit.model$k), df=estimate$df,
        p.value=as.numeric(fit$p.value %||% NA_real_), statistic=as.numeric(fit$statistic %||% NA_real_),
        coefficient=estimate$coefficient, standard.error=estimate$standard.error,
        confidence.interval=estimate$interval,
        intercept=as.numeric(fit$intercept %||% NA_real_), se.intercept=as.numeric(fit$se.intercept %||% NA_real_),
        prepared.effects=as.numeric(prepared$y), prepared.standard.errors=as.numeric(prepared$se),
        effective.sample.size=as.numeric(ess), deeks.predictor=as.numeric(1 / sqrt(ess)),
        deeks.weights=as.numeric(ess)
    )
}

.small.study.fit.mixed.egger <- function(prepared, entry) {
    confidence.level <- prepared$confidence.level
    fit <- metafor::regtest(prepared$y, sei=prepared$se, model="rma", predictor="sei",
                           ret.fit=TRUE, level=confidence.level)
    model <- fit$fit
    list(
        method="mixed-effects-egger", role=entry$role, package="metafor",
        package.version=utils::packageDescription("metafor")$Version,
        call=paste0("metafor::regtest(x=prepared.effects, sei=prepared.standard.errors, model='rma', predictor='sei', ret.fit=TRUE, level=", confidence.level, ")"),
        predictor="SE", weighting="inverse-variance weights with REML heterogeneity",
        inference="z test from metafor::regtest", model="REML mixed-effects meta-regression",
        usable.studies=length(prepared$y), df=as.numeric(fit$dfs %||% NA_real_),
        p.value=as.numeric(fit$pval), statistic=as.numeric(fit$zval),
        coefficient=as.numeric(model$b[2]), standard.error=as.numeric(model$se[2]),
        intercept=as.numeric(model$b[1]), se.intercept=as.numeric(model$se[1]),
        confidence.interval=as.numeric(c(model$ci.lb[2], model$ci.ub[2])),
        confidence.interval.intercept=as.numeric(c(model$ci.lb[1], model$ci.ub[1]))
    )
}

.small.study.fit.pustejovsky <- function(prepared, entry, k.min) {
    confidence.level <- prepared$confidence.level
    fit <- meta::metabias(prepared$native.model, method.bias="Pustejovsky", k.min=k.min,
                         level=.small.study.meta.level(confidence.level))
    estimate <- .small.study.test.interval(fit, confidence.level)
    list(
        method="pustejovsky-rodgers", role=entry$role, package="meta",
        package.version=utils::packageDescription("meta")$Version,
        call=paste0("meta::metacont(n.e, mean.e, sd.e, n.c, mean.c, sd.c, sm='SMD', common=TRUE, random=TRUE, method.tau='REML', level=", .small.study.meta.level(confidence.level), "); meta::metabias(x=prepared.SMD.model, method.bias='Pustejovsky', k.min=", k.min, ", level=", .small.study.meta.level(confidence.level), ")"),
        predictor="sqrt(1/n.e + 1/n.c)", weighting="inverse variance from native Pustejovsky standard errors",
        inference="t-based Pustejovsky regression test",
        model="Pustejovsky-Rodgers independent two-group regression",
        usable.studies=length(prepared$y), df=estimate$df,
        p.value=as.numeric(fit$p.value %||% NA_real_), statistic=as.numeric(fit$statistic %||% NA_real_),
        coefficient=estimate$coefficient, standard.error=estimate$standard.error,
        confidence.interval=estimate$interval,
        intercept=as.numeric(fit$intercept %||% NA_real_), se.intercept=as.numeric(fit$se.intercept %||% NA_real_),
        prepared.effects=as.numeric(prepared$y), prepared.standard.errors=as.numeric(prepared$se)
    )
}

.small.study.fit.classical <- function(prepared, entry, method, k.min) {
    confidence.level <- prepared$confidence.level
    bias.method <- if (method == "classical-egger") "Egger" else "Begg"
    fit <- meta::metabias(prepared$pooled, method.bias=bias.method, k.min=k.min,
                         level=.small.study.meta.level(confidence.level))
    estimate <- .small.study.test.interval(fit, confidence.level)
    list(
        method=method, role=entry$role, package="meta",
        package.version=utils::packageDescription("meta")$Version,
        call=paste0("meta::metabias(x=prepared.meta.model, method.bias='", bias.method, "', k.min=", k.min, ", level=", .small.study.meta.level(confidence.level), ")"),
        predictor=if (method == "begg-mazumdar") "rank correlation of standardized effects and variance" else "SE",
        weighting=if (method == "begg-mazumdar") "not applicable (Kendall rank-based test)" else "inverse variance",
        inference=if (method == "begg-mazumdar") "z test from Kendall rank correlation" else "t-based meta::metabias test",
        model=if (method == "begg-mazumdar") "Begg-Mazumdar rank correlation" else "multiplicative Egger regression",
        usable.studies=length(prepared$y), df=estimate$df,
        p.value=as.numeric(fit$p.value %||% NA_real_), statistic=as.numeric(fit$statistic %||% NA_real_),
        coefficient=estimate$coefficient, standard.error=estimate$standard.error,
        confidence.interval=estimate$interval,
        intercept=if (method == "classical-egger") as.numeric(fit$intercept %||% NA_real_) else NA_real_,
        se.intercept=if (method == "classical-egger") as.numeric(fit$se.intercept %||% NA_real_) else NA_real_
    )
}

.small.study.prepare.or.test <- function(om.data, prepared, method, k.min) {
    params <- prepared$params
    meta.level <- .small.study.meta.level(prepared$confidence.level)
    if (method == "rucker-as-re") {
        fit.model <- .small.study.asd.model(om.data, params, which(prepared$keep))
        bias.method <- "Thompson"
        fit.call <- paste0("meta::metabin(event.e, n.e, event.c, n.c, sm='ASD', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, ")")
        test.call <- paste0("meta::metabias(x=prepared.ASD.model, method.bias='Thompson', k.min=", k.min, ", level=", meta.level, ")")
    } else {
        fit.model <- prepared$native.model
        bias.method <- if (method == "harbord") "Harbord" else "Peters"
        fit.call <- paste0("meta::metabin(event.e, n.e, event.c, n.c, sm='OR', incr=0.5, method.incr='", .small.study.correction.method(params), "', common=TRUE, random=TRUE, method.tau='REML', level=", meta.level, ")")
        if (method == "peters") {
            fit.model$TE <- prepared$y
            fit.model$seTE <- prepared$se
        }
        test.call <- paste0(if (method == "peters") "prepared.OR.model$TE <- prepared.effects; prepared.OR.model$seTE <- prepared.standard.errors; " else "",
                            "meta::metabias(x=prepared.OR.model, method.bias='", bias.method,
                            "', k.min=", k.min, ", level=", meta.level, ")")
    }
    list(model=fit.model, bias.method=bias.method,
         call=paste0(fit.call, "; ", test.call), level=meta.level)
}

.small.study.fit.or.method <- function(om.data, prepared, entry, method, k.min) {
    input <- .small.study.prepare.or.test(om.data, prepared, method, k.min)
    fit <- meta::metabias(input$model, method.bias=input$bias.method,
                         k.min=k.min, level=input$level)
    estimate <- .small.study.test.interval(fit, prepared$confidence.level)
    list(
        method=method, role=entry$role, package="meta",
        package.version=utils::packageDescription("meta")$Version,
        call=input$call,
        predictor=if (method == "harbord") "Harbord Z/V on 1/sqrt(V), where V is the native score variance" else if (method == "peters") "1/(n.e+n.c), with native Peters seTE=sqrt(1/(event.e+event.c)+1/(non-events.e+non-events.c))" else "ASD effect on native ASD standard error",
        weighting=if (method == "harbord") "native Harbord score variance V" else if (method == "peters") "1/Peters seTE^2" else "native AS+RE additive REML weights",
        inference="t-based meta::metabias test",
        model=if (method == "rucker-as-re") "R\u00fccker AS+RE (ASD + Thompson)" else paste0(input$bias.method, " native metabin model"),
        usable.studies=if (method == "rucker-as-re") as.numeric(input$model$k) else length(prepared$y),
        df=estimate$df, p.value=as.numeric(fit$p.value %||% NA_real_),
        statistic=as.numeric(fit$statistic %||% NA_real_), coefficient=estimate$coefficient,
        standard.error=estimate$standard.error, confidence.interval=estimate$interval,
        intercept=if (method == "peters") as.numeric(fit$intercept %||% NA_real_) else NA_real_,
        se.intercept=if (method == "peters") as.numeric(fit$se.intercept %||% NA_real_) else NA_real_,
        prepared.effects=as.numeric(prepared$y), prepared.standard.errors=as.numeric(prepared$se),
        routing.effects=as.numeric(prepared$y), routing.standard.errors=as.numeric(prepared$se)
    )
}

.small.study.fit.one <- function(om.data, prepared, method, entry, k.min=10L) {
    switch(method,
        "deeks"=.small.study.fit.deeks(prepared, entry, k.min),
        "mixed-effects-egger"=.small.study.fit.mixed.egger(prepared, entry),
        "pustejovsky-rodgers"=.small.study.fit.pustejovsky(prepared, entry, k.min),
        "classical-egger"=.small.study.fit.classical(prepared, entry, method, k.min),
        "begg-mazumdar"=.small.study.fit.classical(prepared, entry, method, k.min),
        "harbord"=.small.study.fit.or.method(om.data, prepared, entry, method, k.min),
        "peters"=.small.study.fit.or.method(om.data, prepared, entry, method, k.min),
        "rucker-as-re"=.small.study.fit.or.method(om.data, prepared, entry, method, k.min),
        stop("unsupported selected asymmetry method: ", method)
    )
}

.small.study.fit.tests <- function(om.data, prepared, selected) {
    tests <- list()
    failures <- character()
    for (method in selected) {
        tryCatch({
            matches <- vapply(prepared$eligibility$methods,
                              function(x) identical(x$method, method), logical(1))
            entry <- prepared$eligibility$methods[matches][[1L]]
            if (is.null(entry) || !isTRUE(entry$available))
                stop(entry$reason %||% "method is unavailable")
            tests[[method]] <- .small.study.fit.one(om.data, prepared, method, entry)
        }, error=function(e) failures <<- c(
            failures, paste(.small.study.method.label(method), conditionMessage(e), sep=": ")
        ))
    }
    list(tests=tests, failures=failures)
}

.small.study.primary.summary <- function(eligibility, selected, tests, confidence.level) {
    primary.methods <- vapply(
        eligibility$methods,
        function(x) identical(x$role, "primary") && isTRUE(x$available),
        logical(1)
    )
    name <- if (any(primary.methods))
        vapply(eligibility$methods[primary.methods], `[[`, character(1), "method")[[1L]] else "None"
    test <- if (name != "None") tests[[name]] else NULL
    if (is.null(test)) {
        text <- if (name == "None") .small.study.no.test.summary(eligibility, selected) else
            paste0("Primary asymmetry test: ", .small.study.method.label(name), "; result unavailable.")
        return(list(name=name, text=text))
    }
    p.value <- as.numeric(test$p.value %||% NA_real_)
    coefficient <- as.numeric(test$coefficient %||% NA_real_)
    interval <- as.numeric(test$confidence.interval %||% c(NA_real_, NA_real_))
    if (length(interval) < 2L) interval <- c(interval, NA_real_)[1:2]
    result <- if (!is.finite(p.value)) "p-value not available" else if (p.value < .05)
        paste0("evidence of small-study effects (p = ", .small.study.p.value(p.value), ")") else
        paste0("no clear evidence of small-study effects (p = ", .small.study.p.value(p.value), ")")
    text <- paste(c(
        paste0("Primary asymmetry test: ", .small.study.method.label(name)),
        paste0("Result: ", result),
        paste0("Usable studies: ", .small.study.integer(test$usable.studies)),
        paste0("Estimate: ", .small.study.number(coefficient), " (",
               .small.study.confidence.label(confidence.level, short=TRUE), " ",
               .small.study.number(interval[[1L]]), " to ",
               .small.study.number(interval[[2L]]), ")")
    ), collapse="\n")
    list(name=name, text=text)
}

.small.study.warning.text <- function(metric, eligibility, primary.summary) {
    text <- paste(c(
        primary.summary,
        "Funnel plot asymmetry can reflect publication bias, heterogeneity, study design, or chance.",
        "Interpret the plots and tests together. No single result proves or rules out publication bias."
    ), collapse="\n\n")
    cautions <- c(
        if (metric %in% c("PR", "PLN", "PLO", "PAS", "PFT"))
            "For one-arm proportions, the funnel plot is descriptive because the effect and its standard error are mathematically related.",
        if (metric %in% c("RR", "RD"))
            "No automatic primary asymmetry test is available for this effect measure.",
        if (metric == "SMD")
            "The ordinary Egger test is not selected for standardized mean differences because it can create effect-standard-error artifacts."
    )
    warnings <- unique(as.character(eligibility$warnings %||% character()))
    warnings <- warnings[!is.na(warnings) & nzchar(trimws(warnings))]
    if (length(warnings)) cautions <- c(
        cautions, paste(c("Analysis warnings:", paste0("- ", warnings)), collapse="\n")
    )
    paste(c(text, cautions), collapse="\n\n")
}

.small.study.analysis.summary <- function(prepared, primary.name) {
    metric <- prepared$metric
    params <- prepared$params
    summary <- c(
        paste0("Effect measure: ", .small.study.metric.label(metric), " (", metric, ")"),
        paste0("Studies analyzed: ", length(prepared$y)),
        paste0("Confidence level: ", .small.study.confidence.label(prepared$confidence.level)),
        paste0("Primary test: ", if (primary.name == "None") "None available" else .small.study.method.label(primary.name))
    )
    if (length(prepared$se)) summary <- c(
        summary, paste0("Observed standard-error range: [",
                        .small.study.exact.number(min(prepared$se)), ", ",
                        .small.study.exact.number(max(prepared$se)), "]")
    )
    if (metric == "OR") summary <- c(
        summary,
        paste0("Heterogeneity (REML tau-squared): ", .small.study.number(prepared$pooled$tau2 %||% NA_real_)),
        paste0("Continuity correction: ", as.character(params$correction.policy %||% "Studies with any zero cell"))
    )
    if (metric == "DOR") summary <- c(
        summary,
        paste0("Continuity correction: ", as.character(params$correction.policy %||% "All studies if any zero exists")),
        "Plot method: Deeks funnel plot using effective sample size"
    )
    paste(summary, collapse="\n")
}

.small.study.section.id <- function(name) {
    fixed <- c(
        Warning="small-study.warning",
        `Data and eligibility`="small-study.data-eligibility",
        Tests="small-study.tests",
        `Pooled comparison`="small-study.pooled-comparison",
        References="small-study.references",
        Failures="small-study.failures",
        `Method details`="small-study.method-details",
        `Methods not applicable`="small-study.methods-not-applicable",
        Extrapolation="small-study.extrapolation"
    )
    id <- fixed[[name]]
    if (!is.null(id)) return(id)
    if (startsWith(name, "Trim-and-fill "))
        return(paste0("small-study.trim-and-fill.",
                      gsub("[^a-z0-9]+", "-", tolower(sub("^Trim-and-fill ", "", name)))))
    paste0("small-study.", gsub("[^a-z0-9]+", "-", tolower(name)))
}

.small.study.sections <- function(output, plots) {
    metadata <- c("eligibility", "tests.data", "Trim-and-fill data")
    text.names <- names(output)[vapply(output, function(value) !is.null(value), logical(1))]
    text.names <- setdiff(text.names, metadata)
    sections <- Map(function(name, order) list(
        id=.small.study.section.id(name), kind="text", order=as.integer(order),
        title=name, source_key=name
    ), text.names, seq_along(text.names) - 1L)
    image.names <- names(plots$images %||% character())
    if (length(image.names)) {
        kinds <- vapply(image.names, function(title) {
            kind <- plots$plot_names[[tolower(title)]] %||% "plot"
            as.character(kind)
        }, character(1))
        occurrences <- ave(seq_along(kinds), kinds, FUN=seq_along)
        image.sections <- Map(function(title, kind, occurrence, order) list(
            id=paste0("small-study.", kind, ".", occurrence), kind="image",
            order=as.integer(order), title=title, source_key=title
        ), image.names, kinds, occurrences,
        length(sections) + seq_along(image.names) - 1L)
        sections <- c(sections, image.sections)
    }
    sections
}

.small.study.render.plots <- function(om.data, prepared, trimfill) {
    if (prepared$diagnostic && !isTRUE(prepared$derived$raw))
        return(list(images=character(), plot_capabilities=list(), plot_names=character(),
                    plot_params_paths=list(), image_order=character(), failures=character()))
    .small.study.plots(
        om.data, prepared$metafor.pooled, prepared$params, prepared$metric,
        common.center=prepared$pooled$TE.common, prepared=prepared$derived,
        trimfill=trimfill,
        diagnostic.model=if (prepared$diagnostic) prepared$native.model else NULL
    )
}

.small.study.serialize <- function(prepared, tests, failures, primary, trimfill,
                                   extrapolation, plots) {
    output <- list(
        Warning=.small.study.warning.text(prepared$metric, prepared$eligibility, primary$text),
        `Data and eligibility`=.small.study.analysis.summary(prepared, primary$name),
        Tests=.small.study.tests.text(tests, prepared$confidence.level),
        References=character(),
        Failures=if (length(failures)) paste(failures, collapse="\n") else NULL,
        eligibility=prepared$eligibility,
        tests.data=tests,
        `Trim-and-fill data`=if (!is.null(trimfill)) trimfill else NULL
    )
    if (!prepared$diagnostic) output <- append(
        output,
        list(`Pooled comparison`=.small.study.pooled.text(
            prepared$pooled, prepared$metric, prepared$confidence.level
        )),
        after=3L
    )
    output <- c(output, list(
        `Method details`=.small.study.method.details(tests),
        `Methods not applicable`=.small.study.methods.not.applicable(prepared$eligibility)
    ))
    if (!is.null(trimfill)) output <- c(output, trimfill$text)
    if (!is.null(extrapolation)) output <- c(output, extrapolation)
    trimfill.failures <- trimfill$failures %||% character()
    if (length(trimfill.failures)) trimfill.failures <- paste0("trim-and-fill: ", trimfill.failures)
    plot.failures <- c(trimfill.failures, plots$failures %||% character())
    if (length(plot.failures)) output$Failures <- paste(c(failures, plot.failures), collapse="\n")
    output$References <- .small.study.references(names(tests), names(plots$images))
    output$sections <- .small.study.sections(output, plots)
    plots$failures <- NULL
    c(output, plots)
}

.small.study.fit.report <- function(om.data, params, prepared) {
    selected <- .small.study.select.methods(
        prepared$eligibility, params, prepared$metric, prepared$diagnostic
    )
    fitted <- .small.study.fit.tests(om.data, prepared, selected)
    primary <- .small.study.primary.summary(
        prepared$eligibility, selected, fitted$tests, prepared$confidence.level
    )
    trimfill <- if (isTRUE(params$trim.and.fill) && prepared$metric != "DOR" &&
                        !prepared$metric %in% c("PR", "PLN", "PLO", "PAS", "PFT"))
        .small.study.trimfill(
            prepared$pooled, params, prepared$metric, prepared=prepared$derived
        ) else NULL
    extrapolation <- if (prepared$diagnostic) NULL else .small.study.extrapolation(
        fitted$tests, params, prepared$metric, eligibility=prepared$eligibility
    )
    plots <- .small.study.render.plots(om.data, prepared, trimfill)
    .small.study.serialize(
        prepared, fitted$tests, fitted$failures, primary, trimfill,
        extrapolation, plots
    )
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

.small.study.plot.setting <- function(params, name, index, default) {
    value <- params[[name]]
    if (is.null(value) || !length(value)) return(default)
    value[[min(index, length(value))]]
}

.small.study.plot.kind <- function(kind) {
    if (kind == "ordinary") return("funnel")
    if (kind == "contour") return("contour_funnel")
    if (kind == "deeks") return("deeks_funnel")
    "trimfill_funnel"
}

.small.study.plot.artifact <- function(title, kind, path, plot.data, fit, params,
                                       failure.prefix=title) {
    failure <- tryCatch({
        rcmetar.regenerate.small.study.funnel(plot.data, fit, params, path)
        NULL
    }, error=function(e) paste0(failure.prefix, ": ", conditionMessage(e)))
    if (!is.null(failure)) return(list(failure=failure))
    plot.kind <- .small.study.plot.kind(kind)
    capability <- list(plot_kind=plot.kind, editable=TRUE, styleable=TRUE,
                       composition="single", regenerator="funnel")
    base <- sub("\\.png$", "", path)
    .small.study.save(plot.data, fit, params, base)
    list(title=title, path=path, kind=plot.kind, capability=capability,
         params.path=base, failure=character())
}

.small.study.deeks.params <- function(params, om.data, prepared, diagnostic.model) {
    if (!is(om.data, "DiagnosticData")) stop("Deeks funnel requires diagnostic data.")
    if (is.null(diagnostic.model)) stop("Deeks funnel requires a prepared diagnostic model.")
    effective <- 4 * diagnostic.model$n.e * diagnostic.model$n.c /
        (diagnostic.model$n.e + diagnostic.model$n.c)
    keep <- is.finite(effective) & effective > 0 & is.finite(prepared$y)
    params$deeks.ess <- effective[keep]
    params$deeks.predictor <- 1 / sqrt(effective[keep])
    params$deeks.weights <- effective[keep]
    line <- stats::lm(prepared$y[keep] ~ params$deeks.predictor,
                      weights=params$deeks.weights)
    params$deeks.line <- c(intercept=unname(stats::coef(line)[[1L]]),
                          slope=unname(stats::coef(line)[[2L]]))
    params$deeks.correction.policy <- as.character(
        params$correction.policy %||% "All studies if any zero exists")
    params
}

.small.study.base.plot <- function(kind, index, plot.data, pooled, params, metric,
                                   common.center, prepared, diagnostic.model) {
    title <- if (kind == "ordinary") "Ordinary Funnel Plot" else if (kind == "deeks")
        "Deeks Effective-Sample-Size Funnel Plot" else "Contour Funnel Plot"
    metric.label <- if (metric %in% c("OR", "RR"))
        paste0(metric, " (back-transformed scale)") else metric
    xlab <- .small.study.plot.setting(
        params, "funnel.xlab", index, if (kind == "deeks") "1/sqrt(ESS)" else metric.label)
    ylab <- .small.study.plot.setting(
        params, "funnel.ylab", index,
        if (kind == "deeks") "Log diagnostic odds ratio" else "Standard error")
    run.params <- params
    run.params$funnel.kind <- kind
    run.params$funnel.index <- index
    run.params$funnel.center <- common.center
    run.params$prepared.effects <- prepared$y
    run.params$prepared.standard.errors <- prepared$se
    run.params$funnel.xlab <- as.character(xlab)
    run.params$funnel.ylab <- as.character(ylab)
    if (kind == "deeks") run.params <- .small.study.deeks.params(
        run.params, plot.data, prepared, diagnostic.model)
    path <- tempfile(pattern=paste0("small-study-", kind, "-"), fileext=".png")
    .small.study.plot.artifact(title, kind, path, plot.data, pooled, run.params)
}

.small.study.trimfill.plot <- function(name, scenario, plot.data, params, metric) {
    augmented <- plot.data
    augmented@y <- scenario$augmented.effects
    augmented@SE <- scenario$augmented.standard.errors
    augmented@study.names <- scenario$study.labels
    run.params <- params
    run.params$funnel.kind <- "trimfill"
    run.params$funnel.index <- 1L
    run.params$trimfill.scenario <- name
    run.params$trim.and.fill.estimator <- scenario$estimator
    run.params$trim.and.fill.side <- scenario$side
    run.params$trim.and.fill.model <- scenario$model
    run.params$funnel.center <- scenario$display.center
    run.params$prepared.effects <- scenario$augmented.effects
    run.params$prepared.standard.errors <- scenario$augmented.standard.errors
    label <- if (metric %in% c("OR", "RR"))
        paste0(metric, " (back-transformed scale)") else metric
    run.params$funnel.xlab <- as.character(
        .small.study.plot.setting(params, "funnel.xlab", 1L, label))
    run.params$funnel.ylab <- as.character(
        .small.study.plot.setting(params, "funnel.ylab", 1L, "Standard error"))
    path <- tempfile(pattern="small-study-trimfill-", fileext=".png")
    .small.study.plot.artifact(
        name, "trimfill", path, augmented, scenario$fit, run.params,
        paste0(name, " plot"))
}

.small.study.collect.plots <- function(artifacts) {
    valid <- artifacts[vapply(artifacts, function(item) !is.null(item$title), logical(1))]
    failures <- as.character(unlist(lapply(artifacts, `[[`, "failure"), use.names=FALSE))
    paths <- stats::setNames(vapply(valid, `[[`, character(1), "path"),
                             vapply(valid, `[[`, character(1), "title"))
    kinds <- stats::setNames(vapply(valid, `[[`, character(1), "kind"),
                             tolower(names(paths)))
    params.paths <- stats::setNames(vapply(valid, `[[`, character(1), "params.path"),
                                    names(paths))
    capabilities <- stats::setNames(lapply(valid, `[[`, "capability"), names(paths))
    list(images=paths, plot_capabilities=capabilities, plot_names=kinds,
         plot_params_paths=params.paths, image_order=names(paths), failures=failures)
}

.small.study.plots <- function(om.data, pooled, params, metric, common.center=0,
                               prepared=NULL, trimfill=NULL, diagnostic.model=NULL) {
    if (is.null(prepared)) prepared <- .small.study.reconstruct(om.data, metric, params)
    plot.data <- om.data
    plot.data@y <- prepared$y
    plot.data@SE <- prepared$se
    kinds <- as.character(params$funnels %||% "ordinary")
    artifacts <- Map(
        function(kind, index) .small.study.base.plot(
            kind, index, plot.data, pooled, params, metric, common.center,
            prepared, diagnostic.model),
        kinds, seq_along(kinds))
    if (!is.null(trimfill) && length(trimfill$scenarios)) artifacts <- c(
        artifacts,
        Map(function(name, scenario) .small.study.trimfill.plot(
            name, scenario, plot.data, params, metric),
            names(trimfill$scenarios), trimfill$scenarios))
    .small.study.collect.plots(artifacts)
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
    if (length(params$version) != 1L || !identical(params$version, 1L))
        stop("Unsupported small-study effects request version.", call.=FALSE)
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

.small.study.funnel.index <- function(params) {
    index <- suppressWarnings(as.integer(params$funnel.index %||% 1L))
    if (!length(index) || !is.finite(index[[1L]]) || index[[1L]] < 1L) return(1L)
    index[[1L]]
}

.small.study.funnel.limits <- function(params, index) {
    value <- function(name, default) .small.study.plot.setting(params, name, index, default)
    xlim <- suppressWarnings(as.numeric(c(
        value("funnel.xlim.lower", NA_real_), value("funnel.xlim.upper", NA_real_))))
    if (length(xlim) != 2L || any(!is.finite(xlim)) || xlim[[1L]] >= xlim[[2L]])
        xlim <- NULL
    at <- suppressWarnings(as.numeric(strsplit(
        as.character(value("funnel.xticks", "")), ",", fixed=TRUE)[[1L]]))
    if (!length(at) || any(!is.finite(at))) at <- NULL
    list(xlim=xlim, at=at)
}

.small.study.funnel.settings <- function(params) {
    index <- .small.study.funnel.index(params)
    value <- function(name, default) .small.study.plot.setting(params, name, index, default)
    kind <- as.character(params$funnel.kind %||% "ordinary")
    metric <- as.character(value("metric", ""))
    default.xlab <- if (metric %in% c("OR", "RR"))
        paste0(value("metric", "Effect"), " (back-transformed scale)")
    else value("metric", "Effect")
    xlab <- if (identical(kind, "deeks")) "1/sqrt(ESS)" else default.xlab
    ylab <- if (identical(kind, "deeks")) "Log diagnostic odds ratio" else "Standard error"
    limits <- .small.study.funnel.limits(params, index)
    list(
        kind=kind,
        point.size=as.numeric(value("funnel.point.size", value("point.size", 1))),
        point.symbol=as.integer(value("funnel.point.symbol", 19)),
        point.color=as.character(value("funnel.point.color", value("point.color", "black"))),
        reference.color=as.character(value("funnel.reference.color", "steelblue")),
        region.color=as.character(value("funnel.region.color", "grey90")),
        background.color=as.character(value("funnel.background.color", "white")),
        show.reference=isTRUE(value("funnel.reference.visible", TRUE)),
        show.regression=isTRUE(value("funnel.regression.visible", TRUE)),
        show.pooled=isTRUE(value("funnel.pooled.overlay.visible", TRUE)),
        show.region=isTRUE(value("funnel.sampling.region.visible", TRUE)),
        sampling.level=as.numeric(value("funnel.sampling.conf.level", value("conf.level", 95))),
        include.tau2=isTRUE(value("funnel.include.tau2", FALSE)),
        label.policy=as.character(value("funnel.label.policy", "none")),
        xlab=as.character(value("funnel.xlab", xlab)),
        ylab=as.character(value("funnel.ylab", ylab)),
        xlim=limits$xlim, at=limits$at)
}

.small.study.open.funnel.device <- function(path, background) {
    extension <- tolower(tools::file_ext(path))
    if (extension == "pdf")
        return(grDevices::pdf(path, width=1000/120, height=800/120, bg=background))
    if (extension == "svg")
        return(grDevices::svg(path, width=1000/120, height=800/120, bg=background))
    if (extension %in% c("tif", "tiff"))
        return(grDevices::tiff(path, width=1000, height=800, res=120,
                               compression="lzw", bg=background))
    grDevices::png(path, width=1000, height=800, res=120, bg=background)
}

.small.study.funnel.model <- function(res, y, se, keep) {
    if (inherits(res, "rma")) return(res)
    metafor::rma.uni(yi=y[keep], sei=se[keep], method="REML")
}

.small.study.funnel.args <- function(settings, center, ratio=FALSE) {
    args <- list(
        refline=if (settings$show.reference && settings$show.pooled) center else NULL,
        yaxis="sei", level=settings$sampling.level, addtau2=settings$include.tau2,
        xlab=settings$xlab, ylab=settings$ylab, atransf=if (ratio) exp else NULL,
        pch=settings$point.symbol, cex=settings$point.size, col=settings$point.color,
        bg=settings$point.color, back=settings$background.color,
        shade=if (settings$show.region) settings$region.color else NA,
        colref=settings$reference.color,
        colci=if (settings$show.region) settings$reference.color else NA,
        label=identical(settings$label.policy, "all"))
    if (!is.null(settings$xlim)) args$xlim <- settings$xlim
    if (!is.null(settings$at)) args$at <- settings$at
    args
}

.small.study.label.outside <- function(y, se, center, settings, labels) {
    if (!identical(settings$label.policy, "outside-pseudo-confidence-region")) return()
    outside <- abs(y-center) > stats::qnorm((1 + settings$sampling.level/100)/2) * se
    text(y[outside], se[outside], labels=labels[outside], pos=4, cex=.7)
}

.small.study.draw.deeks <- function(om.data, params, settings, y, se, keep) {
    effective <- as.numeric(params$deeks.ess %||% numeric())
    predictor <- as.numeric(params$deeks.predictor %||% numeric())
    if (length(effective) != sum(keep))
        stop("persisted Deeks effective sample sizes do not match prepared effects")
    plot(predictor, y[keep], xlab=settings$xlab, ylab=settings$ylab,
         xlim=settings$xlim, xaxt=if (is.null(settings$at)) "s" else "n",
         pch=settings$point.symbol, cex=settings$point.size,
         col=settings$point.color, bg=settings$point.color)
    if (!is.null(settings$at)) axis(1, at=settings$at)
    line <- as.numeric(params$deeks.line %||% c(NA_real_, NA_real_))
    if (settings$show.regression && length(line) == 2L && all(is.finite(line)))
        abline(a=line[[1L]], b=line[[2L]], col=settings$reference.color)
    if (settings$label.policy == "all")
        text(predictor, y[keep], labels=om.data@study.names[keep], pos=4, cex=.7)
}

.small.study.draw.standard.funnel <- function(om.data, res, params, settings,
                                              y, se, keep) {
    model <- .small.study.funnel.model(res, y, se, keep)
    center <- as.numeric(params$funnel.center %||% 0)
    ratio <- as.character(params$metric %||% "") %in% c("OR", "RR")
    do.call(metafor::funnel, c(list(model), .small.study.funnel.args(settings, center, ratio)))
    .small.study.label.outside(y, se, center, settings, om.data@study.names)
}

.small.study.draw.contour.funnel <- function(om.data, res, params, settings,
                                             y, se, keep) {
    model <- .small.study.funnel.model(res, y, se, keep)
    center <- as.numeric(params$funnel.center %||% 0)
    raw <- .small.study.plot.setting(params, "funnel.contour.levels",
                                     .small.study.funnel.index(params), "90,95,99")
    levels <- as.numeric(strsplit(as.character(raw), ",", fixed=TRUE)[[1L]])
    levels <- levels[is.finite(levels) & levels > 0 & levels < 100]
    if (!length(levels)) levels <- c(90, 95, 99)
    args <- .small.study.funnel.args(settings, center)
    args$refline <- if (settings$show.reference) 0 else NULL
    args$level <- levels
    args$atransf <- NULL
    args$shade <- settings$region.color
    args$colci <- settings$reference.color
    do.call(metafor::funnel, c(list(model), args))
    .small.study.label.outside(y, se, 0, settings, om.data@study.names)
    if (settings$show.pooled)
        abline(v=center, col=settings$reference.color, lwd=2, lty=2)
    legend("topright", legend=c(paste0(levels, "% null contours"),
                                 if (settings$show.pooled) "Pooled display"), bty="n")
}

rcmetar.regenerate.small.study.funnel <- function(om.data, res, params, output.path=NULL) {
    path <- output.path %||% tempfile(pattern="small-study-funnel-", fileext=".png")
    y <- om.data@y
    se <- om.data@SE
    keep <- is.finite(y) & is.finite(se) & se > 0
    settings <- .small.study.funnel.settings(params)
    .small.study.open.funnel.device(path, settings$background.color)
    on.exit(grDevices::dev.off(), add=TRUE)
    if (identical(settings$kind, "deeks") && is(om.data, "DiagnosticData"))
        .small.study.draw.deeks(om.data, params, settings, y, se, keep)
    else if (identical(settings$kind, "contour"))
        .small.study.draw.contour.funnel(om.data, res, params, settings, y, se, keep)
    else .small.study.draw.standard.funnel(om.data, res, params, settings, y, se, keep)
    path
}
