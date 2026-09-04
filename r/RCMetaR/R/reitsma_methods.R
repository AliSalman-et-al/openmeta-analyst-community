# SPDX-License-Identifier: GPL-3.0-or-later

# The Reitsma path deliberately stays small.  mada owns estimation and
# inference; this file only validates the count contract, converts FPR to the
# clinical specificity representation, and organizes public mada outputs.

rcmetar.reitsma.capture.warnings <- function(expr) {
    captured <- character()
    error <- NULL
    value <- tryCatch(withCallingHandlers(expr, warning=function(w) {
        captured <<- c(captured, conditionMessage(w))
        invokeRestart("muffleWarning")
    }), error=function(e) {
        error <<- conditionMessage(e)
        NULL
    })
    list(value=value, warnings=unique(captured), error=error)
}

rcmetar.reitsma.warning.messages <- function(capture, prefix=NULL) {
    messages <- character()
    if (!is.null(prefix) && length(prefix) && length(capture$warnings)) {
        messages <- c(messages, paste0(prefix, capture$warnings))
    } else {
        messages <- c(messages, capture$warnings)
    }
    if (!is.null(capture$error) && nzchar(capture$error)) {
        messages <- c(messages, if (is.null(prefix)) capture$error else paste0(prefix, capture$error))
    }
    messages[!is.na(messages) & nzchar(trimws(messages))]
}

rcmetar.reitsma.operation.messages <- function(capture, label) {
    state <- if (is.null(capture$value)) "unavailable" else "warning"
    rcmetar.reitsma.warning.messages(capture, paste0(label, " ", state, ": "))
}

rcmetar.reitsma.require.value <- function(capture, label) {
    if (!is.null(capture$value)) return(capture$value)
    detail <- capture$error %||% "mada returned no result"
    stop(sprintf("%s failed: %s", label, detail), call.=FALSE)
}

rcmetar.reitsma.correction.policies <- function() {
    c("Studies with any zero cell", "All studies if any zero exists", "None")
}

rcmetar.reitsma.correction.control <- function(policy) {
    policy <- as.character(policy %||% "All studies if any zero exists")
    switch(policy,
        "Studies with any zero cell"="single",
        "All studies if any zero exists"="all",
        "None"="none",
        stop(sprintf("Unknown Reitsma correction policy '%s'. Expected: %s.",
                     policy, paste(rcmetar.reitsma.correction.policies(), collapse=", ")), call.=FALSE))
}

rcmetar.reitsma.validate.counts <- function(diagnostic.data, min.studies=5L) {
    if (!is(diagnostic.data, "DiagnosticData")) stop("DiagnosticData object expected.", call.=FALSE)
    fields <- c("TP", "FN", "FP", "TN")
    vals <- lapply(fields, function(x) slot(diagnostic.data, x))
    names(vals) <- fields
    n <- length(diagnostic.data@study.names)
    if (n < 1L || any(vapply(vals, length, integer(1)) != n)) {
        stop("Reitsma requires complete TP/FN/FP/TN counts for every included study.", call.=FALSE)
    }
    valid <- vapply(vals, function(x) {
        all(is.finite(x)) && all(x >= 0) && all(x == floor(x))
    }, logical(1))
    if (!all(valid)) stop("Reitsma counts must be finite, non-negative integers.", call.=FALSE)
    if (any(vals$TP + vals$FN <= 0) || any(vals$FP + vals$TN <= 0)) {
        stop("Each Reitsma study must have positive diseased and non-diseased denominators.", call.=FALSE)
    }
    if (n < min.studies) stop(sprintf("Reitsma requires at least %d eligible studies; %d supplied.", min.studies, n), call.=FALSE)
    invisible(vals)
}

rcmetar.reitsma.fpr.to.specificity <- function(x) {
    if (is.null(x)) return(NULL)
    x <- as.numeric(x)
    if (length(x) == 0L) return(x)
    1 - x
}

rcmetar.reitsma.interval.to.specificity <- function(interval) {
    if (is.null(interval)) return(NULL)
    interval <- as.matrix(interval)
    if (ncol(interval) != 2L) return(interval)
    out <- cbind(1 - interval[, 2], 1 - interval[, 1])
    rownames(out) <- rownames(interval)
    colnames(out) <- colnames(interval)
    out
}

# Keep the FPR-to-specificity ordering in one place.  Both the operating
# point and marginal prediction intervals are reported as estimate/lower/upper
# on the clinical specificity scale.
rcmetar.reitsma.fpr.interval.to.specificity <- function(fpr) {
    if (is.null(fpr)) return(NULL)
    c(lower=1 - fpr[["upper"]], estimate=1 - fpr[["estimate"]],
      upper=1 - fpr[["lower"]])
}

rcmetar.reitsma.covariance.to.specificity <- function(covariance) {
    if (is.null(covariance)) return(NULL)
    covariance <- as.matrix(covariance)
    dimensions <- dim(covariance)
    if (length(dimensions) != 2L || !identical(as.integer(dimensions), c(2L, 2L))) return(covariance)
    sign <- diag(c(1, -1))
    out <- sign %*% covariance %*% sign
    dimnames(out) <- list(c("sensitivity", "specificity"), c("sensitivity", "specificity"))
    out
}

rcmetar.reitsma.marginal.prediction <- function(fit, level) {
    mu <- fit$coefficients["(Intercept)", ]
    covariance <- stats::vcov(fit)
    predictive.variance <- diag(fit$Psi + covariance)
    if (any(!is.finite(predictive.variance)) || any(predictive.variance < 0)) {
        stop("mada returned an undefined latent prediction variance.", call.=FALSE)
    }
    z <- qnorm(1 - (1 - level) / 2)
    interval <- function(index, alpha) {
        latent <- c(mu[[index]] - z * sqrt(predictive.variance[[index]]),
                    mu[[index]], mu[[index]] + z * sqrt(predictive.variance[[index]]))
        transformed <- mada::talpha(alpha)$linkinv(latent)
        c(lower=unname(transformed[[1]]), estimate=unname(transformed[[2]]), upper=unname(transformed[[3]]))
    }
    fpr <- interval(2L, fit$alphafpr)
    list(sensitivity=interval(1L, fit$alphasens),
         specificity=rcmetar.reitsma.fpr.interval.to.specificity(fpr),
         false.positive.rate=fpr,
         covariance=fit$Psi + covariance)
}

rcmetar.reitsma.summary.point <- function(fit, level) {
    coef <- fit$coefficients
    if (is.null(dim(coef)) || !all(c("tsens", "tfpr") %in% colnames(coef)))
        stop("mada Reitsma fit did not return intercept coefficients.", call.=FALSE)
    vc <- stats::vcov(fit)
    z <- qnorm(1 - (1 - level) / 2)
    to.proportion <- function(index, alpha) {
        latent.estimate <- coef["(Intercept)", index]
        vc.index <- if (index %in% rownames(vc)) index else grep(index, rownames(vc), fixed=TRUE)[1]
        if (is.na(vc.index)) stop("mada Reitsma fit did not return intercept covariance.", call.=FALSE)
        standard.error <- sqrt(vc[vc.index, vc.index])
        lower <- mada::talpha(alpha)$linkinv(latent.estimate - z * standard.error)
        estimate <- mada::talpha(alpha)$linkinv(latent.estimate)
        upper <- mada::talpha(alpha)$linkinv(latent.estimate + z * standard.error)
        c(estimate=estimate, lower=lower, upper=upper)
    }
    sens <- to.proportion("tsens", fit$alphasens)
    fpr <- to.proportion("tfpr", fit$alphafpr)
    list(
        sensitivity=sens,
        specificity=rcmetar.reitsma.fpr.interval.to.specificity(fpr),
        false.positive.rate=fpr
    )
}

rcmetar.reitsma.summary.points <- function(fit, level, seed, iterations=1000000L) {
    had.seed <- exists(".Random.seed", envir=.GlobalEnv, inherits=FALSE)
    old.seed <- if (had.seed) get(".Random.seed", envir=.GlobalEnv, inherits=FALSE) else NULL
    on.exit({
        if (had.seed) assign(".Random.seed", old.seed, envir=.GlobalEnv)
        else if (exists(".Random.seed", envir=.GlobalEnv, inherits=FALSE)) rm(".Random.seed", envir=.GlobalEnv)
    }, add=TRUE)
    set.seed(as.integer(seed))
    draws <- mada::SummaryPts(fit, n.iter=as.integer(iterations))
    values <- summary(draws, level=level, digits=16)
    values
}

