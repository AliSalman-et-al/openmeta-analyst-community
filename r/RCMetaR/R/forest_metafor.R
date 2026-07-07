# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# Default metafor-backed forest renderer and shared bundle builders.

rcmetar.forest.study.header.label <- function(header) {
    if (is.null(header) || length(header) == 0 ||
            as.character(header) %in% c("[default]", "Studies", "Author(s) and Year")) {
        return("Study or Subgroup")
    }
    as.character(header)
}

rcmetar.metafor.binary.default.supported <- function(binary.data, params, selected.cov=NULL) {
    n <- length(binary.data@study.names)
    has.raw <- rcmetar.has.binary.raw.columns(binary.data, n)
    has.entered.effects <- rcmetar.has.entered.effects(binary.data, n)
    is.null(selected.cov) &&
        !isTRUE(params$fp_legacy_renderer) &&
        "BinaryData" %in% class(binary.data) &&
        rcmetar.forest.style(params) %in% c("default", "revman", "bmj") &&
        as.character(params$measure) %in% binary.two.arm.metrics &&
        n > 0 &&
        (has.raw || has.entered.effects)
}

rcmetar.metafor.continuous.default.supported <- function(cont.data, params, selected.cov=NULL) {
    n <- length(cont.data@study.names)
    is.null(selected.cov) &&
        !isTRUE(params$fp_legacy_renderer) &&
        !identical(params$create.plot, FALSE) &&
        "ContinuousData" %in% class(cont.data) &&
        rcmetar.forest.style(params) %in% c("default", "revman", "bmj") &&
        as.character(params$measure) %in% c(continuous.two.arm.metrics, continuous.one.arm.metrics) &&
        n > 0 &&
        (rcmetar.has.continuous.raw.columns(cont.data, n, params) || rcmetar.has.entered.effects(cont.data, n))
}

rcmetar.metafor.diagnostic.default.supported <- function(diagnostic.data, params, selected.cov=NULL) {
    n <- length(diagnostic.data@study.names)
    has.counts <- rcmetar.has.diagnostic.raw.columns(diagnostic.data, n)
    has.entered.effects <- rcmetar.has.entered.effects(diagnostic.data, n)

    is.null(selected.cov) &&
        !isTRUE(params$fp_legacy_renderer) &&
        !identical(params$create.plot, FALSE) &&
        "DiagnosticData" %in% class(diagnostic.data) &&
        rcmetar.forest.style(params) %in% c("default", "revman", "bmj") &&
        as.character(params$measure) %in% c(diagnostic.logit.metrics, diagnostic.log.metrics) &&
        n > 0 &&
        (has.counts || has.entered.effects)
}

rcmetar.has.entered.effects <- function(om.data, n=length(om.data@study.names)) {
    length(om.data@y) == n && length(om.data@SE) == n
}

rcmetar.has.binary.raw.columns <- function(binary.data, n=length(binary.data@study.names)) {
    n > 0 &&
        length(binary.data@g1O1) == n &&
        length(binary.data@g1O2) == n &&
        length(binary.data@g2O1) == n &&
        length(binary.data@g2O2) == n
}

rcmetar.has.continuous.raw.columns <- function(cont.data, n=length(cont.data@study.names), params=NULL) {
    n > 0 &&
        length(cont.data@N1) == n &&
        length(cont.data@mean1) == n &&
        length(cont.data@sd1) == n &&
        (
            is.null(params) ||
                !(as.character(params$measure) %in% continuous.two.arm.metrics) ||
                (
                    length(cont.data@N2) == n &&
                        length(cont.data@mean2) == n &&
                        length(cont.data@sd2) == n
                )
        )
}

rcmetar.has.diagnostic.raw.columns <- function(diagnostic.data, n=length(diagnostic.data@study.names)) {
    n > 0 &&
        length(diagnostic.data@TP) == n &&
        length(diagnostic.data@FP) == n &&
        length(diagnostic.data@FN) == n &&
        length(diagnostic.data@TN) == n
}

