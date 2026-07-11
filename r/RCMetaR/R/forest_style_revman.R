# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# RevMan Forest Style templates for the metafor-backed forest renderer.

rcmetar.revman.format.number <- function(values, digits) {
    rcmetar.format.metafor.numeric(values, digits)
}

rcmetar.revman.format.effect.number <- function(values, digits) {
    rcmetar.format.effect.number(values, digits)
}

rcmetar.revman.format.weight <- function(weights, n) {
    if (is.null(weights) || length(weights) == 0 || !any(is.finite(weights))) {
        weights <- rep(100 / max(n, 1), n)
    }
    labels <- rep("", length(weights))
    finite <- is.finite(weights)
    if (any(finite)) {
        labels[finite] <- paste0(round.display(as.numeric(weights[finite]), 1), "%")
    }
    labels
}

rcmetar.revman.ilab <- function(columns, n) {
    matrix <- do.call(cbind, lapply(columns, function(column) column$values))
    if (is.null(matrix)) {
        matrix <- matrix(character(0), nrow=n, ncol=0)
    }
    mode(matrix) <- "character"
    headers <- vapply(columns, function(column) column$header, character(1))
    colnames(matrix) <- headers
    groups <- unique(vapply(columns, function(column) column$group, character(1)))
    groups <- groups[nzchar(groups)]
    list(
        matrix = matrix,
        columns = columns,
        headers = headers,
        groups = groups
    )
}

rcmetar.revman.binary.ilab <- function(binary.data, params, res=NULL) {
    n <- length(binary.data@study.names)
    groups <- rcmetar.revman.arm.labels(params)
    columns <- list()
    if (rcmetar.param.is.true(params, "fp_show_raw_counts", TRUE) &&
            rcmetar.has.binary.raw.columns(binary.data, n, params)) {
        experimental.total <- as.numeric(binary.data@g1O1) + as.numeric(binary.data@g1O2)
        experimental.columns <- list(
            list(key="experimental_events", group=groups[[1]], header="Events", values=rcmetar.format.metafor.raw(binary.data@g1O1)),
            list(key="experimental_total", group=groups[[1]], header="Total", values=rcmetar.format.metafor.raw(experimental.total))
        )
        if (rcmetar.param.is.true(params, "fp_show_col3", TRUE)) {
            columns <- c(columns, experimental.columns)
        }
        if (as.character(params$measure) %in% binary.two.arm.metrics &&
                rcmetar.param.is.true(params, "fp_show_col4", TRUE)) {
            control.total <- as.numeric(binary.data@g2O1) + as.numeric(binary.data@g2O2)
            control.columns <- list(
                list(key="control_events", group=groups[[2]], header="Events", values=rcmetar.format.metafor.raw(binary.data@g2O1)),
                list(key="control_total", group=groups[[2]], header="Total", values=rcmetar.format.metafor.raw(control.total))
            )
            columns <- c(columns, control.columns)
        }
    }
    columns <- c(columns, list(
        list(key="weight", group="", header="Weight", values=rcmetar.revman.format.weight(rcmetar.metafor.weights(res), n))
    ))
    rcmetar.revman.ilab(columns, n)
}

rcmetar.revman.continuous.ilab <- function(cont.data, params, res=NULL) {
    n <- length(cont.data@study.names)
    digits <- as.integer(params$digits)
    groups <- rcmetar.revman.arm.labels(params)
    columns <- list()
    if (rcmetar.param.is.true(params, "fp_show_raw_counts", TRUE) &&
            rcmetar.has.continuous.raw.columns(cont.data, n, params)) {
        if (rcmetar.param.is.true(params, "fp_show_col3", TRUE)) {
            columns <- list(
                list(key="experimental_mean", group=groups[[1]], header="Mean", values=rcmetar.revman.format.number(cont.data@mean1, digits)),
                list(key="experimental_sd", group=groups[[1]], header="SD", values=rcmetar.revman.format.number(cont.data@sd1, digits)),
                list(key="experimental_total", group=groups[[1]], header="Total", values=rcmetar.format.metafor.raw(cont.data@N1))
            )
        }
        if (as.character(params$measure) %in% continuous.two.arm.metrics &&
                rcmetar.param.is.true(params, "fp_show_col4", TRUE)) {
            columns <- c(columns, list(
                list(key="control_mean", group=groups[[2]], header="Mean", values=rcmetar.revman.format.number(cont.data@mean2, digits)),
                list(key="control_sd", group=groups[[2]], header="SD", values=rcmetar.revman.format.number(cont.data@sd2, digits)),
                list(key="control_total", group=groups[[2]], header="Total", values=rcmetar.format.metafor.raw(cont.data@N2))
            ))
        }
    }
    columns <- c(columns, list(
        list(key="weight", group="", header="Weight", values=rcmetar.revman.format.weight(rcmetar.metafor.weights(res), n))
    ))
    rcmetar.revman.ilab(columns, n)
}