rcmetar.reitsma.validate.fit <- function(fit, context="Reitsma") {
    if (!isTRUE(fit$converged)) stop(sprintf("%s fit did not converge; no alternate estimator or correction was attempted.", context), call.=FALSE)
    required <- c("coefficients", "vcov", "Psi", "logLik")
    if (any(!required %in% names(fit))) stop(sprintf("%s fit is missing required mada output fields.", context), call.=FALSE)
    finite.matrix <- function(x) is.matrix(x) && length(x) > 0L && all(is.finite(x))
    if (!finite.matrix(fit$coefficients) || !finite.matrix(fit$vcov) || !finite.matrix(fit$Psi) || !is.finite(as.numeric(fit$logLik)))
        stop(sprintf("%s fit returned non-finite fixed effects, covariance, heterogeneity, or log likelihood.", context), call.=FALSE)
    scale <- max(1, max(abs(fit$Psi)), max(abs(fit$vcov)))
    tolerance <- 100 * .Machine$double.eps * scale
    if (any(diag(fit$Psi) < -tolerance) || any(diag(fit$vcov) < -tolerance))
        stop(sprintf("%s fit returned a materially invalid covariance diagonal.", context), call.=FALSE)
    if (!is.null(fit$rank) && !isTRUE(as.integer(fit$rank) > 0L))
        stop(sprintf("%s fit did not retain a full-rank fixed-effect solution.", context), call.=FALSE)
    invisible(fit)
}

rcmetar.reitsma.estimator <- function(params) {
    explicit <- !is.null(params$estimator) || !is.null(params$method)
    candidate <- params$estimator %||% params$method %||% params$rm.method %||% "REML"
    method <- tolower(as.character(candidate[[1L]]))
    if (method %in% c("reml", "ml")) return(method)
    # Generic meta-regression parameters commonly carry rm.method="DL".
    # Reitsma has its own estimator contract, so an absent Reitsma-specific
    # estimator means the documented REML default rather than a hard failure.
    if (!explicit) return("reml")
    stop("Reitsma estimator must be REML or ML.", call.=FALSE)
}

rcmetar.reitsma.formula <- function(terms) {
    terms <- as.character(terms)
    if (!length(terms) || any(!nzchar(terms))) stop("At least one Reitsma moderator is required.", call.=FALSE)
    quoted <- paste0("`", gsub("`", "``", terms, fixed=TRUE), "`")
    stats::reformulate(quoted, response="cbind(tsens, tfpr)")
}

rcmetar.reitsma.restore.coefficient.labels <- function(coefficients, coding) {
    if (is.null(coefficients) || !nrow(coefficients) || !length(coding)) return(coefficients)
    labels <- rownames(coefficients)
    for (name in names(coding)) {
        model.name <- as.character(coding[[name]]$model.name %||% name)
        for (prefix in c("tsens.", "tfpr.")) {
            token <- paste0(prefix, model.name)
            hit <- startsWith(labels, token)
            labels[hit] <- paste0(prefix, name,
                substring(labels[hit], nchar(token) + 1L))
        }
    }
    rownames(coefficients) <- labels
    coefficients
}

rcmetar.reitsma.display.number <- function(value, digits=3L) {
    value <- suppressWarnings(as.numeric(value))
    if (length(value) != 1L || !is.finite(value)) return("Not estimable")
    sprintf(paste0("%.", as.integer(digits), "f"), value)
}

rcmetar.reitsma.display.percent <- function(value, digits=1L) {
    value <- suppressWarnings(as.numeric(value))
    if (length(value) != 1L || !is.finite(value)) return("Not estimable")
    sprintf(paste0("%.", as.integer(digits), "f%%"), 100 * value)
}

rcmetar.reitsma.display.level <- function(level) {
    trimws(formatC(100 * as.numeric(level), format="fg", digits=4))
}

rcmetar.reitsma.display.interval <- function(interval, level, kind="CI", digits=1L) {
    labels <- c(
        "Estimate",
        paste0("Lower bound (", rcmetar.reitsma.display.level(level), "% ", kind, ")"),
        paste0("Upper bound (", rcmetar.reitsma.display.level(level), "% ", kind, ")")
    )
    values <- c(interval[["estimate"]], interval[["lower"]], interval[["upper"]])
    stats::setNames(vapply(values, rcmetar.reitsma.display.percent, character(1), digits=digits), labels)
}

rcmetar.reitsma.display.ratios <- function(ratios, level, digits=3L) {
    if (is.null(ratios) || !length(ratios)) return(NULL)
    ratios <- as.matrix(ratios)
    if (ncol(ratios) < 4L) return(NULL)
    ratio.names <- c(
        posLR="Positive likelihood ratio",
        negLR="Negative likelihood ratio",
        invnegLR="Inverse negative likelihood ratio",
        DOR="Diagnostic odds ratio"
    )
    rows <- intersect(names(ratio.names), rownames(ratios))
    if (!length(rows)) rows <- rownames(ratios)
    display <- data.frame(
        Mean=vapply(ratios[rows, 1L], rcmetar.reitsma.display.number, character(1), digits=digits),
        Median=vapply(ratios[rows, 2L], rcmetar.reitsma.display.number, character(1), digits=digits),
        check.names=FALSE,
        row.names=unname(ratio.names[rows])
    )
    names(display) <- c("Mean", "Median")
    lower.label <- paste0("Lower bound (", rcmetar.reitsma.display.level(level), "% interval)")
    upper.label <- paste0("Upper bound (", rcmetar.reitsma.display.level(level), "% interval)")
    display[[lower.label]] <- vapply(ratios[rows, 3L], rcmetar.reitsma.display.number, character(1), digits=digits)
    display[[upper.label]] <- vapply(ratios[rows, 4L], rcmetar.reitsma.display.number, character(1), digits=digits)
    display
}

rcmetar.reitsma.display.i2 <- function(i2, digits=1L) {
    if (is.null(i2)) return(NULL)
    values <- c(
        "Zhou-Dendukuri"=if (is.data.frame(i2)) i2[["Zhou"]] else i2[["Zhou"]],
        "Holling (unadjusted), method 1"=if (is.data.frame(i2)) i2[["HollingUnadjusted1"]] else NA_real_,
        "Holling (unadjusted), method 2"=if (is.data.frame(i2)) i2[["HollingUnadjusted2"]] else NA_real_,
        "Holling (unadjusted), method 3"=if (is.data.frame(i2)) i2[["HollingUnadjusted3"]] else NA_real_,
        "Holling (adjusted), method 1"=if (is.data.frame(i2)) i2[["HollingAdjusted1"]] else NA_real_,
        "Holling (adjusted), method 2"=if (is.data.frame(i2)) i2[["HollingAdjusted2"]] else NA_real_,
        "Holling (adjusted), method 3"=if (is.data.frame(i2)) i2[["HollingAdjusted3"]] else NA_real_
    )
    data.frame(
        Measure=names(values),
        `I-squared (%)`=vapply(values, rcmetar.reitsma.display.percent, character(1), digits=digits),
        check.names=FALSE,
        row.names=NULL
    )
}

rcmetar.reitsma.display.i2.summary <- function(i2, digits=1L) {
    if (is.null(i2)) return(NULL)
    values <- if (is.data.frame(i2)) unlist(i2[1L, c("Zhou", "HollingUnadjusted1", "HollingUnadjusted2", "HollingUnadjusted3", "HollingAdjusted1", "HollingAdjusted2", "HollingAdjusted3")], use.names=FALSE) else numeric()
    if (length(values) != 7L || any(!is.finite(values))) return(NULL)
    list(
        `Zhou-Dendukuri`=rcmetar.reitsma.display.percent(values[[1L]], digits),
        `Holling unadjusted range`=paste(rcmetar.reitsma.display.percent(min(values[2:4]), digits), "to", rcmetar.reitsma.display.percent(max(values[2:4]), digits)),
        `Holling adjusted range`=paste(rcmetar.reitsma.display.percent(min(values[5:7]), digits), "to", rcmetar.reitsma.display.percent(max(values[5:7]), digits))
    )
}