rcmetar.raw.values.complete <- function(values) {
    values <- suppressWarnings(as.numeric(values))
    length(values) > 0 && all(is.finite(values))
}

rcmetar.format.metafor.raw <- function(values) {
    values <- as.numeric(values)
    labels <- as.character(values)
    labels[!is.finite(values)] <- ""
    labels
}

rcmetar.format.metafor.numeric <- function(values, digits) {
    values <- as.numeric(values)
    ifelse(is.na(values), "", round.display(values, digits))
}

rcmetar.empty.forest.ilab <- function(n) {
    matrix <- matrix(character(0), nrow=n, ncol=0)
    list(matrix=matrix, columns=list(), headers=character(0), groups=character(0))
}

rcmetar.study.labels <- function(om.data) {
    labels <- as.character(om.data@study.names)
    years <- om.data@years
    if (!is.null(years) && length(years) == length(labels)) {
        has.year <- !is.na(years) & years != 0
        labels[has.year] <- paste(labels[has.year], years[has.year], sep=", ")
    }
    labels
}

rcmetar.metafor.weights <- function(res) {
    if (inherits(res, "rma")) {
        return(as.numeric(weights(res)))
    }
    if (!is.null(res$study.weights)) {
        return(as.numeric(res$study.weights))
    }
    NULL
}

rcmetar.metafor.default.supported <- function(params) {
    !isTRUE(params$fp_legacy_renderer) &&
        rcmetar.forest.style(params) %in% c("default", "revman", "bmj")
}

rcmetar.bundle.transform <- function(bundle) {
    switch(
        bundle$data_type,
        binary=binary.transform.f(as.character(bundle$params$measure)),
        continuous=continuous.transform.f(as.character(bundle$params$measure)),
        diagnostic=diagnostic.transform.f(as.character(bundle$params$measure)),
        binary.transform.f(as.character(bundle$params$measure))
    )
}

rcmetar.result.vector <- function(results, field) {
    vapply(results, function(result) as.numeric(result[[field]][1]), numeric(1))
}

