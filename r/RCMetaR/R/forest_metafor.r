# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# metafor-backed forest renderer for the Default Forest Style.

rcmetar.forest.style.default <- function(params) {
    style <- params$fp_style
    if (is.null(style) || length(style) == 0 || is.na(style) || style == "[default]") {
        return("default")
    }
    style <- tolower(trimws(as.character(style[1])))
    switch(
        style,
        "default" = "default",
        "default (metafor)" = "default",
        "default forest style" = "default",
        style
    )
}

rcmetar.is.metafor.forest.bundle <- function(plot.data) {
    is.list(plot.data) &&
        identical(plot.data$render_engine, "metafor") &&
        !is.null(plot.data$fp_style)
}

rcmetar.metafor.binary.default.supported <- function(binary.data, params, selected.cov=NULL) {
    is.null(selected.cov) &&
        !isTRUE(params$fp_legacy_renderer) &&
        "BinaryData" %in% class(binary.data) &&
        rcmetar.forest.style.default(params) == "default" &&
        as.character(params$measure) %in% binary.two.arm.metrics &&
        length(binary.data@g1O1) > 0 &&
        length(binary.data@g1O1) == length(binary.data@g1O2) &&
        length(binary.data@g1O2) == length(binary.data@g2O1) &&
        length(binary.data@g2O1) == length(binary.data@g2O2)
}

rcmetar.metafor.continuous.default.supported <- function(cont.data, params, selected.cov=NULL) {
    is.null(selected.cov) &&
        !isTRUE(params$fp_legacy_renderer) &&
        !identical(params$create.plot, FALSE) &&
        "ContinuousData" %in% class(cont.data) &&
        rcmetar.forest.style.default(params) == "default" &&
        as.character(params$measure) %in% c(continuous.two.arm.metrics, continuous.one.arm.metrics) &&
        length(cont.data@study.names) > 0
}

rcmetar.metafor.diagnostic.default.supported <- function(diagnostic.data, params, selected.cov=NULL) {
    has.counts <- length(diagnostic.data@TP) > 0 &&
        length(diagnostic.data@TP) == length(diagnostic.data@FP) &&
        length(diagnostic.data@FP) == length(diagnostic.data@FN) &&
        length(diagnostic.data@FN) == length(diagnostic.data@TN)
    has.entered.effects <- length(diagnostic.data@y) > 0 && length(diagnostic.data@SE) > 0

    is.null(selected.cov) &&
        !isTRUE(params$fp_legacy_renderer) &&
        !identical(params$create.plot, FALSE) &&
        "DiagnosticData" %in% class(diagnostic.data) &&
        rcmetar.forest.style.default(params) == "default" &&
        as.character(params$measure) %in% c(diagnostic.logit.metrics, diagnostic.log.metrics) &&
        length(diagnostic.data@study.names) > 0 &&
        (has.counts || has.entered.effects)
}

rcmetar.binary.default.ilab <- function(binary.data, params) {
    columns <- list(
        list(key="experimental_events", group="Experimental", header="Events", values=binary.data@g1O1),
        list(key="experimental_nonevents", group="Experimental", header="Non-events", values=binary.data@g1O2),
        list(key="control_events", group="Control", header="Events", values=binary.data@g2O1),
        list(key="control_nonevents", group="Control", header="Non-events", values=binary.data@g2O2)
    )
    groups <- c("Experimental", "Control")
    if (!is.null(params$fp_col3_str) && params$fp_col3_str != "[default]") {
        groups[1] <- as.character(params$fp_col3_str)
    }
    if (!is.null(params$fp_col4_str) && params$fp_col4_str != "[default]") {
        groups[2] <- as.character(params$fp_col4_str)
    }
    for (i in seq_along(columns)) {
        if (columns[[i]]$group == "Experimental") {
            columns[[i]]$group <- groups[1]
        } else if (columns[[i]]$group == "Control") {
            columns[[i]]$group <- groups[2]
        }
    }

    matrix <- do.call(cbind, lapply(columns, function(column) column$values))
    mode(matrix) <- "character"
    headers <- vapply(columns, function(column) column$header, character(1))
    colnames(matrix) <- headers

    list(
        matrix = matrix,
        columns = columns,
        headers = headers,
        groups = unique(vapply(columns, function(column) column$group, character(1)))
    )
}

rcmetar.format.metafor.numeric <- function(values, digits) {
    values <- as.numeric(values)
    ifelse(is.na(values), "", round.display(values, digits))
}