rcmetar.reitsma.coefficient.table <- function(coefficients, specificity=FALSE) {
    if (is.null(coefficients) || !nrow(coefficients)) return(coefficients)
    out <- coefficients
    out <- out[!grepl("Intercept", rownames(out), fixed=TRUE),,drop=FALSE]
    if (!nrow(out)) return(out)
    ci.cols <- grep("%ci", colnames(out), value=TRUE)
    if (isTRUE(specificity)) {
        out[, c("Estimate", "z", ci.cols)] <- -out[, c("Estimate", "z", ci.cols), drop=FALSE]
        out[, ci.cols] <- out[, rev(ci.cols), drop=FALSE]
    }
    lower <- out[, ci.cols[[1]]]
    upper <- out[, ci.cols[[length(ci.cols)]]]
    out <- cbind(out, `Odds Ratio`=exp(out[, "Estimate"]),
                 `Odds Ratio lower`=exp(lower), `Odds Ratio upper`=exp(upper))
    out
}

rcmetar.reitsma.add.reference.rows <- function(coefficients, coding) {
    factors <- coding[vapply(coding, function(x) identical(x$type, "factor"), logical(1))]
    if (!length(factors) || is.null(coefficients) || !nrow(coefficients)) return(coefficients)
    template <- coefficients[1,,drop=FALSE]
    rows <- lapply(names(factors), function(name) {
        row <- template
        row[] <- 0
        if ("Pr(>|z|)" %in% colnames(row)) row[, "Pr(>|z|)"] <- 1
        if ("Odds Ratio" %in% colnames(row)) row[, "Odds Ratio"] <- 1
        if ("Odds Ratio lower" %in% colnames(row)) row[, "Odds Ratio lower"] <- 1
        if ("Odds Ratio upper" %in% colnames(row)) row[, "Odds Ratio upper"] <- 1
        rownames(row) <- sprintf("%s = %s (reference)", name, factors[[name]]$reference)
        row
    })
    do.call(rbind, c(list(coefficients), rows))
}

rcmetar.reitsma.plot.data <- function(fit, diagnostic.data, level, extrapolate=FALSE, params=list()) {
    fpr <- fit$freqdata$FP / (fit$freqdata$FP + fit$freqdata$TN)
    bounds <- if (isTRUE(extrapolate)) c(0, 1) else range(fpr)
    geometry.warnings <- character()
    curve.capture <- rcmetar.reitsma.capture.warnings(mada::sroc(
        fit, fpr=seq(bounds[[1]], bounds[[2]], length.out=201)))
    curve <- curve.capture$value
    geometry.warnings <- c(geometry.warnings,
        rcmetar.reitsma.operation.messages(curve.capture, "SROC curve"))
    confidence.capture <- rcmetar.reitsma.capture.warnings(mada::ROCellipse(
        fit, level=level, add=FALSE))
    confidence <- confidence.capture$value
    geometry.warnings <- c(geometry.warnings,
        rcmetar.reitsma.operation.messages(confidence.capture, "Confidence region"))
    prediction.capture <- rcmetar.reitsma.capture.warnings({
        mu <- fit$coefficients["(Intercept)",]
        Sigma <- fit$Psi + stats::vcov(fit)
        ell <- ellipse::ellipse(Sigma, centre=mu, level=level)
        cbind(mada::talpha(fit$alphafpr)$linkinv(ell[,2]), mada::talpha(fit$alphasens)$linkinv(ell[,1]))
    })
    prediction <- prediction.capture$value
    geometry.warnings <- c(geometry.warnings,
        rcmetar.reitsma.operation.messages(prediction.capture, "Joint prediction region"))
    auc.capture <- rcmetar.reitsma.capture.warnings(unclass(mada::AUC(fit)))
    auc <- auc.capture$value
    geometry.warnings <- c(geometry.warnings,
        rcmetar.reitsma.operation.messages(auc.capture, "SROC AUC"))
    style <- list(
        curve.color=as.character(params$fp_curve_color %||% params$fp_accent_color %||% "#2f5597"),
        confidence.color=as.character(params$fp_confidence_color %||% "#2f5597"),
        prediction.color=as.character(params$fp_prediction_color %||% "#b45f06"),
        # The accent is intentionally separate from curve-specific colors.
        # It styles observed-study markers and the summary point, so the
        # shared appearance/preset control remains visibly useful without
        # silently overriding a researcher's curve palette.
        accent.color=as.character(params$fp_accent_color %||% "#2f5597"),
        point.size.multiplier=as.numeric(params$fp_point_size_multiplier %||% 1),
        digits=as.integer(params$digits %||% 3),
        show.confidence=isTRUE(params$fp_show_confidence %||% TRUE),
        show.prediction=isTRUE(params$fp_show_prediction %||% TRUE),
        show.summary=isTRUE(params$fp_show_summary %||% TRUE),
        show.auc=isTRUE(params$fp_show_auc %||% TRUE),
        point.area.by.sample.size=isTRUE(params$fp_point_area_by_sample_size %||% FALSE),
        # Keep the curve legend on by default so confidence and prediction
        # regions remain distinguishable in a static export. Marker-size
        # legend state is independent from the curve legend.
        show.legend=isTRUE(params$fp_show_legend %||% TRUE),
        show.marker.legend={
            marker.scaled <- identical(as.character(params$fp_marker_area %||% "uniform"), "sample-size") ||
                isTRUE(params$fp_point_area_by_sample_size %||% FALSE)
            if (!is.null(params$fp_show_marker_legend)) {
                isTRUE(params$fp_show_marker_legend)
            } else marker.scaled
        },
        marker.area=as.character(params$fp_marker_area %||% "uniform"),
        xlabel=if (rcmetar.is.plot.default.text(params$fp_xlabel)) "False Positive Rate" else as.character(params$fp_xlabel),
        ylabel=as.character(params$fp_ylabel %||% "Sensitivity"),
        plot.lb=as.character(params$fp_plot_lb %||% "[default]"),
        plot.ub=as.character(params$fp_plot_ub %||% "[default]"),
        xticks=params$fp_xticks %||% "[default]",
        y.plot.lb=as.character(params$fp_sroc_plot_lb %||% "[default]"),
        y.plot.ub=as.character(params$fp_sroc_plot_ub %||% "[default]"),
        yticks=params$fp_sroc_yticks %||% "[default]",
        curve.lty=as.integer(params$fp_curve_lty %||% 1),
        confidence.lty=as.integer(params$fp_confidence_lty %||% 2),
        prediction.lty=as.integer(params$fp_prediction_lty %||% 3),
        text.cex=as.numeric(params$fp_text_cex %||% 0.8),
        point.pch=as.integer(params$fp_point_pch %||% 21),
        show.labels=isTRUE(params$fp_show_labels %||% FALSE))
    marginal.capture <- rcmetar.reitsma.capture.warnings(
        rcmetar.reitsma.marginal.prediction(fit, level))
    marginal.prediction <- marginal.capture$value
    geometry.warnings <- c(geometry.warnings,
        rcmetar.reitsma.operation.messages(marginal.capture, "Marginal prediction intervals"))
    list(kind="sroc", fpr=fpr, sensitivity=fit$freqdata$TP/(fit$freqdata$TP+fit$freqdata$FN),
         sample.size=fit$freqdata$TP + fit$freqdata$FN + fit$freqdata$FP + fit$freqdata$TN,
         study.names=diagnostic.data@study.names, curve=curve,
         style=style,
         legend=rcmetar.reitsma.legend.spec(style, curve, confidence, prediction,
                                             fit$freqdata$TP + fit$freqdata$FN + fit$freqdata$FP + fit$freqdata$TN),
         display.path=rcmetar.plot.scalar_path(params$fp_display_path),
         confidence.region=if (is.null(confidence)) NULL else confidence$ROCellipse,
         prediction.region=prediction, marginal.prediction=marginal.prediction,
         prediction.covariance=if (is.null(marginal.prediction)) NULL else marginal.prediction$covariance,
         summary.point=rcmetar.reitsma.summary.point(fit, level),
         fpr.bounds=range(fpr), curve.bounds=bounds,
         auc=auc, warnings=unique(geometry.warnings))
}