rcmetar.revman.diagnostic.ilab <- function(diagnostic.data, params, res=NULL) {
    n <- length(diagnostic.data@study.names)
    columns <- list()
    if (rcmetar.param.is.true(params, "fp_show_raw_counts", TRUE) &&
            rcmetar.has.diagnostic.raw.columns(diagnostic.data, n)) {
        columns <- list(
            list(key="true_positive", group="DTA", header="TP", values=rcmetar.format.metafor.raw(diagnostic.data@TP)),
            list(key="false_positive", group="DTA", header="FP", values=rcmetar.format.metafor.raw(diagnostic.data@FP)),
            list(key="false_negative", group="DTA", header="FN", values=rcmetar.format.metafor.raw(diagnostic.data@FN)),
            list(key="true_negative", group="DTA", header="TN", values=rcmetar.format.metafor.raw(diagnostic.data@TN))
        )
    }
    columns <- c(columns, list(
        list(key="weight", group="", header="Weight", values=rcmetar.revman.format.weight(rcmetar.metafor.weights(res), n))
    ))
    rcmetar.revman.ilab(columns, n)
}

rcmetar.revman.arm.labels <- function(params) {
    labels <- rcmetar.default.arm.labels()
    experimental <- labels[[1]]
    control <- labels[[2]]
    if (!is.null(params$fp_col3_str) && params$fp_col3_str != "[default]") {
        experimental <- as.character(params$fp_col3_str)
    }
    if (!is.null(params$fp_col4_str) && params$fp_col4_str != "[default]") {
        control <- as.character(params$fp_col4_str)
    }
    c(experimental, control)
}

rcmetar.revman.ilab.for.data <- function(om.data, params, res=NULL) {
    if ("BinaryData" %in% class(om.data)) {
        return(rcmetar.revman.binary.ilab(om.data, params, res))
    }
    if ("ContinuousData" %in% class(om.data)) {
        return(rcmetar.revman.continuous.ilab(om.data, params, res))
    }
    if ("DiagnosticData" %in% class(om.data)) {
        return(rcmetar.revman.diagnostic.ilab(om.data, params, res))
    }
    rcmetar.empty.forest.ilab(length(om.data@study.names))
}

rcmetar.revman.test.overall.label <- function(bundle) {
    res <- rcmetar.revman.summary.result(bundle)
    if ((isTRUE(bundle$single_study) && !identical(bundle$forest_variant, "subgroup")) ||
            is.null(res$zval)) {
        return("")
    }
    paste0(
        "Test for overall effect: Z = ", round.display(res$zval, 2),
        " (", rcmetar.revman.p.value.label(res$pval), ")"
    )
}

rcmetar.revman.summary.result <- function(bundle) {
    if (identical(bundle$forest_variant, "subgroup") && !is.null(bundle$subgroups$overall)) {
        return(bundle$subgroups$overall)
    }
    bundle$res
}

rcmetar.revman.heterogeneity.label <- function(bundle) {
    res <- rcmetar.revman.summary.result(bundle)
    if ((isTRUE(bundle$single_study) && !identical(bundle$forest_variant, "subgroup")) ||
            is.null(res$QE)) {
        return("")
    }
    paste0(
        "Heterogeneity: Tau\u00b2 = ", round.display(res$tau2, 2),
        "; Chi\u00b2 = ", round.display(res$QE, 2),
        ", df = ", res$k - res$p,
        " (", rcmetar.revman.p.value.label(res$QEp), "); I\u00b2 = ",
        round.display(res$I2, 0), "%"
    )
}