rcmetar.continuous.default.ilab <- function(cont.data, params) {
    digits <- as.integer(params$digits)
    groups <- c("Experimental", "Control")
    if (!is.null(params$fp_col3_str) && params$fp_col3_str != "[default]") {
        groups[1] <- as.character(params$fp_col3_str)
    } else if (length(cont.data@g1.name) > 0 && nzchar(cont.data@g1.name[1])) {
        groups[1] <- cont.data@g1.name[1]
    }
    if (!is.null(params$fp_col4_str) && params$fp_col4_str != "[default]") {
        groups[2] <- as.character(params$fp_col4_str)
    } else if (length(cont.data@g2.name) > 0 && nzchar(cont.data@g2.name[1])) {
        groups[2] <- cont.data@g2.name[1]
    }

    columns <- list(
        list(key="experimental_mean", group=groups[1], header="Mean", values=rcmetar.format.metafor.numeric(cont.data@mean1, digits)),
        list(key="experimental_sd", group=groups[1], header="SD", values=rcmetar.format.metafor.numeric(cont.data@sd1, digits)),
        list(key="experimental_n", group=groups[1], header="N", values=as.character(cont.data@N1))
    )
    if (as.character(params$measure) %in% continuous.two.arm.metrics) {
        columns <- c(columns, list(
            list(key="control_mean", group=groups[2], header="Mean", values=rcmetar.format.metafor.numeric(cont.data@mean2, digits)),
            list(key="control_sd", group=groups[2], header="SD", values=rcmetar.format.metafor.numeric(cont.data@sd2, digits)),
            list(key="control_n", group=groups[2], header="N", values=as.character(cont.data@N2))
        ))
    }

    matrix <- do.call(cbind, lapply(columns, function(column) column$values))
    mode(matrix) <- "character"
    headers <- vapply(columns, function(column) column$header, character(1))
    colnames(matrix) <- headers

    list(
        matrix = matrix,
        columns = columns,
        headers = headers,
        groups = unique(vapply(columns, function(column) column$group, character(1)))
    )
}

rcmetar.empty.default.ilab <- function(n) {
    matrix <- matrix(character(0), nrow=n, ncol=0)
    list(matrix=matrix, columns=list(), headers=character(0), groups=character(0))
}

rcmetar.diagnostic.default.ilab <- function(diagnostic.data, params) {
    if (length(diagnostic.data@TP) == 0) {
        return(rcmetar.empty.default.ilab(length(diagnostic.data@study.names)))
    }

    columns <- list(
        list(key="true_positive", group="Counts", header="TP", values=diagnostic.data@TP),
        list(key="false_positive", group="Counts", header="FP", values=diagnostic.data@FP),
        list(key="false_negative", group="Counts", header="FN", values=diagnostic.data@FN),
        list(key="true_negative", group="Counts", header="TN", values=diagnostic.data@TN)
    )
    matrix <- do.call(cbind, lapply(columns, function(column) column$values))
    mode(matrix) <- "character"
    headers <- vapply(columns, function(column) column$header, character(1))
    colnames(matrix) <- headers

    list(
        matrix = matrix,
        columns = columns,
        headers = headers,
        groups = "Counts"
    )
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
        rcmetar.forest.style.default(params) == "default"
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
        fp_style = "default",
        res = results,
        effect = list(
            yi = yi,
            sei = sei,
            ci.lb = ci.lb,
            ci.ub = ci.ub,
            slab = as.character(labels)
        ),
        single_study = TRUE,
        ilab = rcmetar.empty.default.ilab(length(labels)),
        slab = as.character(labels),
        weights = NULL,
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
}