rcmetar.reitsma.legend.spec <- function(style, curve, confidence, prediction, sample.size) {
    scalar.bool <- function(x, default) if (is.null(x)) default else isTRUE(x)
    labels <- character(); colors <- character(); ltys <- numeric(); pchs <- numeric()
    pt.cex <- numeric(); pt.bg <- character()
    add.line <- function(label, color, lty) {
        labels <<- c(labels, label); colors <<- c(colors, color); ltys <<- c(ltys, lty)
        pchs <<- c(pchs, NA_real_); pt.cex <<- c(pt.cex, 1); pt.bg <<- c(pt.bg, NA_character_)
    }
    if (scalar.bool(style$show.legend, FALSE)) {
        if (!is.null(curve)) add.line("SROC", as.character(style$curve.color %||% "#2f5597"), as.numeric(style$curve.lty %||% 1))
        if (scalar.bool(style$show.confidence, TRUE) && !is.null(confidence))
            add.line("Confidence region", as.character(style$confidence.color %||% style$curve.color %||% "#2f5597"), as.numeric(style$confidence.lty %||% 2))
        if (scalar.bool(style$show.prediction, TRUE) && !is.null(prediction))
            add.line("Joint prediction region", as.character(style$prediction.color %||% "#b45f06"), as.numeric(style$prediction.lty %||% 3))
    }
    marker.scaled <- identical(as.character(style$marker.area %||% "uniform"), "sample-size") ||
        scalar.bool(style$point.area.by.sample.size, FALSE)
    if (marker.scaled && scalar.bool(style$show.marker.legend, FALSE) &&
            length(sample.size) && all(is.finite(sample.size))) {
        values <- sort(unique(range(sample.size)))
        values <- if (length(values) == 1L) values else values[c(1L, length(values))]
        multiplier <- as.numeric(style$point.size.multiplier %||% 1)
        if (!is.finite(multiplier) || multiplier <= 0) multiplier <- 1
        mean.size <- mean(sample.size)
        for (value in values) {
            labels <- c(labels, sprintf("Study sample size (n=%g)", value))
            colors <- c(colors, "grey35"); ltys <- c(ltys, 0); pchs <- c(pchs, as.numeric(style$point.pch %||% 21))
            pt.cex <- c(pt.cex, multiplier * sqrt(value / mean.size)); pt.bg <- c(pt.bg, "white")
        }
    }
    list(labels=labels, col=colors, lty=ltys, pch=pchs, pt.cex=pt.cex, pt.bg=pt.bg)
}

rcmetar.reitsma.draw <- function(plot.data, outpath) {
    size <- list(width=7, height=6, dpi=300, bg="white")
    style <- plot.data$style
    if (is.null(style)) style <- list()
    scalar.bool <- function(x, default) if (is.null(x)) default else isTRUE(x)
    curve.color <- as.character(style$curve.color %||% "#2f5597")
    confidence.color <- as.character(style$confidence.color %||% curve.color)
    prediction.color <- as.character(style$prediction.color %||% "#b45f06")
    accent.color <- as.character(style$accent.color %||% "#2f5597")
    size.multiplier <- as.numeric(style$point.size.multiplier %||% 1)
    if (!is.finite(size.multiplier) || size.multiplier <= 0) size.multiplier <- 1
    scalar.number <- function(value, fallback) {
        parsed <- suppressWarnings(as.numeric(value))
        if (length(parsed) != 1L || !is.finite(parsed)) fallback else parsed
    }
    axis.limits <- function(lower, upper, fallback) {
        lower.value <- if (length(lower)) lower[[1L]] else "[default]"
        upper.value <- if (length(upper)) upper[[1L]] else "[default]"
        lo <- if (identical(as.character(lower.value), "[default]")) fallback[[1L]] else scalar.number(lower, fallback[[1L]])
        hi <- if (identical(as.character(upper.value), "[default]")) fallback[[2L]] else scalar.number(upper, fallback[[2L]])
        limits <- sort(c(lo, hi))
        if (length(limits) != 2L || !all(is.finite(limits)) || diff(limits) <= 0) fallback else limits
    }
    axis.ticks <- function(value, limits) {
        if (is.null(value) || !length(value) || identical(as.character(value[[1L]]), "[default]")) return(pretty(limits))
        parsed <- rcmetar.numeric.values(value)
        parsed <- as.numeric(parsed)
        parsed[is.finite(parsed) & parsed >= limits[[1L]] & parsed <= limits[[2L]]]
    }
    xlim <- axis.limits(style$plot.lb %||% "[default]", style$plot.ub %||% "[default]", c(0, 1))
    ylim <- axis.limits(style$y.plot.lb %||% "[default]", style$y.plot.ub %||% "[default]", c(0, 1))
    draw <- function() {
        plot(plot.data$fpr, plot.data$sensitivity, xlim=xlim, ylim=ylim, xaxt="n", yaxt="n",
             xlab=as.character(style$xlabel %||% "False Positive Rate"),
             ylab=as.character(style$ylabel %||% "Sensitivity"), pch=as.integer(style$point.pch %||% 21), bg="white",
             col=accent.color,
             cex=size.multiplier * if (identical(style$marker.area, "sample-size") || scalar.bool(style$point.area.by.sample.size, FALSE))
                 sqrt(plot.data$sample.size / mean(plot.data$sample.size)) else 1)
        axis(1, at=axis.ticks(style$xticks %||% "[default]", xlim))
        axis(2, at=axis.ticks(style$yticks %||% "[default]", ylim))
        if (!is.null(plot.data$curve)) lines(plot.data$curve[,1], plot.data$curve[,2], lwd=2, col=curve.color, lty=as.integer(style$curve.lty %||% 1))
        if (scalar.bool(style$show.confidence, TRUE) && !is.null(plot.data$confidence.region)) lines(plot.data$confidence.region, col=confidence.color, lty=as.integer(style$confidence.lty %||% 2))
        if (scalar.bool(style$show.prediction, TRUE) && !is.null(plot.data$prediction.region)) lines(plot.data$prediction.region, col=prediction.color, lty=as.integer(style$prediction.lty %||% 3))
        point <- plot.data$summary.point
        if (scalar.bool(style$show.summary, TRUE)) points(1 - point$specificity[["estimate"]], point$sensitivity[["estimate"]], pch=19, col=accent.color)
        if (scalar.bool(style$show.labels, FALSE)) text(plot.data$fpr, plot.data$sensitivity, labels=plot.data$study.names, pos=4, cex=as.numeric(style$text.cex %||% .8))
        if (scalar.bool(style$show.auc, TRUE) && !is.null(plot.data$auc$pAUC)) {
            digits <- as.integer(style$digits %||% 3L)
            if (length(digits) != 1L || is.na(digits) || digits < 0L || digits > 15L) digits <- 3L
            mtext(sprintf(paste0("Normalized partial SROC AUC: %.", digits, "f"), plot.data$auc$pAUC),
                  side=3, line=.3, cex=as.numeric(style$text.cex %||% .8))
        }
        legend.spec <- plot.data$legend %||% rcmetar.reitsma.legend.spec(
            style, plot.data$curve, plot.data$confidence.region, plot.data$prediction.region,
            plot.data$sample.size
        )
        if (length(legend.spec$labels)) {
            graphics::legend("bottomright", legend=legend.spec$labels, col=legend.spec$col,
                             lty=legend.spec$lty, pch=legend.spec$pch,
                             pt.cex=legend.spec$pt.cex, pt.bg=legend.spec$pt.bg, bty="n")
        }
    }
    dir.create(dirname(outpath), recursive=TRUE, showWarnings=FALSE)
    rcmetar.render.plot_file(outpath, size, draw, display.path=plot.data$display.path)
    invisible(outpath)
}

rcmetar.reitsma.apply.saved.style <- function(plot.data, params) {
    # Re-rendering is deliberately geometry-preserving: mutable presentation
    # controls are overlaid onto the captured SROC bundle, never re-extracted
    # from the fitted model.
    style <- plot.data$style %||% list()
    fields <- c(curve.color="fp_curve_color", confidence.color="fp_confidence_color",
        prediction.color="fp_prediction_color", accent.color="fp_accent_color",
        point.size.multiplier="fp_point_size_multiplier", show.confidence="fp_show_confidence",
        show.prediction="fp_show_prediction", show.summary="fp_show_summary", show.auc="fp_show_auc",
        point.area.by.sample.size="fp_point_area_by_sample_size", show.legend="fp_show_legend",
        show.marker.legend="fp_show_marker_legend", marker.area="fp_marker_area", xlabel="fp_xlabel",
        ylabel="fp_ylabel", plot.lb="fp_plot_lb", plot.ub="fp_plot_ub", xticks="fp_xticks",
        y.plot.lb="fp_sroc_plot_lb", y.plot.ub="fp_sroc_plot_ub", yticks="fp_sroc_yticks",
        curve.lty="fp_curve_lty", confidence.lty="fp_confidence_lty", prediction.lty="fp_prediction_lty",
        text.cex="fp_text_cex", point.pch="fp_point_pch", show.labels="fp_show_labels")
    for (field in names(fields)) {
        value <- params[[fields[[field]]]]
        if (!is.null(value) && length(value)) style[[field]] <- value
    }
    plot.data$style <- style
    plot.data$display.path <- rcmetar.plot.scalar_path(params$fp_display_path %||% plot.data$display.path)
    plot.data$legend <- NULL
    plot.data
}