rcmetar.revman.direction.labels <- function(bundle) {
    measure <- as.character(bundle$params$measure)
    if (identical(bundle$data_type, "diagnostic") ||
            measure %in% c(binary.one.arm.metrics, continuous.one.arm.metrics)) {
        return(list(left="", right="", axis=pretty.metric.name(as.character(bundle$params$measure))))
    }
    labels <- rcmetar.default.arm.labels()
    left <- paste("Favours", labels[[1]])
    right <- paste("Favours", labels[[2]])
    if (!is.null(bundle$params$fp_col3_str) && bundle$params$fp_col3_str != "[default]") {
        left <- paste("Favours", as.character(bundle$params$fp_col3_str))
    }
    if (!is.null(bundle$params$fp_col4_str) && bundle$params$fp_col4_str != "[default]") {
        right <- paste("Favours", as.character(bundle$params$fp_col4_str))
    }
    list(left=left, right=right, axis="")
}

rcmetar.revman.wrap.header <- function(label, width=18) {
    label <- as.character(label)
    wrapped <- strwrap(label, width=width)
    if (length(wrapped) <= 1) {
        return(label)
    }
    paste(wrapped, collapse="\n")
}

rcmetar.revman.wrap.direction <- function(label, width=22) {
    if (is.null(label) || !nzchar(label)) {
        return("")
    }
    if (grepl("^Favours\\s+", label)) {
        arm.label <- sub("^Favours\\s+", "", label)
        arm.lines <- strwrap(arm.label, width=max(18, width - 6))
        return(paste(c("Favours", arm.lines), collapse="\n"))
    }
    rcmetar.revman.wrap.header(label, width=width)
}

rcmetar.revman.p.value.label <- function(p.value) {
    if (display.value.is.missing(p.value)) {
        return("P = NA")
    }
    if (p.value < 0.001) {
        return("P < 0.001")
    }
    paste("P =", format.p.value.display(p.value, RCMETAR_DEFAULT_DISPLAY_DIGITS))
}

rcmetar.revman.decorate.bundle <- function(bundle) {
    directions <- rcmetar.revman.direction.labels(bundle)
    bundle$slab <- gsub(", ([0-9]{4})$", " \\1", bundle$slab)
    if (!is.null(bundle$effect$slab)) {
        bundle$effect$slab <- gsub(", ([0-9]{4})$", " \\1", bundle$effect$slab)
    }
    not.estimable <- rcmetar.revman.not_estimable(bundle)
    weight.index <- rcmetar.revman.column.index(bundle, "weight")
    if (any(not.estimable) && length(weight.index) == 1) {
        bundle$ilab$matrix[not.estimable, weight.index] <- ""
    }
    bundle$style_blocks <- list(
        heterogeneity = rcmetar.revman.heterogeneity.label(bundle),
        test_overall = rcmetar.revman.test.overall.label(bundle),
        totals = rcmetar.revman.total.values(bundle),
        total_events = rcmetar.revman.total.events(bundle),
        not_estimable = not.estimable,
        favours_left = directions$left,
        favours_right = directions$right,
        axis_label = directions$axis
    )
    bundle
}

rcmetar.revman.column.index <- function(bundle, key) {
    keys <- vapply(bundle$ilab$columns, function(column) column$key, character(1))
    which(keys == key)
}

rcmetar.revman.total.values <- function(bundle) {
    totals <- list()
    for (key in c("experimental_total", "control_total")) {
        index <- rcmetar.revman.column.index(bundle, key)
        if (length(index) == 1 && rcmetar.raw.values.complete(bundle$ilab$matrix[, index])) {
            totals[[key]] <- sum(suppressWarnings(as.numeric(bundle$ilab$matrix[, index])))
        }
    }
    weight.index <- rcmetar.revman.column.index(bundle, "weight")
    if (length(weight.index) == 1) {
        totals[["weight"]] <- "100.0%"
    }
    totals
}

rcmetar.revman.total.events <- function(bundle) {
    if (!identical(bundle$data_type, "binary")) {
        return(list())
    }
    events <- list()
    for (key in c("experimental_events", "control_events")) {
        index <- rcmetar.revman.column.index(bundle, key)
        if (length(index) == 1 && rcmetar.raw.values.complete(bundle$ilab$matrix[, index])) {
            events[[key]] <- sum(suppressWarnings(as.numeric(bundle$ilab$matrix[, index])))
        }
    }
    events
}