rcmetar.build.sequential.metafor.bundle <- function(om.data, params, results, variant, labels, legacy.plot.data=NULL) {
    if (is.null(legacy.plot.data)) {
        legacy.plot.data <- switch(
            variant,
            cumulative=create.plot.data.cum(om.data, params, results),
            "leave-one-out"=create.plot.data.loo(om.data, params, results),
            NULL
        )
    }

    yi <- rcmetar.result.vector(results, "b")
    ci.lb <- rcmetar.result.vector(results, "ci.lb")
    ci.ub <- rcmetar.result.vector(results, "ci.ub")
    sei <- rcmetar.result.vector(results, "se")
    missing.se <- !is.finite(sei)
    if (any(missing.se)) {
        mult <- get.mult.from.conf.level(params$conf.level)
        sei[missing.se] <- (ci.ub[missing.se] - ci.lb[missing.se]) / (2 * mult)
    }

    list(
        render_engine = "metafor",
        data_type = .rcmetar.data.type(om.data),
        forest_variant = variant,
        fp_style = rcmetar.forest.style(params),
        res = results,
        effect = list(
            yi = yi,
            sei = sei,
            ci.lb = ci.lb,
            ci.ub = ci.ub,
            slab = as.character(labels)
        ),
        single_study = TRUE,
        ilab = rcmetar.empty.forest.ilab(length(labels)),
        slab = as.character(labels),
        weights = NULL,
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
}

rcmetar.build.subgroup.metafor.bundle <- function(om.data, params, subgroup.data, legacy.plot.data=NULL) {
    if (is.null(legacy.plot.data)) {
        legacy.plot.data <- switch(
            .rcmetar.data.type(om.data),
            binary=create.subgroup.plot.data.binary(subgroup.data, params),
            continuous=create.subgroup.plot.data.cont(subgroup.data, params),
            diagnostic=create.subgroup.plot.data.diagnostic(subgroup.data, params)
        )
    }

    subgroup.list <- as.character(subgroup.data$subgroup.list)
    grouped.data <- subgroup.data$grouped.data
    subgroup.results <- subgroup.data$results
    study.data <- grouped.data[seq_along(subgroup.list)]
    flat.yi <- unlist(lapply(study.data, function(data) as.numeric(data@y)), use.names=FALSE)
    flat.sei <- unlist(lapply(study.data, function(data) as.numeric(data@SE)), use.names=FALSE)
    subgroup.values <- unlist(Map(function(group, data) {
        rep(group, length(data@study.names))
    }, subgroup.list, study.data), use.names=FALSE)
    mult <- get.mult.from.conf.level(params$conf.level)
    flat.ci.lb <- flat.yi - mult * flat.sei
    flat.ci.ub <- flat.yi + mult * flat.sei
    flat.slab <- unlist(lapply(study.data, rcmetar.study.labels), use.names=FALSE)
    flat.ilab <- lapply(study.data, rcmetar.ilab.for.data, params=params, res=NULL)
    ilab.matrix <- do.call(rbind, lapply(flat.ilab, function(ilab) ilab$matrix))
    if (is.null(ilab.matrix)) {
        ilab.matrix <- matrix(character(0), nrow=length(flat.slab), ncol=0)
    }
    ilab.template <- rcmetar.ilab.for.data(om.data, params, subgroup.results[[length(subgroup.list) + 1]])
    colnames(ilab.matrix) <- ilab.template$headers

    study.rows <- list()
    header.rows <- numeric(length(subgroup.list))
    polygon.rows <- numeric(length(subgroup.list))
    cursor <- length(flat.slab) + length(subgroup.list) * 2
    for (i in seq_along(subgroup.list)) {
        n <- length(study.data[[i]]@study.names)
        header.rows[[i]] <- cursor
        study.rows[[i]] <- seq(from=cursor - 1.0, length.out=n, by=-1)
        polygon.rows[[i]] <- min(study.rows[[i]]) - 1
        cursor <- polygon.rows[[i]] - 2.2
    }

    bundle <- list(
        render_engine = "metafor",
        data_type = .rcmetar.data.type(om.data),
        forest_variant = "subgroup",
        fp_style = rcmetar.forest.style(params),
        res = subgroup.results[[length(subgroup.list) + 1]],
        effect = list(yi=flat.yi, sei=flat.sei, ci.lb=flat.ci.lb, ci.ub=flat.ci.ub, slab=flat.slab),
        single_study = TRUE,
        ilab = list(
            matrix = ilab.matrix,
            columns = ilab.template$columns,
            headers = ilab.template$headers,
            groups = ilab.template$groups
        ),
        slab = flat.slab,
        weights = NULL,
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data,
        subgroups = list(
            names = subgroup.list,
            results = subgroup.results[seq_along(subgroup.list)],
            overall = subgroup.results[[length(subgroup.list) + 1]],
            study_rows = unlist(study.rows, use.names=FALSE),
            header_rows = header.rows,
            polygon_rows = polygon.rows,
            overall_row = min(polygon.rows) - 2,
            difference_test = rcmetar.metafor.subgroup.difference.test(flat.yi, flat.sei, subgroup.values, params),
            ylim = c(min(polygon.rows) - 4, max(header.rows) + 2.5)
        )
    )
    rcmetar.decorate.metafor.bundle(bundle)
}

rcmetar.metafor.subgroup.difference.test <- function(yi, sei, subgroup.values, params) {
    if (length(unique(subgroup.values)) < 2 || length(yi) != length(subgroup.values)) {
        return(NULL)
    }
    subgroup.factor <- stats::relevel(factor(subgroup.values), ref=as.character(subgroup.values[[1]]))
    res <- tryCatch(
        metafor::rma.uni(
            yi=yi,
            sei=sei,
            mods=~ subgroup.factor,
            method=params$rm.method,
            level=params$conf.level,
            digits=params$digits
        ),
        error=function(e) NULL
    )
    if (is.null(res) || is.null(res$QM) || display.value.is.missing(res$QM)) {
        return(NULL)
    }
    list(QM=res$QM, QMp=res$QMp, df=res$p - 1)
}

rcmetar.build.binary.metafor.bundle <- function(binary.data, params, res, legacy.plot.data=NULL) {
    if (is.null(legacy.plot.data)) {
        legacy.plot.data <- create.plot.data.generic(binary.data, params, res)
    }

    single.study <- !inherits(res, "rma")
    effect <- NULL
    if (single.study) {
        effect <- list(
            yi = as.numeric(binary.data@y),
            sei = as.numeric(binary.data@SE),
            ci.lb = as.numeric(res$ci.lb),
            ci.ub = as.numeric(res$ci.ub),
            slab = rcmetar.study.labels(binary.data)
        )
    }

    bundle <- list(
        render_engine = "metafor",
        data_type = "binary",
        fp_style = rcmetar.forest.style(params),
        res = res,
        effect = effect,
        single_study = single.study,
        ilab = rcmetar.ilab.for.data(binary.data, params, res),
        slab = rcmetar.study.labels(binary.data),
        weights = rcmetar.metafor.weights(res),
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
    rcmetar.decorate.metafor.bundle(bundle)
}

rcmetar.build.continuous.metafor.bundle <- function(cont.data, params, res, legacy.plot.data=NULL) {
    if (is.null(legacy.plot.data)) {
        legacy.plot.data <- create.plot.data.generic(cont.data, params, res)
    }

    single.study <- !inherits(res, "rma")
    effect <- NULL
    if (single.study) {
        effect <- list(
            yi = as.numeric(cont.data@y),
            sei = as.numeric(cont.data@SE),
            ci.lb = as.numeric(res$ci.lb),
            ci.ub = as.numeric(res$ci.ub),
            slab = rcmetar.study.labels(cont.data)
        )
    }

    bundle <- list(
        render_engine = "metafor",
        data_type = "continuous",
        fp_style = rcmetar.forest.style(params),
        res = res,
        effect = effect,
        single_study = single.study,
        ilab = rcmetar.ilab.for.data(cont.data, params, res),
        slab = rcmetar.study.labels(cont.data),
        weights = rcmetar.metafor.weights(res),
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
    rcmetar.decorate.metafor.bundle(bundle)
}

rcmetar.build.diagnostic.metafor.bundle <- function(diagnostic.data, params, res, legacy.plot.data=NULL) {
    if (is.null(legacy.plot.data)) {
        legacy.plot.data <- create.plot.data.generic(diagnostic.data, params, res)
    }

    single.study <- !inherits(res, "rma")
    effect <- NULL
    if (single.study) {
        effect <- list(
            yi = as.numeric(diagnostic.data@y),
            sei = as.numeric(diagnostic.data@SE),
            ci.lb = as.numeric(res$ci.lb),
            ci.ub = as.numeric(res$ci.ub),
            slab = rcmetar.study.labels(diagnostic.data)
        )
    }

    bundle <- list(
        render_engine = "metafor",
        data_type = "diagnostic",
        fp_style = rcmetar.forest.style(params),
        res = res,
        effect = effect,
        single_study = single.study,
        ilab = rcmetar.ilab.for.data(diagnostic.data, params, res),
        slab = rcmetar.study.labels(diagnostic.data),
        weights = rcmetar.metafor.weights(res),
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
    rcmetar.decorate.metafor.bundle(bundle)
}

rcmetar.metafor.atransf <- function(bundle) {
    measure <- as.character(bundle$params$measure)
    if (metric.is.log.scale(measure)) {
        return(exp)
    }
    if (metric.is.logit.scale(measure)) {
        return(invlogit)
    }
    NULL
}

rcmetar.metafor.refline <- function(bundle, alim=NULL) {
    if (identical(bundle$forest_variant, "cumulative") || identical(bundle$forest_variant, "leave-one-out")) {
        return(NA)
    }
    refline <- 0
    if (metric.is.log.scale(as.character(bundle$params$measure))) {
        refline <- 0
    }
    if (!is.null(alim) && is.finite(refline) && (refline < alim[[1]] || refline > alim[[2]])) {
        return(NA)
    }
    refline
}

rcmetar.metafor.axis.ticks <- function(bundle, alim) {
    params <- bundle$params
    if (!is.null(params$fp_xticks) && !identical(params$fp_xticks[1], "[default]") && !all(is.na(params$fp_xticks))) {
        ticks <- as.numeric(params$fp_xticks)
        if (metric.is.log.scale(as.character(params$measure))) {
            ticks <- log(ticks)
        }
        return(ticks)
    }
    if (metric.is.log.scale(as.character(params$measure))) {
        candidates <- log(c(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 10, 20, 100))
        ticks <- candidates[candidates >= alim[1] & candidates <= alim[2]]
        if (length(ticks) >= 2) {
            return(ticks)
        }
    }
    if (metric.is.logit.scale(as.character(params$measure))) {
        candidates <- logit(c(0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99))
        ticks <- candidates[candidates >= alim[1] & candidates <= alim[2]]
        if (length(ticks) >= 2) {
            return(ticks)
        }
    }
    pretty(alim)
}

rcmetar.metafor.xlab <- function(bundle) {
    helper <- rcmetar.metafor.style.helper(bundle$fp_style, "xlab")
    if (!is.null(helper)) {
        return(helper(bundle))
    }
    rcmetar.default.xlab(bundle)
}

rcmetar.metafor.study.header <- function(bundle) {
    helper <- rcmetar.metafor.style.helper(bundle$fp_style, "study.header")
    if (!is.null(helper)) {
        return(helper(bundle))
    }
    rcmetar.default.study.header(bundle)
}

rcmetar.metafor.effect.header <- function(bundle) {
    helper <- rcmetar.metafor.style.helper(bundle$fp_style, "effect.header")
    if (!is.null(helper)) {
        return(helper(bundle))
    }
    rcmetar.default.effect.header(bundle)
}

rcmetar.metafor.psize <- function(bundle) {
    if (identical(bundle$forest_variant, "subgroup")) {
        return(rep(1, length(bundle$effect$yi)))
    }
    if (inherits(bundle$res, "rma") && is.null(bundle$forest_variant)) {
        return(NULL)
    }
    sei <- as.numeric(bundle$effect$sei)
    multiplier <- rcmetar.point.size.multiplier(bundle$params)
    if (length(sei) == 0 || any(!is.finite(sei)) || length(unique(round(sei, 10))) == 1) {
        return(rep(1, length(sei)) * multiplier)
    }
    precision <- 1 / (sei^2)
    precision <- precision / max(precision, na.rm=TRUE)
    (0.65 + 0.9 * sqrt(precision)) * multiplier
}

rcmetar.metafor.alim <- function(bundle) {
    if (!is.null(bundle$plot_range) && length(bundle$plot_range) == 2 && all(is.finite(bundle$plot_range))) {
        if (metric.is.logit.scale(as.character(bundle$params$measure))) {
            return(logit(pmin(pmax(as.numeric(bundle$plot_range), .Machine$double.eps), 1 - .Machine$double.eps)))
        }
        return(as.numeric(bundle$plot_range))
    }
    values <- c(bundle$effect$yi, bundle$effect$ci.lb, bundle$effect$ci.ub)
    if (inherits(bundle$res, "rma")) {
        values <- c(values, bundle$res$yi, bundle$res$ci.lb, bundle$res$ci.ub)
    }
    values <- values[is.finite(values)]
    if (length(values) == 0) {
        return(c(-1, 1))
    }
    range(values)
}

rcmetar.metafor.effect.labels <- function(bundle) {
    legacy <- bundle$legacy_plot_data
    digits <- as.integer(bundle$params$digits)
    if (!is.null(bundle$forest_variant) && !identical(bundle$forest_variant, "standard")) {
        transform <- rcmetar.bundle.transform(bundle)
        y <- transform$display.scale(bundle$effect$yi)
        lb <- transform$display.scale(bundle$effect$ci.lb)
        ub <- transform$display.scale(bundle$effect$ci.ub)
    } else if (!is.null(legacy$effects.disp)) {
        y <- legacy$effects.disp$y.disp
        lb <- legacy$effects.disp$lb.disp
        ub <- legacy$effects.disp$ub.disp
    } else if (isTRUE(bundle$single_study)) {
        transform <- rcmetar.bundle.transform(bundle)
        y <- transform$display.scale(bundle$effect$yi)
        lb <- transform$display.scale(bundle$effect$ci.lb)
        ub <- transform$display.scale(bundle$effect$ci.ub)
    } else {
        transform <- rcmetar.bundle.transform(bundle)
        y <- transform$display.scale(c(bundle$res$yi, bundle$res$b))
        lb <- transform$display.scale(c(bundle$res$ci.lb, bundle$res$ci.lb))
        ub <- transform$display.scale(c(bundle$res$ci.ub, bundle$res$ci.ub))
    }
    paste0(
        round.display(y, digits),
        " [",
        round.display(lb, digits),
        ", ",
        round.display(ub, digits),
        "]"
    )
}

rcmetar.metafor.heterogeneity.measure.label <- function(bundle) {
    helper <- rcmetar.metafor.style.helper(bundle$fp_style, "heterogeneity.measure.label")
    if (!is.null(helper)) {
        return(helper(bundle))
    }
    rcmetar.default.heterogeneity.measure.label(bundle)
}

rcmetar.measure.metafor.forest.device <- function(bundle) {
    rcmetar.default.measure.forest.device(bundle)
}

rcmetar.metafor.wrap.header <- function(label, width=18) {
    rcmetar.default.wrap.header(label, width=width)
}

rcmetar.metafor.group.headers <- function(bundle) {
    helper <- rcmetar.metafor.style.helper(bundle$fp_style, "group.headers")
    if (!is.null(helper)) {
        return(helper(bundle))
    }
    rcmetar.default.group.headers(bundle)
}

rcmetar.metafor.layout <- function(bundle, size, alim) {
    rcmetar.default.layout(bundle, size, alim)
}

rcmetar.open.metafor_device <- function(outpath, size) {
    rcmetar.open.svg_device(outpath, size)
}

rcmetar.draw.metafor.forest <- function(bundle, outpath) {
    renderer <- rcmetar.metafor.style.renderer(bundle$fp_style)
    if (!is.null(renderer)) {
        return(renderer(bundle, outpath))
    }
    rcmetar.draw.default.forest(bundle, outpath)
}

rcmetar.draw.metafor.sequential.text <- function(bundle, rows, layout, k, cex) {
    graphics::par(xpd=NA)
    graphics::text(layout$xlim[[1]], rows, bundle$slab, pos=4, cex=cex, col="black")
    if (rcmetar.param.is.true(bundle$params, "fp_show_annotation", TRUE)) {
        labels <- rcmetar.metafor.effect.labels(bundle)
        graphics::text(layout$xlim[[2]], rows, labels, pos=2, cex=cex, col="black")
    }
    if (rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE)) {
        first.row <- max(rows, na.rm=TRUE)
        header.y <- first.row + 1.25
        rule.y <- first.row + 0.70
        graphics::text(layout$xlim[[1]], header.y, rcmetar.metafor.study.header(bundle), pos=4, font=2, cex=cex, col="black")
        graphics::text(layout$xlim[[2]], header.y, rcmetar.metafor.effect.header(bundle), pos=2, font=2, cex=cex, col="black")
        graphics::segments(layout$xlim[[1]], rule.y, layout$xlim[[2]], rule.y, lwd=0.8)
    }
    invisible(NULL)
}

rcmetar.draw.metafor.single.study.accent <- function(bundle, rows, alim, color, pch=15) {
    if (identical(color, "black")) {
        return(invisible(NULL))
    }
    rcmetar.draw.metafor.effect.accent(
        effect=bundle$effect,
        rows=rows,
        alim=alim,
        color=color,
        psize=rcmetar.metafor.psize(bundle),
        pch=pch
    )
}

rcmetar.draw.metafor.effect.accent <- function(effect, rows, alim, color, psize, lwd=1.35, pch=15) {
    if (length(rows) != length(effect$yi)) {
        return(invisible(NULL))
    }
    yi <- as.numeric(effect$yi)
    ci.lb <- as.numeric(effect$ci.lb)
    ci.ub <- as.numeric(effect$ci.ub)
    finite <- is.finite(yi) & is.finite(ci.lb) & is.finite(ci.ub)
    if (!any(finite)) {
        return(invisible(NULL))
    }
    left <- pmax(ci.lb[finite], alim[[1]])
    right <- pmin(ci.ub[finite], alim[[2]])
    graphics::segments(left, rows[finite], right, rows[finite], col=color, lwd=lwd)
    rcmetar.draw.metafor.single.study.interval.ends(ci.lb[finite], ci.ub[finite], rows[finite], alim, color, lwd=lwd)
    inside <- yi[finite] >= alim[[1]] & yi[finite] <= alim[[2]]
    if (any(inside)) {
        graphics::points(
            yi[finite][inside],
            rows[finite][inside],
            pch=pch,
            col=color,
            cex=psize[finite][inside]
        )
    }
    invisible(NULL)
}

rcmetar.draw.metafor.single.study.interval.ends <- function(ci.lb, ci.ub, rows, alim, color, lwd=1.35) {
    span <- diff(alim)
    if (!is.finite(span) || span <= 0) {
        span <- 1
    }
    arrow.length <- span * 0.026
    cap.height <- 0.055

    left.clipped <- ci.lb < alim[[1]]
    if (any(left.clipped)) {
        for (row in rows[left.clipped]) {
            graphics::polygon(
                x=c(alim[[1]], alim[[1]] + arrow.length, alim[[1]] + arrow.length),
                y=c(row, row + cap.height * 1.35, row - cap.height * 1.35),
                col=color,
                border=color
            )
        }
    }

    right.clipped <- ci.ub > alim[[2]]
    if (any(right.clipped)) {
        for (row in rows[right.clipped]) {
            graphics::polygon(
                x=c(alim[[2]], alim[[2]] - arrow.length, alim[[2]] - arrow.length),
                y=c(row, row + cap.height * 1.35, row - cap.height * 1.35),
                col=color,
                border=color
            )
        }
    }

    left.cap <- !left.clipped & is.finite(ci.lb)
    if (any(left.cap)) {
        graphics::segments(
            ci.lb[left.cap],
            rows[left.cap] - cap.height,
            ci.lb[left.cap],
            rows[left.cap] + cap.height,
            col=color,
            lwd=lwd
        )
    }

    right.cap <- !right.clipped & is.finite(ci.ub)
    if (any(right.cap)) {
        graphics::segments(
            ci.ub[right.cap],
            rows[right.cap] - cap.height,
            ci.ub[right.cap],
            rows[right.cap] + cap.height,
            col=color,
            lwd=lwd
        )
    }

    invisible(NULL)
}