rcmetar.reitsma.coefficient.bundle <- function(coefficients, scale, params=list()) {
    if (is.null(coefficients) || !nrow(coefficients)) stop(sprintf("No %s moderator coefficients were returned by mada.", scale), call.=FALSE)
    list(kind="forest", render_engine="reitsma.coefficient", fp_style="default",
         scale=scale, labels=rownames(coefficients), estimate=coefficients[, "Odds Ratio"],
         ci.lb=coefficients[, "Odds Ratio lower"], ci.ub=coefficients[, "Odds Ratio upper"],
         params=params)
}

rcmetar.is.reitsma.coefficient.bundle <- function(plot.data) {
    is.list(plot.data) && identical(plot.data$render_engine, "reitsma.coefficient")
}

rcmetar.draw.reitsma.coefficient <- function(plot.data, outpath) {
    style <- plot.data$params
    color <- rcmetar.forest.accent.color(style)
    multiplier <- as.numeric(style$fp_point_size_multiplier %||% 1)
    if (!is.finite(multiplier) || multiplier <= 0) multiplier <- 1
    scalar.number <- function(value) {
        parsed <- suppressWarnings(as.numeric(value))
        if (length(parsed) != 1L || !is.finite(parsed)) return(NULL)
        parsed
    }
    bound <- function(value, fallback) {
        parsed <- scalar.number(value)
        if (is.null(parsed)) fallback else parsed
    }
    tick.values <- function(value, limits) {
        if (is.null(value) || !length(value) || identical(as.character(value[[1L]]), "[default]")) {
            return(pretty(limits))
        }
        parsed <- rcmetar.numeric.values(value)
        parsed <- as.numeric(parsed)
        parsed[is.finite(parsed) & parsed >= limits[[1L]] & parsed <= limits[[2L]]]
    }
    draw <- function() {
        labels <- as.character(plot.data$labels)
        y <- seq_along(labels)
        xlim <- range(c(plot.data$ci.lb, plot.data$ci.ub, 1), finite=TRUE)
        xlim <- sort(c(bound(style$fp_plot_lb, xlim[[1L]]), bound(style$fp_plot_ub, xlim[[2L]])))
        if (diff(xlim) <= 0) xlim <- xlim + c(-.5, .5)
        xlab <- style$fp_xlabel
        if (is.null(xlab) || !length(xlab) || is.na(xlab[[1L]]) || identical(as.character(xlab[[1L]]), "[default]")) {
            xlab <- "Odds ratio"
        }
        show.annotation <- rcmetar.param.is.true(style, "fp_show_annotation", TRUE)
        plot(plot.data$estimate, y, xlim=xlim, yaxt="n", xaxt="n", ylab="",
             xlab=if (show.annotation) as.character(xlab[[1L]]) else "",
             pch=19, col=color, cex=multiplier)
        axis(2, at=y, labels=labels, las=2)
        x_ticks <- tick.values(style$fp_xticks, xlim)
        if (length(x_ticks)) {
            digits <- suppressWarnings(as.integer(style$digits %||% 3L))
            if (length(digits) != 1L || is.na(digits) || digits < 0L || digits > 15L) digits <- 3L
            axis(1, at=x_ticks, labels=vapply(x_ticks, rcmetar.reitsma.display.number, character(1), digits=digits))
        }
        segments(plot.data$ci.lb, y, plot.data$ci.ub, y, col=color)
        abline(v=1, lty=2, col="grey50")
        title(main=sprintf("%s moderator coefficients", plot.data$scale))
    }
    dir.create(dirname(outpath), recursive=TRUE, showWarnings=FALSE)
    rcmetar.render.plot_file(outpath, list(width=7, height=5, dpi=300, bg="white"), draw)
    invisible(outpath)
}

rcmetar.reitsma.prepare <- function(diagnostic.data, params) {
    params <- .rcmetar.as.params.list(params)
    level <- as.numeric(params$conf.level %||% 95) / 100
    validate.conf.level(level * 100)
    digits <- suppressWarnings(as.integer(params$digits %||% 3L))
    if (length(digits) != 1L || is.na(digits) || digits < 0L || digits > 15L) digits <- 3L
    method <- rcmetar.reitsma.estimator(params)
    adjust <- as.numeric(params$adjust %||% 0.5)
    if (!is.finite(adjust) || adjust < 0) stop("Reitsma correction factor must be finite and non-negative.", call.=FALSE)
    policy <- as.character(params$correction.policy %||% "All studies if any zero exists")
    control <- rcmetar.reitsma.correction.control(policy)
    counts <- rcmetar.reitsma.validate.counts(diagnostic.data)
    if (control == "none" && any(counts$TP == 0 | counts$FN == 0 | counts$FP == 0 | counts$TN == 0))
        stop("Correction policy None cannot fit boundary proportions; choose a correction factor and policy.", call.=FALSE)
    list(data=diagnostic.data, params=params, level=level, digits=digits,
         method=method, adjust=adjust, policy=policy, control=control, counts=counts)
}

rcmetar.reitsma.fit <- function(prepared) {
    fit.capture <- rcmetar.reitsma.capture.warnings(mada::reitsma(
        data=data.frame(TP=prepared$counts$TP, FN=prepared$counts$FN,
                        FP=prepared$counts$FP, TN=prepared$counts$TN),
        correction=prepared$adjust, correction.control=prepared$control,
        method=prepared$method))
    fit <- rcmetar.reitsma.require.value(fit.capture, "Reitsma fit")
    rcmetar.reitsma.validate.fit(fit)
    list(fit=fit, warnings=rcmetar.reitsma.warning.messages(fit.capture, "Reitsma fit: "),
         capture=fit.capture)
}

rcmetar.reitsma.render.standard <- function(plot.data, diagnostic.data, fit, params) {
    empty <- list(images=character(), paths=character(), capabilities=list(), warnings=character())
    if (!isTRUE(params$create.plot %||% TRUE) || is.null(plot.data)) return(empty)
    path <- as.character(params$fp_outpath %||% params$roc_outpath %||% params$sroc_outpath %||% "./r_tmp/reitsma_sroc.svg")
    capture <- rcmetar.reitsma.capture.warnings(rcmetar.reitsma.draw(plot.data, path))
    warnings <- rcmetar.reitsma.operation.messages(capture, "SROC plot")
    if (is.null(capture$value)) {
        empty$warnings <- warnings
        return(empty)
    }
    params$fp_outpath <- path
    params$reitsma.sroc.geometry <- plot.data
    saved <- save.data(diagnostic.data, fit, params, plot.data)
    list(images=c(SROC=path), paths=c(SROC=saved),
         capabilities=list(SROC=.rcmetar.plot.descriptor.for.kind("sroc", has.params=TRUE)),
         warnings=warnings)
}