rcmetar.revman.not_estimable <- function(bundle) {
    if (!identical(bundle$data_type, "binary")) {
        return(rep(FALSE, nrow(bundle$ilab$matrix)))
    }
    experimental.total <- rcmetar.revman.column.index(bundle, "experimental_total")
    control.total <- rcmetar.revman.column.index(bundle, "control_total")
    if (length(experimental.total) != 1 || length(control.total) != 1) {
        return(rep(FALSE, nrow(bundle$ilab$matrix)))
    }
    exp.total <- suppressWarnings(as.numeric(bundle$ilab$matrix[, experimental.total]))
    ctrl.total <- suppressWarnings(as.numeric(bundle$ilab$matrix[, control.total]))
    ifelse(is.na(exp.total) | is.na(ctrl.total), FALSE, exp.total + ctrl.total == 0)
}

rcmetar.revman.xlab <- function(bundle) {
    if (identical(bundle$data_type, "diagnostic")) {
        return(pretty.metric.name(as.character(bundle$params$measure)))
    }
    ""
}

rcmetar.revman.metric.label <- function(bundle) {
    label <- pretty.metric.name(as.character(bundle$params$measure))
    if (identical(label, "Odds Ratio")) {
        return("Odds ratio")
    }
    if (identical(label, "Risk Ratio")) {
        return("Risk ratio")
    }
    label
}

rcmetar.revman.study.header <- function(bundle) {
    if (!rcmetar.param.is.true(bundle$params, "fp_show_col1", TRUE)) {
        return("")
    }
    rcmetar.forest.study.header.label(bundle$params$fp_col1_str)
}