rcmetar.default.ilab.for.data <- function(om.data, params) {
    if ("BinaryData" %in% class(om.data)) {
        return(rcmetar.binary.default.ilab(om.data, params))
    }
    if ("ContinuousData" %in% class(om.data)) {
        return(rcmetar.continuous.default.ilab(om.data, params))
    }
    if ("DiagnosticData" %in% class(om.data)) {
        return(rcmetar.diagnostic.default.ilab(om.data, params))
    }
    rcmetar.empty.default.ilab(length(om.data@study.names))
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
    flat.ilab <- lapply(study.data, rcmetar.default.ilab.for.data, params=params)
    ilab.matrix <- do.call(rbind, lapply(flat.ilab, function(ilab) ilab$matrix))
    if (is.null(ilab.matrix)) {
        ilab.matrix <- matrix(character(0), nrow=length(flat.slab), ncol=0)
    }
    ilab.template <- rcmetar.default.ilab.for.data(om.data, params)
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

    list(
        render_engine = "metafor",
        data_type = .rcmetar.data.type(om.data),
        forest_variant = "subgroup",
        fp_style = "default",
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

    list(
        render_engine = "metafor",
        data_type = "binary",
        fp_style = "default",
        res = res,
        effect = effect,
        single_study = single.study,
        ilab = rcmetar.binary.default.ilab(binary.data, params),
        slab = rcmetar.study.labels(binary.data),
        weights = rcmetar.metafor.weights(res),
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
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

    list(
        render_engine = "metafor",
        data_type = "continuous",
        fp_style = "default",
        res = res,
        effect = effect,
        single_study = single.study,
        ilab = rcmetar.continuous.default.ilab(cont.data, params),
        slab = rcmetar.study.labels(cont.data),
        weights = rcmetar.metafor.weights(res),
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
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

    list(
        render_engine = "metafor",
        data_type = "diagnostic",
        fp_style = "default",
        res = res,
        effect = effect,
        single_study = single.study,
        ilab = rcmetar.diagnostic.default.ilab(diagnostic.data, params),
        slab = rcmetar.study.labels(diagnostic.data),
        weights = rcmetar.metafor.weights(res),
        params = params,
        side_by_side = FALSE,
        plot_range = legacy.plot.data$plot.range,
        changed.params = legacy.plot.data$changed.params,
        legacy_plot_data = legacy.plot.data
    )
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

rcmetar.metafor.refline <- function(bundle) {
    if (metric.is.log.scale(as.character(bundle$params$measure))) {
        return(0)
    }
    0
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
    params <- bundle$params
    if (!is.null(params$fp_xlabel) && params$fp_xlabel != "[default]") {
        return(as.character(params$fp_xlabel))
    }
    label <- pretty.metric.name(as.character(params$measure))
    if (metric.is.log.scale(as.character(params$measure))) {
        label <- paste(label, "(log scale)")
    }
    if (metric.is.logit.scale(as.character(params$measure))) {
        label <- paste(label, "(probability scale)")
    }
    label
}

rcmetar.metafor.study.header <- function(bundle) {
    header <- bundle$params$fp_col1_str
    if (is.null(header) || length(header) == 0 || header == "[default]") {
        return("Author(s) and Year")
    }
    as.character(header)
}

rcmetar.metafor.effect.header <- function(bundle) {
    paste0(pretty.metric.name(as.character(bundle$params$measure)), " [", bundle$params$conf.level, "% CI]")
}

rcmetar.metafor.psize <- function(bundle) {
    if (identical(bundle$forest_variant, "subgroup")) {
        return(rep(1, length(bundle$effect$yi)))
    }
    if (inherits(bundle$res, "rma") && is.null(bundle$forest_variant)) {
        return(NULL)
    }
    sei <- as.numeric(bundle$effect$sei)
    if (length(sei) == 0 || any(!is.finite(sei)) || length(unique(round(sei, 10))) == 1) {
        return(rep(1, length(sei)))
    }
    precision <- 1 / (sei^2)
    precision <- precision / max(precision, na.rm=TRUE)
    0.65 + 0.9 * sqrt(precision)
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

rcmetar.measure.metafor.forest.device <- function(bundle) {
    scratch <- rcmetar.scratch.path("INTER")
    grDevices::png(filename=scratch, width=1200, height=800, res=144)
    on.exit(grDevices::dev.off(), add=TRUE)

    k <- nrow(bundle$ilab$matrix)
    display.rows <- k
    if (identical(bundle$forest_variant, "subgroup")) {
        display.rows <- length(bundle$subgroups$study_rows) + length(bundle$subgroups$header_rows) + length(bundle$subgroups$polygon_rows) + 2
    }
    cex <- max(0.70, min(1.10, 1.08 - max(display.rows - 10, 0) * 0.018))
    study.width <- max(strwidth(c(bundle$slab, rcmetar.metafor.study.header(bundle)), units="inches", cex=cex), na.rm=TRUE)
    if (ncol(bundle$ilab$matrix) > 0) {
        column.widths <- apply(bundle$ilab$matrix, 2, function(col) {
            max(strwidth(c(col, bundle$ilab$headers), units="inches", cex=cex), na.rm=TRUE)
        })
        group.widths <- vapply(bundle$ilab$groups, function(group) strwidth(group, units="inches", cex=cex), numeric(1))
    } else {
        column.widths <- numeric(0)
        group.widths <- numeric(0)
    }
    annotation.width <- max(strwidth(c(rcmetar.metafor.effect.header(bundle), rcmetar.metafor.effect.labels(bundle)), units="inches", cex=cex), na.rm=TRUE)
    column.gap <- 0.34
    block.gap <- 0.78
    plot.width <- 3.5
    ilab.width <- if (length(column.widths) > 0) {
        sum(pmax(column.widths, 0.45)) + column.gap * (length(column.widths) - 1) + block.gap
    } else {
        0
    }
    left.width <- study.width + block.gap + ilab.width

    list(
        width = max(9.5, min(18, left.width + plot.width + annotation.width + 1.5)),
        height = max(5.8, min(20, 3.1 + 0.48 * display.rows)),
        cex = cex,
        study_width = study.width,
        column_widths = pmax(column.widths, 0.45),
        group_widths = group.widths,
        column_gap = column.gap,
        block_gap = block.gap,
        left_width = left.width,
        plot_width = plot.width,
        annotation_width = annotation.width + 0.35
    )
}

rcmetar.metafor.layout <- function(bundle, size, alim) {
    span <- max(diff(alim), 1)
    user.per.inch <- span / size$plot_width
    xlim <- c(
        alim[1] - size$left_width * user.per.inch,
        alim[2] + size$annotation_width * user.per.inch
    )
    column.lefts <- size$study_width + size$block_gap +
        c(0, head(cumsum(size$column_widths + size$column_gap), -1))
    column.centers <- column.lefts + size$column_widths / 2
    ilab.xpos <- xlim[1] + column.centers * user.per.inch

    if (length(bundle$ilab$columns) > 0) {
        column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
        group.xpos <- vapply(bundle$ilab$groups, function(group) {
            mean(ilab.xpos[column.groups == group])
        }, numeric(1))
    } else {
        group.xpos <- numeric(0)
    }

    list(
        xlim = xlim,
        ilab.xpos = ilab.xpos,
        group.xpos = group.xpos
    )
}

rcmetar.open.metafor_device <- function(outpath, size) {
    bg <- "white"
    if (length(grep(".png", outpath)) != 0) {
        grDevices::png(filename=outpath, width=size$width, height=size$height, units="in", res=144, bg=bg)
    } else {
        grDevices::pdf(file=outpath, width=size$width, height=size$height, bg=bg)
    }
}

rcmetar.draw.metafor.forest <- function(bundle, outpath) {
    size <- rcmetar.measure.metafor.forest.device(bundle)
    rcmetar.open.metafor_device(outpath, size)
    on.exit(grDevices::dev.off(), add=TRUE)

    op <- graphics::par(no.readonly=TRUE)
    on.exit(graphics::par(op), add=TRUE)
    graphics::par(bg="white", mar=c(4.8, 1.0, 1.4, 1.0), fg="black", col.axis="black", col.lab="black")

    k <- nrow(bundle$ilab$matrix)
    rows <- seq(from=k, to=1)
    alim <- rcmetar.metafor.alim(bundle)
    layout <- rcmetar.metafor.layout(bundle, size, alim)
    top <- k + 3
    ylim <- c(-1.5, top)
    if (identical(bundle$forest_variant, "subgroup")) {
        rows <- bundle$subgroups$study_rows
        ylim <- bundle$subgroups$ylim
        top <- ylim[2]
    }

    forest.args <- list(
        slab = bundle$slab,
        ilab = if (ncol(bundle$ilab$matrix) > 0) bundle$ilab$matrix else NULL,
        ilab.lab = if (ncol(bundle$ilab$matrix) > 0) bundle$ilab$headers else NULL,
        ilab.xpos = if (ncol(bundle$ilab$matrix) > 0) layout$ilab.xpos else NULL,
        xlim = layout$xlim,
        alim = alim,
        at = rcmetar.metafor.axis.ticks(bundle, alim),
        atransf = rcmetar.metafor.atransf(bundle),
        refline = rcmetar.metafor.refline(bundle),
        xlab = rcmetar.metafor.xlab(bundle),
        cex = size$cex,
        cex.lab = size$cex,
        cex.axis = size$cex,
        header = c(rcmetar.metafor.study.header(bundle), rcmetar.metafor.effect.header(bundle)),
        rows = rows,
        ylim = ylim,
        annotate = TRUE,
        col = "black",
        colshade = "#eeeeee",
        shade = "zebra",
        pch = 15,
        psize = rcmetar.metafor.psize(bundle),
        lwd = 1.35,
        efac = 1.15,
        digits = as.integer(bundle$params$digits)
    )
    forest.args <- forest.args[!vapply(forest.args, is.null, logical(1))]

    if (isTRUE(bundle$single_study)) {
        plot.info <- do.call(metafor::forest.default, c(
            list(
                x = bundle$effect$yi,
                sei = bundle$effect$sei,
                ci.lb = bundle$effect$ci.lb,
                ci.ub = bundle$effect$ci.ub
            ),
            forest.args
        ))
    } else {
        plot.info <- do.call(metafor::forest.rma, c(list(x = bundle$res), c(forest.args, list(mlab="", border="black"))))
    }

    if (identical(bundle$forest_variant, "subgroup")) {
        rcmetar.draw.metafor.subgroups(bundle, layout$xlim[1], size$cex)
    }

    text.y <- if (!is.null(plot.info$ylim)) plot.info$ylim[2] - 0.2 else top - 0.2
    if (length(bundle$ilab$groups) > 0) {
        graphics::text(
            layout$group.xpos,
            text.y,
            bundle$ilab$groups,
            font=2,
            cex=size$cex
        )
    }
    rcmetar.draw.metafor.heterogeneity(bundle, layout$xlim[1], cex=size$cex)

    invisible(bundle$changed.params)
}

rcmetar.draw.metafor.subgroups <- function(bundle, x, cex) {
    for (i in seq_along(bundle$subgroups$names)) {
        label <- bundle$subgroups$names[[i]]
        label.y <- bundle$subgroups$header_rows[[i]]
        graphics::text(
            x,
            label.y,
            label,
            pos=4,
            font=4,
            cex=cex
        )
        metafor::addpoly.rma(
            bundle$subgroups$results[[i]],
            row=bundle$subgroups$polygon_rows[[i]],
            mlab=rcmetar.metafor.model.label("RE Model for Subgroup", bundle$subgroups$results[[i]]),
            cex=cex
        )
    }
    graphics::segments(
        x,
        bundle$subgroups$overall_row + 1,
        par("usr")[2],
        bundle$subgroups$overall_row + 1,
        lwd=1.15
    )
    metafor::addpoly.rma(
        bundle$subgroups$overall,
        row=bundle$subgroups$overall_row,
        mlab=rcmetar.metafor.model.label("RE Model for All Studies", bundle$subgroups$overall),
        cex=cex
    )
    if (!is.null(bundle$subgroups$difference_test)) {
        graphics::text(
            x,
            bundle$subgroups$overall_row - 0.75,
            rcmetar.metafor.subgroup.difference.label(bundle$subgroups$difference_test),
            pos=4,
            cex=cex
        )
    }
    invisible(NULL)
}

rcmetar.metafor.model.label <- function(prefix, res) {
    if (is.null(res$QE)) {
        return(prefix)
    }
    as.expression(bquote(paste(
        .(prefix), " (Q = ", .(round.display(res$QE, 2)),
        ", df = ", .(res$k - res$p), ", ",
        .(rcmetar.metafor.p.value.label(res$QEp)), "; ",
        I^2, " = ", .(round.display(res$I2, 1)), "%, ",
        tau^2, " = ", .(round.display(res$tau2, 2)), ")"
    )))
}

rcmetar.metafor.subgroup.difference.label <- function(test) {
    as.expression(bquote(paste(
        "Test for Subgroup Differences: ", Q[M], " = ",
        .(round.display(test$QM, 2)), ", df = ", .(test$df), ", ",
        .(rcmetar.metafor.p.value.label(test$QMp))
    )))
}

rcmetar.draw.metafor.heterogeneity <- function(bundle, x, cex) {
    if (isTRUE(bundle$single_study) || is.null(bundle$res$QE)) {
        return(invisible(NULL))
    }
    res <- bundle$res
    label <- bquote(paste(
        "RE Model (Q = ", .(round.display(res$QE, 2)),
        ", df = ", .(res$k - res$p), ", ",
        .(rcmetar.metafor.p.value.label(res$QEp)), "; ",
        I^2, " = ", .(round.display(res$I2, 1)), "%, ",
        tau^2, " = ", .(round.display(res$tau2, 2)), ")"
    ))
    graphics::text(x, -1, label, pos=4, cex=cex)
    invisible(NULL)
}

rcmetar.metafor.p.value.label <- function(p.value) {
    if (display.value.is.missing(p.value)) {
        return("p = NA")
    }
    if (p.value < 0.001) {
        return("p < .001")
    }
    paste("p =", round.display(p.value, 3))
}