diagnostic.reitsma <- function(diagnostic.data, params) {
    if (!requireNamespace("mada", quietly=TRUE)) stop("Reitsma requires mada 0.5.12. Install the pinned package before running this analysis.", call.=FALSE)
    if (as.character(packageVersion("mada")) != "0.5.12") stop(sprintf("Reitsma requires mada 0.5.12; loaded %s.", packageVersion("mada")), call.=FALSE)
    prepared <- rcmetar.reitsma.prepare(diagnostic.data, params)
    params <- prepared$params
    level <- prepared$level
    digits <- prepared$digits
    method <- prepared$method
    adjust <- prepared$adjust
    policy <- prepared$policy
    control <- prepared$control
    counts <- prepared$counts
    fitted <- rcmetar.reitsma.fit(prepared)
    fit.capture <- fitted$capture
    fit.warnings <- fitted$warnings
    fit <- fitted$fit
    section.warnings <- character()
    summary.capture <- rcmetar.reitsma.capture.warnings(summary(fit, level=level))
    # A converged fit remains authoritative when an optional extractor fails.
    # Keep every independently available result instead of replacing it with
    # an estimator fallback or failing the entire report.
    sm <- summary.capture$value
    summary.warnings <- rcmetar.reitsma.warning.messages(summary.capture, "mada summary: ")
    if (!is.null(summary.capture$error)) section.warnings <- c(section.warnings, paste("mada summary unavailable:", summary.capture$error))
    point.capture <- rcmetar.reitsma.capture.warnings(rcmetar.reitsma.summary.point(fit, level))
    point <- point.capture$value
    section.warnings <- c(section.warnings,
        rcmetar.reitsma.operation.messages(point.capture, "Summary operating point"))
    # Keep mada's sampling-based ratios reproducible without exposing an RNG
    # control as an analysis parameter or a user-facing result.
    summary.seed <- 380381L
    summary.iterations <- 1000000L
    summary.points.capture <- rcmetar.reitsma.capture.warnings(
        rcmetar.reitsma.summary.points(fit, level, summary.seed, summary.iterations))
    summary.warnings <- c(summary.warnings,
        rcmetar.reitsma.warning.messages(summary.points.capture, "SummaryPts: "))
    ratios <- summary.points.capture$value
    if (is.null(ratios)) section.warnings <- c(section.warnings,
        paste("Sampling-based summary ratios unavailable:", summary.points.capture$error %||% "unknown error"))
    auc.capture <- rcmetar.reitsma.capture.warnings(unclass(mada::AUC(fit)))
    auc <- auc.capture$value
    section.warnings <- c(section.warnings,
        rcmetar.reitsma.operation.messages(auc.capture, "SROC AUC"))
    plot.capture <- rcmetar.reitsma.capture.warnings(rcmetar.reitsma.plot.data(
        fit, diagnostic.data, level,
        extrapolate=isTRUE(params$fp_extrapolate %||% params$sroc_extrapolate %||% FALSE),
        params=params))
    plot.data <- plot.capture$value
    section.warnings <- c(section.warnings,
        rcmetar.reitsma.operation.messages(plot.capture, "SROC-derived geometry"))
    if (!is.null(plot.data$warnings)) section.warnings <- c(section.warnings, plot.data$warnings)
    rendered <- rcmetar.reitsma.render.standard(plot.data, diagnostic.data, fit, params)
    images <- rendered$images
    plot.paths <- rendered$paths
    capabilities <- rendered$capabilities
    section.warnings <- c(section.warnings, rendered$warnings)
    # mada's full AUC uses .01 through .99, while its normalized partial AUC
    # uses the observed FPR range clipped to those same endpoints.
    observed.fpr <- fit$freqdata$FP / (fit$freqdata$FP + fit$freqdata$TN)
    pauc.bounds <- range(observed.fpr)
    pauc.bounds[[1L]] <- max(0.01, pauc.bounds[[1L]])
    pauc.bounds[[2L]] <- min(0.99, pauc.bounds[[2L]])
    i2 <- if (is.null(sm)) NULL else sm$i2
    marginal.capture <- rcmetar.reitsma.capture.warnings(
        rcmetar.reitsma.marginal.prediction(fit, level))
    marginal.prediction <- marginal.capture$value
    section.warnings <- c(section.warnings,
        rcmetar.reitsma.operation.messages(marginal.capture, "Marginal prediction intervals"))
    prediction.summary <- if (is.null(marginal.prediction)) NULL else
        marginal.prediction[c("sensitivity", "specificity", "false.positive.rate")]
    clinical.covariance <- rcmetar.reitsma.covariance.to.specificity(fit$Psi)
    clinical.correlation.raw <- if (all(diag(fit$Psi) > 0)) stats::cov2cor(fit$Psi) else NULL
    if (is.null(clinical.correlation.raw)) section.warnings <- c(section.warnings, "Between-study correlation is undefined for the boundary covariance fit.")
    clinical.correlation <- rcmetar.reitsma.covariance.to.specificity(clinical.correlation.raw)
    heterogeneity <- list(
        `Sensitivity logit SD`=sqrt(fit$Psi[1, 1]),
        `False-positive rate logit SD`=sqrt(fit$Psi[2, 2]),
        `Sensitivity-specificity covariance`=clinical.covariance[1, 2],
        `Sensitivity-specificity correlation`=if (is.null(clinical.correlation)) NULL else clinical.correlation[1, 2],
        Interpretation="SDs and covariance are on the model logit scale; correlation is unitless."
    )
    clinical.interpretation <- if (!is.null(point)) paste0(
        "Across ", length(diagnostic.data@study.names), " studies, summary sensitivity was ",
        rcmetar.reitsma.display.percent(point$sensitivity[["estimate"]], digits), " (", sprintf("%g%%", level * 100), " confidence interval ",
        rcmetar.reitsma.display.percent(point$sensitivity[["lower"]], digits), " to ", rcmetar.reitsma.display.percent(point$sensitivity[["upper"]], digits),
        ") and summary specificity was ", rcmetar.reitsma.display.percent(point$specificity[["estimate"]], digits), " (",
        sprintf("%g%%", level * 100), " confidence interval ", rcmetar.reitsma.display.percent(point$specificity[["lower"]], digits),
        " to ", rcmetar.reitsma.display.percent(point$specificity[["upper"]], digits), ").\n",
        "These are average operating characteristics across the included study thresholds. ",
        "The Reitsma bivariate and HSROC formulations are equivalent parameterizations of this model; that equivalence does not assume a common threshold. ",
        "Use the prediction intervals to assess how performance may vary in a new setting."
    ) else paste0(
        "Across ", length(diagnostic.data@study.names),
        " studies, the summary operating point could not be calculated. " ,
        "Other valid model outputs are shown below."
    )
    aic.capture <- rcmetar.reitsma.capture.warnings(stats::AIC(fit))
    bic.capture <- rcmetar.reitsma.capture.warnings(stats::BIC(fit))
    section.warnings <- c(section.warnings,
        rcmetar.reitsma.operation.messages(aic.capture, "AIC"),
        rcmetar.reitsma.operation.messages(bic.capture, "BIC"))
    summary.warnings <- unique(summary.warnings)
    summary.warnings <- summary.warnings[!is.na(summary.warnings) & nzchar(trimws(summary.warnings))]
    all.warnings <- unique(c(fit.warnings, summary.warnings, section.warnings))
    all.warnings <- all.warnings[!is.na(all.warnings) & nzchar(trimws(all.warnings))]
    if (length(all.warnings)) clinical.interpretation <- paste(
        clinical.interpretation,
        paste(c("Analysis warnings:", paste0("- ", all.warnings)), collapse="\n"),
        sep="\n\n"
    )
    i2.summary <- rcmetar.reitsma.display.i2.summary(i2, digits)
    model.info <- list(
        estimator=toupper(method), studies.used=length(diagnostic.data@study.names),
        correction.factor=adjust, correction.policy=policy,
        converged=fit$converged, logLik=as.numeric(fit$logLik),
        summary.seed=summary.seed, summary.iterations=summary.iterations,
        summary.warnings=summary.warnings, warnings=all.warnings,
        AIC=if (is.null(aic.capture$value)) NULL else as.numeric(aic.capture$value),
        BIC=if (is.null(bic.capture$value)) NULL else as.numeric(bic.capture$value),
        formula="cbind(tsens, tfpr) ~ 1",
        package.version=as.character(packageVersion("mada"))
    )
    summary.point.display <- if (is.null(point)) NULL else list(
        `Summary sensitivity`=rcmetar.reitsma.display.interval(point$sensitivity, level, "CI", digits),
        `Summary specificity`=rcmetar.reitsma.display.interval(point$specificity, level, "CI", digits),
        `False-positive rate`=rcmetar.reitsma.display.interval(point$false.positive.rate, level, "CI", digits)
    )
    prediction.display <- if (is.null(prediction.summary)) NULL else list(
        description="Underlying new-study operating characteristics",
        intervals=lapply(prediction.summary, rcmetar.reitsma.display.interval, level=level, kind="PI", digits=digits)
    )
    if (!is.null(prediction.display)) {
        names(prediction.display$intervals) <- c("Sensitivity", "Specificity", "False-positive rate")
    }
    summary <- list(
        "Clinical interpretation"=clinical.interpretation,
        "Summary operating point"=summary.point.display,
        "Sampling-based summary ratios"=rcmetar.reitsma.display.ratios(ratios, level, digits),
        "Marginal prediction"=prediction.display,
        "Between-study heterogeneity"=heterogeneity,
        "Diagnostic I-squared"=list(
            `I-squared summary`=i2.summary,
            `I-squared estimates`=rcmetar.reitsma.display.i2(i2, digits),
            Interpretation="I-squared is shown as percent unexplained heterogeneity; Zhou-Dendukuri and Holling are distinct estimators."
        ),
        "Model information"=model.info
    )
    if (!is.null(auc)) summary[["SROC AUC"]] <- list(
        AUC=auc[["AUC"]] %||% NULL, normalized.partial.AUC=auc[["pAUC"]] %||% NULL,
        full.FPR.bounds=c(0.01, 0.99), partial.FPR.bounds=pauc.bounds,
        note="The Reitsma bivariate and HSROC models are equivalent parameterizations of the same threshold-aware diagnostic model; this does not imply a common threshold.",
        `AUC confidence interval`="Not provided by mada::AUC(); no invented AUC CI.")
    # Keep the most useful sections first while ensuring optional AUC remains
    # near the other SROC outputs when it is available.
    if (!is.null(auc)) {
        desired.order <- c("Clinical interpretation", "Summary operating point",
            "Sampling-based summary ratios", "SROC AUC", "Marginal prediction",
            "Between-study heterogeneity", "Diagnostic I-squared", "Model information")
        summary <- summary[intersect(desired.order, names(summary))]
    }
    plot.names <- if (length(images)) setNames("sroc", names(images)) else character()
    list(images=images, image_order=names(images), plot_names=plot.names, plot_params_paths=plot.paths,
         plot_capabilities=capabilities, Summary=summary,
         References=rcmetar.unique.references(c(rcmetar.method.references("reitsma"), rcmetar.method.references("rutter.gatsonis"))))
}