rcmetar.draw.revman.forest <- function(bundle, outpath) {
    if (!inherits(bundle$res, "rma") && isTRUE(bundle$single_study)) {
        return(rcmetar.draw.revman.sequential.forest(bundle, outpath))
    }
    if (!inherits(bundle$res, "rma") || identical(bundle$forest_variant, "subgroup")) {
        return(rcmetar.draw.default.metafor.forest(within(bundle, fp_style <- "default"), outpath))
    }

    plan <- rcmetar.forest.layout.preflight(bundle, style="revman")
    size <- plan$device
    display.path <- rcmetar.plot.display_path_for_bundle(bundle, outpath, "fp")
    rcmetar.render.plot_file(outpath, size, function() {

    op <- graphics::par(no.readonly=TRUE)
    on.exit(graphics::par(op), add=TRUE)
    old.options <- options(na.action="na.pass")
    on.exit(options(old.options), add=TRUE)
    graphics::par(
        bg="white",
        mar=c(1.0, 0, 1.8, 1.0),
        mgp=c(3, 0.2, 0),
        tcl=-0.2,
        fg="black",
        col.axis="black",
        col.lab="black"
    )

    layout <- plan$layout
    effect <- rcmetar.revman.study.effects(bundle)
    summary <- rcmetar.revman.summary.effect(bundle)
    bundle$style_blocks$heterogeneity <- rcmetar.revman.heterogeneity.label(within(bundle, res <- summary$res))
    bundle$style_blocks$test_overall <- rcmetar.revman.test.overall.label(within(bundle, res <- summary$res))
    ilab <- rcmetar.revman.display.ilab(bundle, summary$weights)
    method <- rcmetar.revman.method.label(bundle)
    metric <- rcmetar.revman.metric.label(bundle)
    k <- plan$rows$k
    rows <- plan$rows$study_rows
    show.headers <- plan$headers$show

    plot.info <- suppressWarnings(metafor::forest.default(
        x=effect$yi,
        vi=effect$vi,
        ci.lb=effect$ci.lb,
        ci.ub=effect$ci.ub,
        slab=rep("", length(bundle$slab)),
        atransf=rcmetar.metafor.atransf(bundle),
        at=plan$x$at,
        xlim=plan$x$xlim,
        alim=plan$x$alim,
        xlab="",
        xaxt="n",
        efac=0,
        textpos=c(rcmetar.forest.study.x(layout), layout$annotation.xpos),
        lty=c(1, 1, 0),
        refline=NA,
        ilab=ilab$matrix,
        ilab.xpos=layout$ilab.xpos,
        ilab.pos=NULL,
        cex=plan$typography$cex,
        cex.lab=plan$typography$cex.lab,
        cex.axis=plan$typography$cex.axis,
        header=FALSE,
        pch=15,
        psize=summary$psize,
        col=rcmetar.forest.accent.color(bundle$params),
        annotate=FALSE,
        ylim=plan$rows$ylim,
        rows=rows
    ))

    graphics::par(xpd=NA)
    rcmetar.draw.metafor.effect.accent(
        effect=effect,
        rows=rows,
        alim=layout$alim,
        color=rcmetar.forest.accent.color(bundle$params),
        psize=summary$psize,
        lwd=1.15
    )
    graphics::segments(plot.info$xlim[1], k + 1, plot.info$xlim[2], k + 1, lwd=0.8)
    graphics::segments(0, -2, 0, k + 1, lwd=0.8)

    graphics::par(cex=plot.info$cex, font=2)
    if (show.headers) {
        graphics::text(rcmetar.forest.study.x(layout), k + 2, rcmetar.revman.study.header(bundle), pos=4)
        graphics::text(layout$ilab.xpos, k + 2, ilab$headers)
    }
    if (show.headers && length(layout$group.xpos) > 0) {
        graphics::text(layout$group.xpos, k + 3, vapply(names(layout$group.xpos), rcmetar.revman.wrap.header, character(1)))
    }
    if (show.headers) {
        method.header <- paste0(method, ",\n", bundle$params$conf.level, "% CI")
        graphics::text(layout$annotation.xpos, k + 3, metric, pos=2)
        graphics::text(layout$annotation.xpos, k + 2, method.header, pos=2)
        graphics::text(layout$plot.header.xpos, k + 3, metric)
        graphics::text(layout$plot.header.xpos, k + 2, method.header)
    }

    graphics::rect(layout$annotation.xpos, -1.5, layout$ilab.xpos[[length(layout$ilab.xpos)]], -0.5, col="white", border=NA)
    graphics::text(layout$annotation.xpos, -1, summary$label, pos=2)
    rcmetar.draw.revman.summary.diamond(summary, -1, rcmetar.forest.accent.color(bundle$params))
    rcmetar.draw.revman.axis(bundle, layout, plot.info$cex)

    graphics::par(cex=plot.info$cex, font=1)
    graphics::text(rcmetar.forest.study.x(layout), rows, bundle$slab, pos=4, cex=plot.info$cex, col="black")
    rcmetar.draw.revman.study.effect.labels(bundle, effect, layout, rows, plot.info$cex)
    rcmetar.draw.revman.bottom.blocks(bundle, rcmetar.forest.study.x(layout), plot.info$cex, layout)

    invisible(bundle$changed.params)
    }, display.path=display.path)
}

rcmetar.draw.revman.sequential.forest <- function(bundle, outpath) {
    style <- if (identical(bundle$fp_style, "bmj")) "bmj" else "revman"
    plan <- rcmetar.forest.layout.preflight(bundle, style=style)
    size <- plan$device
    size$bg <- "white"
    display.path <- rcmetar.plot.display_path_for_bundle(bundle, outpath, "fp")
    rcmetar.render.plot_file(outpath, size, function() {

    op <- graphics::par(no.readonly=TRUE)
    on.exit(graphics::par(op), add=TRUE)
    bottom.margin <- if (nzchar(plan$x$xlab)) 3.1 else 2.15
    graphics::par(
        bg="white",
        mar=c(bottom.margin, 0.8, 0.9, 0.8),
        fg="black",
        col.axis="black",
        col.lab="black",
        mgp=c(2.2, 0.45, 0),
        tcl=-0.25
    )

    k <- plan$rows$k
    rows <- plan$rows$study_rows
    alim <- plan$x$alim
    layout <- plan$layout
    compact.pch <- if (identical(style, "bmj")) 18 else 15
    compact.lwd <- if (identical(style, "bmj")) 1.25 else 1.15
    plot.info <- suppressWarnings(metafor::forest.default(
        x=bundle$effect$yi,
        sei=bundle$effect$sei,
        ci.lb=bundle$effect$ci.lb,
        ci.ub=bundle$effect$ci.ub,
        slab=rep("", length(bundle$slab)),
        xlim=plan$x$xlim,
        alim=plan$x$alim,
        at=plan$x$at,
        atransf=rcmetar.metafor.atransf(bundle),
        refline=plan$x$refline,
        xlab=plan$x$xlab,
        cex=plan$typography$cex,
        cex.lab=plan$typography$cex.lab,
        cex.axis=plan$typography$cex.axis,
        header=FALSE,
        rows=rows,
        ylim=plan$rows$ylim,
        annotate=FALSE,
        col=rcmetar.forest.accent.color(bundle$params),
        pch=compact.pch,
        psize=rcmetar.metafor.psize(bundle),
        lty=rcmetar.metafor.forest.line.types(plan),
        lwd=compact.lwd,
        efac=0,
        digits=as.integer(bundle$params$digits)
    ))
    rcmetar.draw.metafor.single.study.accent(
        bundle,
        rows,
        alim,
        rcmetar.forest.accent.color(bundle$params),
        pch=compact.pch
    )
    rcmetar.draw.metafor.sequential.text(bundle, rows, layout, k, plan$typography$cex)
    invisible(bundle$changed.params)
    }, display.path=display.path)
}

