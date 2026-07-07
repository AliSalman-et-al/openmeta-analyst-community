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

rcmetar.binary.default.ilab <- function(binary.data, params) {
    columns <- list(
        list(key="experimental_events", group="Experimental", header="Events", values=binary.data@g1O1),
        list(key="experimental_total", group="Experimental", header="Total", values=binary.data@g1O1 + binary.data@g1O2),
        list(key="control_events", group="Control", header="Events", values=binary.data@g2O1),
        list(key="control_total", group="Control", header="Total", values=binary.data@g2O1 + binary.data@g2O2)
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
    label
}

rcmetar.metafor.effect.header <- function(bundle) {
    paste0(pretty.metric.name(as.character(bundle$params$measure)), " [", bundle$params$conf.level, "% CI]")
}

rcmetar.metafor.alim <- function(bundle) {
    if (!is.null(bundle$plot_range) && length(bundle$plot_range) == 2 && all(is.finite(bundle$plot_range))) {
        return(as.numeric(bundle$plot_range))
    }
    values <- c(bundle$res$yi, bundle$res$ci.lb, bundle$res$ci.ub, bundle$effect$yi, bundle$effect$ci.lb, bundle$effect$ci.ub)
    values <- values[is.finite(values)]
    if (length(values) == 0) {
        return(c(-1, 1))
    }
    range(values)
}

rcmetar.metafor.effect.labels <- function(bundle) {
    legacy <- bundle$legacy_plot_data
    digits <- as.integer(bundle$params$digits)
    if (!is.null(legacy$effects.disp)) {
        y <- legacy$effects.disp$y.disp
        lb <- legacy$effects.disp$lb.disp
        ub <- legacy$effects.disp$ub.disp
    } else if (isTRUE(bundle$single_study)) {
        transform <- binary.transform.f(as.character(bundle$params$measure))
        y <- transform$display.scale(bundle$effect$yi)
        lb <- transform$display.scale(bundle$effect$ci.lb)
        ub <- transform$display.scale(bundle$effect$ci.ub)
    } else {
        transform <- binary.transform.f(as.character(bundle$params$measure))
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
    cex <- max(0.62, min(1.05, 1.08 - max(k - 8, 0) * 0.025))
    study.width <- max(strwidth(c(bundle$slab, as.character(bundle$params$fp_col1_str)), units="inches", cex=cex), na.rm=TRUE)
    column.widths <- apply(bundle$ilab$matrix, 2, function(col) {
        max(strwidth(c(col, bundle$ilab$headers), units="inches", cex=cex), na.rm=TRUE)
    })
    group.widths <- vapply(bundle$ilab$groups, function(group) strwidth(group, units="inches", cex=cex), numeric(1))
    annotation.width <- max(strwidth(c(rcmetar.metafor.effect.header(bundle), rcmetar.metafor.effect.labels(bundle)), units="inches", cex=cex), na.rm=TRUE)
    column.gap <- 0.32
    block.gap <- 0.7
    plot.width <- 3.2
    left.width <- study.width + block.gap + sum(pmax(column.widths, 0.45)) + column.gap * (length(column.widths) - 1) + block.gap

    list(
        width = max(8.5, min(14, left.width + plot.width + annotation.width + 1.4)),
        height = max(5.2, min(18, 3.0 + 0.52 * k)),
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

    column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
    group.xpos <- vapply(bundle$ilab$groups, function(group) {
        mean(ilab.xpos[column.groups == group])
    }, numeric(1))

    list(
        xlim = xlim,
        ilab.xpos = ilab.xpos,
        group.xpos = group.xpos
    )
}

rcmetar.open.metafor_device <- function(outpath, size) {
    bg <- "#d9d9d9"
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
    graphics::par(bg="#d9d9d9", mar=c(4.8, 1.0, 1.6, 1.0), fg="black", col.axis="black", col.lab="black")

    k <- nrow(bundle$ilab$matrix)
    rows <- seq(from=k, to=1)
    alim <- rcmetar.metafor.alim(bundle)
    layout <- rcmetar.metafor.layout(bundle, size, alim)
    top <- k + 3

    forest.args <- list(
        slab = bundle$slab,
        ilab = bundle$ilab$matrix,
        ilab.lab = bundle$ilab$headers,
        ilab.xpos = layout$ilab.xpos,
        xlim = layout$xlim,
        alim = alim,
        at = rcmetar.metafor.axis.ticks(bundle, alim),
        atransf = rcmetar.metafor.atransf(bundle),
        refline = rcmetar.metafor.refline(bundle),
        xlab = rcmetar.metafor.xlab(bundle),
        cex = size$cex,
        cex.lab = size$cex,
        cex.axis = size$cex,
        header = c(as.character(bundle$params$fp_col1_str), rcmetar.metafor.effect.header(bundle)),
        rows = rows,
        ylim = c(-1.5, top),
        annotate = TRUE,
        col = "black",
        colshade = "#c9c9c9",
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
        plot.info <- do.call(metafor::forest.rma, c(list(x = bundle$res), c(forest.args, list(mlab="", shade="zebra", border="black"))))
    }

    text.y <- if (!is.null(plot.info$ylim)) plot.info$ylim[2] - 0.2 else top - 0.2
    graphics::text(
        layout$group.xpos,
        text.y,
        bundle$ilab$groups,
        font=2,
        cex=size$cex
    )
    rcmetar.draw.metafor.heterogeneity(bundle, layout$xlim[1], cex=size$cex)

    invisible(bundle$changed.params)
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