diagnostic.reitsma.parameters <- function() {
    list(parameters=list(estimator=c("REML", "ML"), conf.level="float", adjust="float",
                          correction.policy=rcmetar.reitsma.correction.policies(), digits="int"),
         defaults=list(estimator="REML", conf.level=95, adjust=.5,
                       correction.policy="All studies if any zero exists", digits=2),
         var_order=c("estimator", "conf.level", "adjust", "correction.policy", "digits"))
}

diagnostic.reitsma.pretty.names <- function() list(
    pretty.name="Reitsma bivariate model",
    description="Count-based joint sensitivity and specificity model backed by mada 0.5.12.",
    estimator=list(pretty.name="Estimator", description="REML is the default; ML is available."),
    conf.level=list(pretty.name="Confidence level", description="Confidence level for compatible intervals and regions."),
    adjust=list(pretty.name="Continuity-correction factor", description="Constant added according to the correction policy."),
    correction.policy=list(pretty.name="Correction policy", description="Studies with any zero cell, All studies if any zero exists, or None."),
    digits=list(pretty.name="Display digits", description="Decimal places used for presentation."))

diagnostic.reitsma.is.feasible <- function(diagnostic.data, metric) {
    is(diagnostic.data, "DiagnosticData") && length(diagnostic.data@TP) >= 5L &&
        length(diagnostic.data@TP) == length(diagnostic.data@FN) &&
        length(diagnostic.data@TP) == length(diagnostic.data@FP) &&
        length(diagnostic.data@TP) == length(diagnostic.data@TN)
}