rcmetar.revman.method.label <- function(bundle) {
    if (!is.null(bundle$params$rm.method) && bundle$params$rm.method != "FE") {
        return("IV, Random")
    }
    "IV, Fixed"
}

rcmetar.revman.axis.ticks <- function(bundle, alim) {
    params <- bundle$params
    if (!is.null(params$fp_xticks) &&
            !identical(params$fp_xticks[1], "[default]") &&
            !all(is.na(params$fp_xticks))) {
        return(rcmetar.metafor.axis.ticks(bundle, alim))
    }
    if (metric.is.log.scale(as.character(bundle$params$measure))) {
        return(rcmetar.forest.journal.ratio.ticks(alim))
    }
    ticks <- pretty(alim, n=4)
    ticks[ticks >= alim[1] & ticks <= alim[2]]
}

rcmetar.revman.layout <- function(bundle) {
    rcmetar.forest.revman.layout.coordinates(bundle)
}

rcmetar.revman.study.effects <- function(bundle) {
    yi <- as.numeric(bundle$res$yi)
    vi <- as.numeric(bundle$res$vi)
    z <- stats::qnorm(1 - (1 - as.numeric(bundle$params$conf.level) / 100) / 2)
    effect <- list(
        yi=yi,
        vi=vi,
        ci.lb=yi - z * sqrt(vi),
        ci.ub=yi + z * sqrt(vi)
    )
    not.estimable <- bundle$style_blocks$not_estimable
    if (length(not.estimable) == length(effect$yi) && any(not.estimable)) {
        effect$yi[not.estimable] <- NA
        effect$vi[not.estimable] <- NA
        effect$ci.lb[not.estimable] <- NA
        effect$ci.ub[not.estimable] <- NA
    }
    effect
}

rcmetar.revman.summary.effect <- function(bundle) {
    not.estimable <- bundle$style_blocks$not_estimable
    keep <- rep(TRUE, length(bundle$res$yi))
    if (length(not.estimable) == length(keep)) {
        keep <- !not.estimable
    }
    keep <- keep & is.finite(bundle$res$yi) & is.finite(bundle$res$vi)
    res <- bundle$res
    if (any(!keep) && sum(keep) > 0) {
        refit <- try(metafor::rma.uni(
            yi=bundle$res$yi[keep],
            vi=bundle$res$vi[keep],
            method=bundle$params$rm.method,
            level=bundle$params$conf.level,
            digits=bundle$params$digits
        ), silent=TRUE)
        if (!inherits(refit, "try-error")) {
            res <- refit
        }
    }
    weights <- rep(NA_real_, length(bundle$res$yi))
    if (sum(keep) > 0) {
        weights[keep] <- as.numeric(weights(res))
    }
    transform <- rcmetar.bundle.transform(bundle)
    pred <- c(transform$display.scale(res$b), transform$display.scale(res$ci.lb), transform$display.scale(res$ci.ub))
    psize <- rep(NA_real_, length(weights))
    finite.weights <- is.finite(weights)
    if (any(finite.weights)) {
        psize[finite.weights] <- 0.55 + 0.85 * sqrt(weights[finite.weights] / max(weights[finite.weights]))
    }
    list(
        res=res,
        yi=as.numeric(res$b),
        ci.lb=as.numeric(res$ci.lb),
        ci.ub=as.numeric(res$ci.ub),
        weights=weights,
        psize=psize,
        label=paste0(
            rcmetar.revman.format.effect.number(pred[[1]], bundle$params$digits),
            " [",
            rcmetar.revman.format.effect.number(pred[[2]], bundle$params$digits),
            ", ",
            rcmetar.revman.format.effect.number(pred[[3]], bundle$params$digits),
            "]"
        )
    )
}

rcmetar.revman.display.ilab <- function(bundle, weights) {
    ilab <- bundle$ilab
    weight.index <- rcmetar.revman.column.index(bundle, "weight")
    if (length(weight.index) == 1 && length(weights) == nrow(ilab$matrix)) {
        ilab$matrix[, weight.index] <- rcmetar.revman.format.weight(weights, length(weights))
    }
    ilab
}

rcmetar.draw.revman.study.effect.labels <- function(bundle, effect, layout, rows, cex) {
    transform <- rcmetar.bundle.transform(bundle)
    labels <- rep("Not estimable", length(effect$yi))
    finite <- is.finite(effect$yi) & is.finite(effect$ci.lb) & is.finite(effect$ci.ub)
    if (any(finite)) {
        labels[finite] <- paste0(
            rcmetar.revman.format.effect.number(transform$display.scale(effect$yi[finite]), bundle$params$digits),
            " [",
            rcmetar.revman.format.effect.number(transform$display.scale(effect$ci.lb[finite]), bundle$params$digits),
            ", ",
            rcmetar.revman.format.effect.number(transform$display.scale(effect$ci.ub[finite]), bundle$params$digits),
            "]"
        )
    }
    graphics::text(layout$annotation.xpos, rows, labels, pos=2, cex=cex)
}

rcmetar.draw.revman.summary.diamond <- function(summary, row, color="black") {
    graphics::polygon(
        x=c(summary$ci.lb, summary$yi, summary$ci.ub, summary$yi),
        y=c(row, row + 0.32, row, row - 0.32),
        col=color,
        border=color
    )
}

rcmetar.draw.revman.axis <- function(bundle, layout, cex) {
    ticks <- rcmetar.revman.axis.ticks(bundle, layout$alim)
    labels <- rcmetar.revman.axis.labels(bundle, ticks)
    y.axis <- -2.3
    y.tick <- -2.12
    y.label <- -2.78
    span <- max(diff(layout$alim), 1)
    graphics::rect(layout$alim[[1]] - 0.04 * span, -5.4, layout$alim[[2]] + 0.04 * span, -2.05, col="white", border=NA)
    graphics::segments(layout$alim[[1]], y.axis, layout$alim[[2]], y.axis, lwd=0.8)
    graphics::segments(ticks, y.axis, ticks, y.tick, lwd=0.8)
    graphics::text(ticks, y.label, labels, cex=cex)
    invisible(NULL)
}

rcmetar.revman.axis.labels <- function(bundle, ticks) {
    measure <- as.character(bundle$params$measure)
    if (metric.is.log.scale(measure)) {
        return(formatC(exp(ticks), digits=3, format="fg"))
    }
    values <- rcmetar.bundle.transform(bundle)$display.scale(ticks)
    digits <- if (metric.is.logit.scale(measure)) 2 else max(0, min(2, as.integer(bundle$params$digits)))
    rcmetar.revman.format.effect.number(values, digits)
}

rcmetar.revman.axis.footer.layout <- function(bundle, layout) {
    rcmetar.forest.revman.axis.footer(bundle, layout)
}

rcmetar.revman.constrained.direction.label <- function(label, cex, max.width, preferred.width) {
    widths <- sort(unique(pmax(18, c(preferred.width, 24, 22, 20, 18))), decreasing=TRUE)
    for (width in widths) {
        wrapped <- rcmetar.revman.wrap.direction(label, width)
        lines <- unlist(strsplit(wrapped, "\n", fixed=TRUE), use.names=FALSE)
        if (length(lines) == 0 || length(lines) <= 3 ||
                max(graphics::strwidth(lines, units="user", cex=cex), na.rm=TRUE) <= max.width) {
            return(wrapped)
        }
    }
    rcmetar.revman.wrap.direction(label, 18)
}