diagnostic.reitsma.meta.regression <- function(reg.data, params, stop.at.rma=FALSE) {
    if (!requireNamespace("mada", quietly=TRUE) || as.character(packageVersion("mada")) != "0.5.12") {
        stop("Reitsma bivariate meta-regression requires mada 0.5.12.", call.=FALSE)
    }
    covs <- reg.data@covariates
    if (length(covs) < 1L) stop("Reitsma meta-regression requires at least one selected moderator.", call.=FALSE)
    counts <- rcmetar.reitsma.validate.counts(reg.data, min.studies=1L)
    data <- data.frame(TP=counts$TP, FN=counts$FN, FP=counts$FP, TN=counts$TN,
                       stringsAsFactors=FALSE)
    terms <- character()
    coding <- list()
    moderator.values <- list()
    for (cov in covs) {
        name <- as.character(cov@cov.name)
        values <- cov@cov.vals
        if (length(values) != nrow(data) || any(is.na(values) | values == ""))
            stop(sprintf("Missing moderator values for '%s'. Confirm exclusions before fitting.", name), call.=FALSE)
        if (identical(cov@cov.type, "factor")) {
            levels <- sort(unique(as.character(values)))
            if (length(levels) < 2L) {
                observed <- if (length(levels)) sprintf("only observed level '%s'", levels[[1L]]) else "no observed levels"
                stop(sprintf(
                    "Categorical moderator '%s' has fewer than two observed levels after missing-value exclusions (%s). Restore eligible studies or remove this moderator before fitting.",
                    name, observed
                ), call.=FALSE)
            }
            ref <- as.character(cov@ref.var)
            if (!(ref %in% levels)) stop(sprintf("Reference level '%s' for moderator '%s' is absent.", ref, name), call.=FALSE)
            levels <- c(ref, setdiff(levels, ref))
            moderator.values[[name]] <- factor(as.character(values), levels=levels)
            contrasts(moderator.values[[name]]) <- stats::contr.treatment(length(levels), base=1L)
            coding[[name]] <- list(type="factor", levels=levels, reference=ref)
        } else {
            numeric.values <- suppressWarnings(as.numeric(values))
            if (any(!is.finite(numeric.values))) stop(sprintf("Moderator '%s' must contain finite numeric values.", name), call.=FALSE)
            moderator.values[[name]] <- numeric.values
            coding[[name]] <- list(type="continuous", range=range(numeric.values))
        }
        terms <- c(terms, name)
    }
    # mada rebuilds its design frame with data.frame(), which sanitizes
    # non-syntactic column names. Fit against stable aliases while retaining
    # the entered names for tables and researcher-facing model information.
    model.terms <- make.names(terms, unique=TRUE)
    for (i in seq_along(terms)) {
        data[[model.terms[[i]]]] <- moderator.values[[terms[[i]]]]
        coding[[terms[[i]]]]$model.name <- model.terms[[i]]
    }
    formula <- rcmetar.reitsma.formula(model.terms)
    design <- stats::model.matrix(formula, data=cbind(data, tsens=0, tfpr=0))
    p <- ncol(design)
    if (qr(design)$rank < p) stop("Reitsma moderator design matrix is rank deficient; remove redundant moderators or levels.", call.=FALSE)
    if (nrow(data) < max(5L, p + 2L)) stop(sprintf("Reitsma meta-regression requires at least %d eligible studies for %d model-matrix columns; %d supplied.", max(5L,p+2L), p, nrow(data)), call.=FALSE)
    method <- rcmetar.reitsma.estimator(params)
    adjust <- as.numeric(params$adjust %||% .5)
    if (!is.finite(adjust) || adjust < 0) stop("Reitsma correction factor must be finite and non-negative.", call.=FALSE)
    policy <- as.character(params$correction.policy %||% "All studies if any zero exists")
    control <- rcmetar.reitsma.correction.control(policy)
    if (control == "none" && any(unlist(counts) == 0)) stop("Correction policy None cannot fit boundary proportions.", call.=FALSE)
    level <- as.numeric(params$conf.level %||% 95) / 100
    validate.conf.level(level * 100)
    digits <- suppressWarnings(as.integer(params$digits %||% 3L))
    if (length(digits) != 1L || is.na(digits) || digits < 0L || digits > 15L) digits <- 3L
    warnings <- character()
    fit.capture <- rcmetar.reitsma.capture.warnings(mada::reitsma(
        data=data, formula=formula, correction=adjust,
        correction.control=control, method=method))
    fit <- rcmetar.reitsma.require.value(fit.capture, "Reitsma meta-regression fit")
    warnings <- c(warnings, rcmetar.reitsma.warning.messages(fit.capture, "Full model fit: "))
    rcmetar.reitsma.validate.fit(fit, "Reitsma meta-regression")
    if (isTRUE(stop.at.rma)) return(fit)
    summary.capture <- rcmetar.reitsma.capture.warnings(summary(fit, level=level))
    sm <- rcmetar.reitsma.require.value(summary.capture, "Reitsma meta-regression summary")
    warnings <- c(warnings, rcmetar.reitsma.warning.messages(summary.capture, "Full model summary: "))
    coefficients <- sm$coefficients
    sens.coefficients <- rcmetar.reitsma.coefficient.table(
        coefficients[grepl("tsens", rownames(coefficients), fixed=TRUE),,drop=FALSE])
    spec.coefficients <- rcmetar.reitsma.coefficient.table(
        coefficients[grepl("tfpr", rownames(coefficients), fixed=TRUE),,drop=FALSE], specificity=TRUE)
    sens.coefficients <- rcmetar.reitsma.restore.coefficient.labels(sens.coefficients, coding)
    spec.coefficients <- rcmetar.reitsma.restore.coefficient.labels(spec.coefficients, coding)
    sens.coefficients <- rcmetar.reitsma.add.reference.rows(sens.coefficients, coding)
    spec.coefficients <- rcmetar.reitsma.add.reference.rows(spec.coefficients, coding)
    fit.ml.capture <- rcmetar.reitsma.capture.warnings(mada::reitsma(
        data=data, formula=formula, correction=adjust,
        correction.control=control, method="ml"))
    fit.ml <- rcmetar.reitsma.require.value(fit.ml.capture, "Reitsma full ML likelihood-ratio fit")
    warnings <- c(warnings, rcmetar.reitsma.warning.messages(fit.ml.capture, "Full ML likelihood-ratio fit: "))
    intercept.data <- data
    intercept.formula <- stats::reformulate(
        termlabels=character(0),
        response="cbind(tsens, tfpr)"
    )
    reduced.ml.capture <- rcmetar.reitsma.capture.warnings(mada::reitsma(
        data=intercept.data, formula=intercept.formula, correction=adjust,
        correction.control=control, method="ml"))
    reduced.ml <- rcmetar.reitsma.require.value(reduced.ml.capture, "Reitsma intercept-only likelihood-ratio fit")
    warnings <- c(warnings, rcmetar.reitsma.warning.messages(reduced.ml.capture, "Intercept-only likelihood-ratio fit: "))
    rcmetar.reitsma.validate.fit(fit.ml, "Reitsma ML likelihood-ratio")
    rcmetar.reitsma.validate.fit(reduced.ml, "Reitsma intercept-only likelihood-ratio")
    lrt <- function(full, reduced, label) {
        df <- attr(full$logLik,"df") - attr(reduced$logLik,"df")
        statistic <- max(0, 2 * (as.numeric(full$logLik) - as.numeric(reduced$logLik)))
        list(moderator=label, statistic=statistic, df=df, p.value=stats::pchisq(statistic, df=df, lower.tail=FALSE))
    }
    block.tests <- lapply(seq_along(terms), function(i) {
        remaining <- model.terms[-i]
        reduced.formula <- if (length(remaining))
            rcmetar.reitsma.formula(remaining)
        else intercept.formula
        reduced.capture <- rcmetar.reitsma.capture.warnings(mada::reitsma(
            data=data, formula=reduced.formula, correction=adjust,
            correction.control=control, method="ml"))
        reduced <- rcmetar.reitsma.require.value(
            reduced.capture,
            paste0("Reitsma reduced model for moderator '", terms[[i]], "'")
        )
        warnings <<- c(warnings, rcmetar.reitsma.warning.messages(
            reduced.capture, paste0("Reduced model for moderator '", terms[[i]], "': ")))
        rcmetar.reitsma.validate.fit(reduced, "Reitsma reduced meta-regression")
        lrt(fit.ml, reduced, terms[[i]])
    })
    names(block.tests) <- terms
    images <- character(); image.order <- character(); plot.names <- character(); plot.paths <- character(); plot.capabilities <- list()
    if (!identical(params$create.plot, FALSE)) {
        output <- as.character(params$fp_outpath %||% rcmetar.scratch.path("reitsma_coefficients.svg"))
        extension <- tools::file_ext(output); if (!nzchar(extension)) extension <- "svg"
        stem <- tools::file_path_sans_ext(output)
        specifications <- list(Sensitivity=list(data=sens.coefficients, suffix="sensitivity"),
                               Specificity=list(data=spec.coefficients, suffix="specificity"))
        for (scale in names(specifications)) {
            spec <- specifications[[scale]]
            path <- paste0(stem, "_", spec$suffix, ".", extension)
            plot.params <- params
            plot.params$reitsma.coefficient.scale <- scale
            plot.params$reitsma.moderator.coding <- coding
            bundle <- rcmetar.reitsma.coefficient.bundle(spec$data, scale, plot.params)
            plot.params$reitsma.coefficient.geometry <- bundle
            rcmetar.draw.reitsma.coefficient(bundle, path)
            saved <- save.data(reg.data, fit, plot.params, bundle)
            title <- paste(scale, "Moderator Coefficients")
            images[[title]] <- path; image.order <- c(image.order, title); plot.names[[title]] <- "forest"; plot.paths[[title]] <- saved
            plot.capabilities[[title]] <- .rcmetar.plot.descriptor.for.kind("forest", has.params=TRUE)
        }
    }
    full.aic.capture <- rcmetar.reitsma.capture.warnings(stats::AIC(fit))
    full.bic.capture <- rcmetar.reitsma.capture.warnings(stats::BIC(fit))
    warnings <- c(warnings,
        rcmetar.reitsma.operation.messages(full.aic.capture, "Full model AIC"),
        rcmetar.reitsma.operation.messages(full.bic.capture, "Full model BIC"))
    all.warnings <- unique(warnings)
    all.warnings <- all.warnings[!is.na(all.warnings) & nzchar(trimws(all.warnings))]
    clinical.interpretation <- paste0(
        "This Reitsma bivariate meta-regression jointly models sensitivity and false-positive rate across ",
        nrow(data), " studies using ", length(terms), " moderator", if (length(terms) == 1L) "" else "s", ".\n",
        "Moderator coefficients are reported separately for sensitivity and specificity as odds ratios with confidence intervals. ",
        "Reference rows equal 1; continuous-moderator estimates describe a one-unit increase."
    )
    if (length(all.warnings)) clinical.interpretation <- paste(
        clinical.interpretation,
        paste(c("Analysis warnings:", paste0("- ", all.warnings)), collapse="\n"),
        sep="\n\n"
    )
    display.formula <- paste("cbind(tsens, tfpr) ~", paste0("`", gsub("`", "``", terms, fixed=TRUE), "`", collapse=" + "))
    public.coding <- lapply(coding, function(item) item[setdiff(names(item), "model.name")])
    model.info <- list(estimator=toupper(method), formula=display.formula, studies.used=nrow(data),
                       correction.policy=policy, correction.factor=adjust,
                       converged=fit$converged, logLik=as.numeric(fit$logLik),
                       AIC=if (is.null(full.aic.capture$value)) NULL else as.numeric(full.aic.capture$value),
                       BIC=if (is.null(full.bic.capture$value)) NULL else as.numeric(full.bic.capture$value),
                       warnings=all.warnings,
                       package.version=as.character(packageVersion("mada")))
    list(images=images, image_order=image.order, plot_names=plot.names, plot_params_paths=plot.paths,
         plot_capabilities=plot.capabilities, input_data=reg.data, input_params=params, res=fit,
         Summary=list("Clinical interpretation"=clinical.interpretation,
                      "Overall ML likelihood-ratio test"=lrt(fit.ml,reduced.ml,"All moderators"),
                      "Moderator block tests"=block.tests,
                      "Sensitivity coefficients"=sens.coefficients, "Specificity coefficients"=spec.coefficients,
                      "Residual diagnostic I-squared"=list(
                          `I-squared estimates`=rcmetar.reitsma.display.i2(sm$i2, digits),
                          Interpretation="I-squared is shown as percent unexplained heterogeneity; residual values describe heterogeneity after moderator adjustment."
                      ), "Moderator coding"=public.coding,
                      "Model information"=model.info),
         References=rcmetar.unique.references(rcmetar.method.references("reitsma")))
}