rcmetar.revman.line.count <- function(label) {
    if (is.null(label) || !nzchar(label)) {
        return(0)
    }
    length(strsplit(label, "\n", fixed=TRUE)[[1]])
}

rcmetar.measure.revman.forest.device <- function(bundle) {
    rcmetar.forest.revman.device.metrics(bundle)
}

rcmetar.draw.revman.bottom.blocks <- function(bundle, x, cex, layout=NULL) {
    graphics::par(xpd=NA)
    if (!is.null(layout)) {
        rcmetar.draw.revman.total.row(bundle, x, layout, cex)
    }
    if (length(bundle$style_blocks$total_events) > 0 && !is.null(layout)) {
        graphics::text(x, -2, "Total events:", pos=4, cex=cex)
        event.keys <- c("experimental_events", "control_events")
        for (key in event.keys) {
            index <- rcmetar.revman.column.index(bundle, key)
            if (length(index) == 1 && !is.null(bundle$style_blocks$total_events[[key]])) {
                graphics::text(layout$ilab.xpos[[index]], -2, bundle$style_blocks$total_events[[key]], cex=cex)
            }
        }
    }
    if (nzchar(bundle$style_blocks$heterogeneity)) {
        graphics::text(x, -3, bundle$style_blocks$heterogeneity, pos=4, cex=cex)
    }
    if (nzchar(bundle$style_blocks$test_overall)) {
        graphics::text(x, -4, bundle$style_blocks$test_overall, pos=4, cex=cex)
    }
    axis.footer <- rcmetar.revman.axis.footer.layout(bundle, layout)
    left.label <- ""
    right.label <- ""
    if (nzchar(bundle$style_blocks$favours_left)) {
        left.label <- rcmetar.revman.constrained.direction.label(
            bundle$style_blocks$favours_left,
            cex,
            axis.footer$left.max.width,
            axis.footer$direction.width
        )
    }
    if (nzchar(bundle$style_blocks$favours_right)) {
        right.label <- rcmetar.revman.constrained.direction.label(
            bundle$style_blocks$favours_right,
            cex,
            axis.footer$right.max.width,
            axis.footer$direction.width
        )
    }
    direction.y <- axis.footer$direction.y -
        max(0, max(rcmetar.revman.line.count(left.label), rcmetar.revman.line.count(right.label)) - 2) * 0.36
    label.wraps.deeply <- max(rcmetar.revman.line.count(left.label), rcmetar.revman.line.count(right.label)) > 2
    left.x <- axis.footer$left.x
    right.x <- axis.footer$right.x
    left.adj <- 0.5
    right.adj <- 0.5
    if (label.wraps.deeply || (nzchar(left.label) && nzchar(right.label))) {
        label.gap <- max(axis.footer$span * 0.035, 0.08)
        left.x <- axis.footer$split.x - label.gap
        right.x <- axis.footer$split.x + label.gap
        left.adj <- 1
        right.adj <- 0
    }
    if (nzchar(bundle$style_blocks$favours_left)) {
        graphics::text(
            left.x,
            direction.y,
            left.label,
            cex=cex,
            adj=left.adj
        )
    }
    if (nzchar(bundle$style_blocks$favours_right)) {
        graphics::text(
            right.x,
            direction.y,
            right.label,
            cex=cex,
            adj=right.adj
        )
    }
    if (nzchar(bundle$style_blocks$axis_label)) {
        graphics::text(axis.footer$axis.x, axis.footer$axis.label.y, bundle$style_blocks$axis_label, cex=cex)
    }
    invisible(NULL)
}

rcmetar.draw.revman.total.row <- function(bundle, x, layout, cex) {
    graphics::text(x, -1, paste0("Total (", bundle$params$conf.level, "% CI)"), pos=4, font=2, cex=cex)
    for (key in names(bundle$style_blocks$totals)) {
        index <- rcmetar.revman.column.index(bundle, key)
        if (length(index) == 1) {
            graphics::text(layout$ilab.xpos[[index]], -1, bundle$style_blocks$totals[[key]], font=2, cex=cex)
        }
    }
    invisible(NULL)
}
