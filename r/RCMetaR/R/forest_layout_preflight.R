# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# Style-neutral measurement and planning for metafor-backed forest renderers.

rcmetar.forest.layout.preflight <- function(bundle, style=bundle$fp_style, size.policy="export") {
    style <- if (is.null(style) || length(style) == 0) "default" else as.character(style[[1]])
    if (identical(style, "revman") &&
            inherits(bundle$res, "rma") &&
            !identical(bundle$forest_variant, "subgroup")) {
        return(rcmetar.forest.revman.layout.preflight(bundle, size.policy=size.policy))
    }
    if (identical(style, "bmj") &&
            inherits(bundle$res, "rma") &&
            !identical(bundle$forest_variant, "subgroup")) {
        return(rcmetar.forest.bmj.layout.preflight(bundle, size.policy=size.policy))
    }
    rcmetar.forest.default.layout.preflight(bundle, style=style, size.policy=size.policy)
}

rcmetar.forest.layout.plan <- function(
        style,
        template,
        device,
        typography,
        rows,
        x,
        columns,
        headers,
        footer=list(),
        warnings=list(),
        metrics=list(),
        layout=NULL) {
    if (is.null(layout)) {
        layout <- c(
            list(xlim=x$xlim, alim=x$alim),
            columns[intersect(names(columns), c(
                "ilab.xpos",
                "group.xpos",
                "annotation.xpos",
                "annotation.header.xpos",
                "plot.header.xpos"
            ))]
        )
    }
    structure(
        list(
            style=list(name=style, template=template),
            device=device,
            typography=typography,
            rows=rows,
            x=x,
            columns=columns,
            headers=headers,
            footer=footer,
            warnings=warnings,
            metrics=metrics,
            layout=layout
        ),
        class=c("rcmetar_forest_layout_plan", "list")
    )
}

rcmetar.forest.layout.warning <- function(severity, code, message) {
    list(severity=severity, code=code, message=message)
}

rcmetar.forest.layout.cap.warnings <- function(size, min.cex=0.78, max.width=18, max.height=18) {
    warnings <- list()
    text.floor <- if (!is.null(size$text_floor) && is.finite(size$text_floor)) size$text_floor else min.cex
    if (!is.null(size$cex) && is.finite(size$cex) && size$cex <= text.floor + 1e-8) {
        warnings[[length(warnings) + 1]] <- rcmetar.forest.layout.warning(
            "warning",
            "text-scale-floor",
            "Forest plot text scale reached the minimum readable size."
        )
    }
    if (!is.null(size$width) && is.finite(size$width) && size$width >= max.width - 1e-8) {
        warnings[[length(warnings) + 1]] <- rcmetar.forest.layout.warning(
            "warning",
            "device-width-cap",
            "Forest plot width reached the configured export cap."
        )
    }
    if (!is.null(size$height) && is.finite(size$height) && size$height >= max.height - 1e-8) {
        warnings[[length(warnings) + 1]] <- rcmetar.forest.layout.warning(
            "warning",
            "device-height-cap",
            "Forest plot height reached the configured export cap."
        )
    }
    warnings
}

rcmetar.forest.with.measurement.device <- function(expr) {
    scratch <- rcmetar.scratch.path("INTER")
    grDevices::png(filename=scratch, width=1200, height=800, res=144)
    on.exit(grDevices::dev.off(), add=TRUE)
    force(expr)
}

rcmetar.forest.display.row.count <- function(bundle) {
    if (identical(bundle$forest_variant, "subgroup")) {
        return(length(bundle$subgroups$study_rows) +
            length(bundle$subgroups$header_rows) +
            length(bundle$subgroups$polygon_rows) + 2)
    }
    nrow(bundle$ilab$matrix)
}

rcmetar.forest.is.sequential.variant <- function(bundle) {
    isTRUE(bundle$single_study) &&
        (identical(bundle$forest_variant, "cumulative") ||
            identical(bundle$forest_variant, "leave-one-out"))
}

rcmetar.forest.study.x <- function(layout) {
    if (!is.null(layout$study.xpos) && is.finite(layout$study.xpos)) {
        return(layout$study.xpos)
    }
    layout$xlim[[1]]
}

rcmetar.forest.annotation.x <- function(layout) {
    if (!is.null(layout$annotation.xpos) && is.finite(layout$annotation.xpos)) {
        return(layout$annotation.xpos)
    }
    layout$xlim[[2]]
}

rcmetar.forest.left.block.labels <- function(bundle) {
    labels <- as.list(c(
        bundle$slab,
        rcmetar.metafor.study.header(bundle)
    ))
    labels <- c(
        labels,
        list(rcmetar.metafor.heterogeneity.measure.label(bundle))
    )
    if (identical(bundle$forest_variant, "subgroup")) {
        labels <- c(
            labels,
            as.list(bundle$subgroups$names),
            lapply(
                bundle$subgroups$results,
                function(res) rcmetar.default.model.label("RE Model for Subgroup", res)
            ),
            list(rcmetar.default.model.label("RE Model for All Studies", bundle$subgroups$overall))
        )
        if (!is.null(bundle$subgroups$difference_test)) {
            labels <- c(
                labels,
                list(rcmetar.default.subgroup.difference.label(bundle$subgroups$difference_test))
            )
        }
    }
    Filter(function(label) {
        length(label) > 0 && (is.expression(label) || !all(is.na(label)))
    }, labels)
}

rcmetar.forest.default.device.metrics <- function(bundle) {
    rcmetar.forest.with.measurement.device({
        display.rows <- rcmetar.forest.display.row.count(bundle)
        text.floor <- 0.78
        cex <- max(text.floor, min(1.10, 1.08 - max(display.rows - 10, 0) * 0.018))
        study.width <- max(strwidth(
            c(bundle$slab, rcmetar.metafor.study.header(bundle)),
            units="inches",
            cex=cex
        ), na.rm=TRUE)
        left.block.width <- max(vapply(
            rcmetar.forest.left.block.labels(bundle),
            function(label) max(strwidth(label, units="inches", cex=cex), na.rm=TRUE),
            numeric(1)
        ), na.rm=TRUE)
        column.gap <- 0.34
        block.gap <- 0.78
        plot.width <- 3.5
        if (ncol(bundle$ilab$matrix) > 0) {
            column.widths <- apply(bundle$ilab$matrix, 2, function(col) {
                max(strwidth(c(col, bundle$ilab$headers), units="inches", cex=cex), na.rm=TRUE)
            })
            group.headers <- rcmetar.metafor.group.headers(bundle)
            group.widths <- vapply(group.headers, function(group) {
                lines <- unlist(strsplit(group, "\n", fixed=TRUE), use.names=FALSE)
                max(strwidth(lines, units="inches", cex=cex), na.rm=TRUE)
            }, numeric(1))
            column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
            for (group in bundle$ilab$groups) {
                group.columns <- which(column.groups == group)
                if (length(group.columns) == 0) {
                    next
                }
                current.width <- sum(column.widths[group.columns]) +
                    column.gap * max(length(group.columns) - 1, 0)
                required.width <- group.widths[[group]]
                if (is.finite(required.width) && required.width > current.width) {
                    column.widths[group.columns] <- column.widths[group.columns] +
                        ((required.width - current.width) / length(group.columns))
                }
            }
        } else {
            column.widths <- numeric(0)
            group.widths <- numeric(0)
        }
        annotation.values <- if (rcmetar.param.is.true(bundle$params, "fp_show_annotation", TRUE)) {
            c(rcmetar.metafor.effect.header(bundle), rcmetar.metafor.effect.labels(bundle))
        } else {
            ""
        }
        annotation.width <- max(strwidth(annotation.values, units="inches", cex=cex), na.rm=TRUE)
        ilab.width <- if (length(column.widths) > 0) {
            sum(pmax(column.widths, 0.45)) + column.gap * (length(column.widths) - 1) + block.gap
        } else {
            0
        }
        left.width <- max(
            study.width + block.gap + ilab.width,
            left.block.width + block.gap
        )
        sequential <- rcmetar.forest.is.sequential.variant(bundle)
        vertical.margin <- if (sequential) 1.70 else 3.1
        row.height <- if (sequential) 0.34 else 0.48
        min.height <- if (sequential) 3.90 else 5.0
        list(
            width=max(9.5, min(18, left.width + plot.width + annotation.width + 1.5)),
            height=max(min.height, min(18, vertical.margin + row.height * display.rows)),
            cex=cex,
            text_floor=text.floor,
            bg="white",
            study_width=study.width,
            left_block_width=left.block.width,
            column_widths=pmax(column.widths, 0.45),
            group_widths=group.widths,
            column_gap=column.gap,
            block_gap=block.gap,
            left_width=left.width,
            plot_width=plot.width,
            annotation_width=annotation.width + 0.35,
            display_rows=display.rows
        )
    })
}

rcmetar.forest.default.layout.coordinates <- function(bundle, size, alim) {
    span <- max(diff(alim), 1)
    user.per.inch <- span / size$plot_width
    edge.pad <- 0.18 * span
    base.xlim <- c(
        alim[1] - size$left_width * user.per.inch,
        alim[2] + size$annotation_width * user.per.inch
    )
    xlim <- c(base.xlim[[1]] - edge.pad, base.xlim[[2]] + edge.pad)
    column.lefts <- size$study_width + size$block_gap +
        c(0, head(cumsum(size$column_widths + size$column_gap), -1))
    column.centers <- column.lefts + size$column_widths / 2
    ilab.xpos <- base.xlim[1] + column.centers * user.per.inch

    if (length(bundle$ilab$columns) > 0) {
        column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
        group.xpos <- vapply(bundle$ilab$groups, function(group) {
            mean(ilab.xpos[column.groups == group])
        }, numeric(1))
    } else {
        group.xpos <- numeric(0)
    }

    list(
        xlim=xlim,
        study.xpos=base.xlim[[1]],
        annotation.xpos=base.xlim[[2]],
        ilab.xpos=ilab.xpos,
        group.xpos=group.xpos
    )
}

rcmetar.forest.sequential.rows <- function(k, headers=TRUE) {
    top <- if (isTRUE(headers)) k + 1.7 else k + 0.95
    list(
        k=k,
        study_rows=seq(from=k, to=1),
        ylim=c(-1.05, top),
        top=top,
        manual_sequential_labels=TRUE,
        max_group_header_lines=1
    )
}

rcmetar.forest.default.rows <- function(bundle) {
    k <- nrow(bundle$ilab$matrix)
    rows <- seq(from=k, to=1)
    group.headers <- rcmetar.metafor.group.headers(bundle)
    max.group.header.lines <- if (length(group.headers) > 0) {
        max(vapply(strsplit(group.headers, "\n", fixed=TRUE), length, integer(1)))
    } else {
        1
    }
    manual.sequential.labels <- rcmetar.forest.is.sequential.variant(bundle)
    if (manual.sequential.labels) {
        return(rcmetar.forest.sequential.rows(
            k,
            rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE)
        ))
    }
    header.extra <- if (rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE)) {
        max(0, max.group.header.lines - 1) * 0.55
    } else {
        0
    }
    top <- if (rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE)) k + 3 + header.extra else k + 2.7
    ylim <- c(-1.5, top)
    if (identical(bundle$forest_variant, "subgroup")) {
        rows <- bundle$subgroups$study_rows
        ylim <- bundle$subgroups$ylim
        top <- ylim[2]
    }
    list(
        k=k,
        study_rows=rows,
        ylim=ylim,
        top=top,
        manual_sequential_labels=manual.sequential.labels,
        max_group_header_lines=max.group.header.lines
    )
}

rcmetar.forest.default.layout.preflight <- function(bundle, style="default", size.policy="export") {
    size <- rcmetar.forest.default.device.metrics(bundle)
    size$size_policy <- size.policy
    alim <- if (metric.is.log.scale(as.character(bundle$params$measure))) {
        rcmetar.forest.journal.ratio.alim(bundle)
    } else {
        rcmetar.forest.journal.alim(bundle)
    }
    layout <- rcmetar.forest.default.layout.coordinates(bundle, size, alim)
    rows <- rcmetar.forest.default.rows(bundle)
    group.headers <- rcmetar.metafor.group.headers(bundle)
    header.offset <- if (rows$max_group_header_lines > 1) 0.35 else 0.2
    rcmetar.forest.layout.plan(
        style=style,
        template=if (rows$manual_sequential_labels) "compact" else if (identical(style, "revman")) "compact" else "default",
        device=size,
        typography=list(cex=size$cex, cex.axis=size$cex, cex.lab=size$cex),
        rows=rows,
        x=list(
            xlim=layout$xlim,
            alim=alim,
            at=rcmetar.metafor.axis.ticks(bundle, alim),
            refline=if (identical(style, "revman")) NA else rcmetar.metafor.refline(bundle, alim),
            xlab=rcmetar.metafor.xlab(bundle)
        ),
        columns=list(
            ilab.xpos=layout$ilab.xpos,
            group.xpos=layout$group.xpos,
            annotation.xpos=rcmetar.forest.annotation.x(layout)
        ),
        headers=list(
            group=group.headers,
            show=rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE),
            study=rcmetar.metafor.study.header(bundle),
            effect=rcmetar.metafor.effect.header(bundle),
            offset=header.offset
        ),
        warnings=rcmetar.forest.layout.cap.warnings(size),
        metrics=size,
        layout=layout
    )
}

rcmetar.forest.revman.device.metrics <- function(bundle) {
    k <- length(bundle$slab)
    label.width <- max(nchar(as.character(bundle$slab)), 0)
    column.count <- max(ncol(bundle$ilab$matrix), 0)
    header.width <- max(
        nchar(c(
            bundle$ilab$headers,
            bundle$ilab$groups,
            rcmetar.revman.metric.label(bundle),
            rcmetar.revman.method.label(bundle)
        )),
        0
    )
    text.floor <- if (k <= 16) 0.78 else 0.68
    ratio.axis.reserve <- if (
        metric.is.log.scale(as.character(bundle$params$measure))
    ) 2.75 else 0
    width <- 11.25 + ratio.axis.reserve +
        max(0, label.width - 24) * 0.095 +
        max(0, column.count - 5) * 0.22 +
        max(0, header.width - 16) * 0.045
    height <- max(4.25, 3.05 + 0.25 * k)
    cex <- 0.98 -
        max(0, k - 8) * 0.008 -
        max(0, label.width - 48) * 0.0025 -
        max(0, header.width - 28) * 0.0015
    if (width > 18) {
        cex <- cex * (18 / width)
    }
    list(
        width=min(width, 18),
        height=min(height, 18),
        cex=max(text.floor, cex),
        text_floor=text.floor,
        bg="white",
        display_rows=k,
        label_width=label.width,
        column_count=column.count,
        header_width=header.width
    )
}

rcmetar.forest.has.explicit.axis.bound <- function(bundle, side=c("lower", "upper")) {
    side <- match.arg(side)
    name <- if (identical(side, "lower")) "fp_plot_lb" else "fp_plot_ub"
    value <- bundle$params[[name]]
    !is.null(value) && length(value) > 0 &&
        !is.na(value[[1]]) && !identical(value[[1]], "[default]")
}

rcmetar.forest.has.explicit.axis.bounds <- function(bundle) {
    rcmetar.forest.has.explicit.axis.bound(bundle, "lower") ||
        rcmetar.forest.has.explicit.axis.bound(bundle, "upper")
}

rcmetar.forest.journal.effect.intervals <- function(bundle) {
    yi <- as.numeric(bundle$effect$yi)
    ci.lb <- as.numeric(bundle$effect$ci.lb)
    ci.ub <- as.numeric(bundle$effect$ci.ub)
    if (inherits(bundle$res, "rma")) {
        yi <- as.numeric(bundle$res$yi)
        vi <- as.numeric(bundle$res$vi)
        if (length(yi) == length(vi)) {
            z <- stats::qnorm(
                1 - (1 - as.numeric(bundle$params$conf.level) / 100) / 2
            )
            se <- sqrt(vi)
            ci.lb <- yi - z * se
            ci.ub <- yi + z * se
        }
    }
    list(yi=yi, ci.lb=ci.lb, ci.ub=ci.ub)
}

rcmetar.forest.journal.alim <- function(bundle) {
    effect <- rcmetar.forest.journal.effect.intervals(bundle)
    yi <- effect$yi[is.finite(effect$yi)]
    lower <- effect$ci.lb[is.finite(effect$ci.lb)]
    upper <- effect$ci.ub[is.finite(effect$ci.ub)]
    summary.bounds <- numeric(0)
    if (inherits(bundle$res, "rma")) {
        summary.bounds <- c(bundle$res$ci.lb, bundle$res$ci.ub)
        summary.bounds <- summary.bounds[is.finite(summary.bounds)]
    }
    interval.count <- min(length(lower), length(upper))
    widths <- if (interval.count > 0) upper[seq_len(interval.count)] - lower[seq_len(interval.count)] else numeric(0)
    isolated.extreme <- integer(0)
    if (length(widths) >= 2 && all(is.finite(widths)) && all(widths >= 0)) {
        widest <- which.max(widths)
        typical <- stats::median(widths[-widest])
        if (is.finite(typical) && typical > 0 && widths[[widest]] > 8 * typical) {
            isolated.extreme <- widest
        }
    }
    central.bounds <- if (length(isolated.extreme) == 1) {
        c(lower[-isolated.extreme], upper[-isolated.extreme])
    } else if (length(lower) >= 5 && length(upper) >= 5) {
        trim.count <- max(1, floor(min(length(lower), length(upper)) * 0.10))
        c(
            sort(lower)[[trim.count + 1]],
            sort(upper, decreasing=TRUE)[[trim.count + 1]]
        )
    } else {
        c(lower, upper)
    }
    values <- c(yi, central.bounds, summary.bounds)
    values <- values[is.finite(values)]
    if (length(values) < 2 || diff(range(values)) <= 0) {
        return(rcmetar.metafor.alim(bundle))
    }
    alim <- range(values)
    raw <- rcmetar.metafor.alim(bundle)
    if (rcmetar.forest.has.explicit.axis.bound(bundle, "lower")) alim[[1]] <- raw[[1]]
    if (rcmetar.forest.has.explicit.axis.bound(bundle, "upper")) alim[[2]] <- raw[[2]]
    alim
}

rcmetar.forest.journal.ratio.alim <- function(bundle) {
    base <- rcmetar.forest.journal.alim(bundle)
    lower.explicit <- rcmetar.forest.has.explicit.axis.bound(bundle, "lower")
    upper.explicit <- rcmetar.forest.has.explicit.axis.bound(bundle, "upper")
    include.null <- (!lower.explicit || base[[1]] <= 0) && (!upper.explicit || base[[2]] >= 0)
    observed <- range(c(base, if (include.null) 0 else numeric(0)), finite=TRUE)
    displayed <- exp(observed)
    candidates <- sort(as.vector(outer(c(1, 2, 5), 10^(-8:8))))
    lower <- max(candidates[candidates <= displayed[[1]]], na.rm=TRUE)
    upper <- min(candidates[candidates >= displayed[[2]]], na.rm=TRUE)
    if (!is.finite(lower) || !is.finite(upper) || lower >= upper) {
        return(observed)
    }
    rounded <- log(c(lower, upper))
    if (lower.explicit) rounded[[1]] <- base[[1]]
    if (upper.explicit) rounded[[2]] <- base[[2]]
    rounded
}

rcmetar.forest.journal.ratio.ticks <- function(alim) {
    candidates <- log(sort(as.vector(outer(c(1, 2, 5), 10^(-8:8)))))
    ticks <- candidates[candidates >= alim[[1]] & candidates <= alim[[2]]]
    major <- ticks[abs((ticks / log(10)) - round(ticks / log(10))) < 1e-8]
    if (length(major) >= 3 && length(major) <= 5) {
        return(major)
    }
    if (length(ticks) > 5) {
        indexes <- unique(round(seq(1, length(ticks), length.out=4)))
        ticks <- sort(unique(c(ticks[indexes], 0)))
    }
    ticks
}

rcmetar.forest.revman.layout.coordinates <- function(bundle) {
    if (metric.is.log.scale(as.character(bundle$params$measure))) {
        alim <- rcmetar.forest.journal.ratio.alim(bundle)
    } else {
        alim <- rcmetar.forest.journal.alim(bundle)
    }
    label.extra <- max(0, max(nchar(as.character(bundle$slab)), 0) - 44)
    span <- max(diff(alim), 1)
    if (identical(bundle$data_type, "binary") && length(bundle$ilab$columns) == 5) {
        ilab.xpos <- c(-20.6, -18.6, -16.1, -14.1, -10.8)
        column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
        group.xpos <- c(
            stats::setNames(mean(ilab.xpos[column.groups == bundle$ilab$groups[[1]]]), bundle$ilab$groups[[1]]),
            stats::setNames(mean(ilab.xpos[column.groups == bundle$ilab$groups[[2]]]), bundle$ilab$groups[[2]])
        )
        base.xlim <- c(-30 - label.extra * 0.16, 5.6)
        edge.pad <- 0.20 * span
        return(list(
            xlim=c(base.xlim[[1]] - edge.pad, base.xlim[[2]] + edge.pad),
            study.xpos=base.xlim[[1]],
            alim=alim,
            ilab.xpos=ilab.xpos,
            group.xpos=group.xpos,
            annotation.xpos=-4.7,
            annotation.header.xpos=-6.6,
            plot.header.xpos=mean(alim)
        ))
    }
    if (ncol(bundle$ilab$matrix) == 1) {
        ilab.xpos <- alim[1] - 1.95 * span
        group.xpos <- numeric(0)
        base.xlim <- c(alim[1] - (3.80 + label.extra * 0.030) * span, alim[2] + 0.25 * span)
        edge.pad <- 0.16 * span
        return(list(
            xlim=c(base.xlim[[1]] - edge.pad, base.xlim[[2]] + edge.pad),
            study.xpos=base.xlim[[1]],
            alim=alim,
            ilab.xpos=ilab.xpos,
            group.xpos=group.xpos,
            annotation.xpos=alim[1] - 0.36 * span,
            annotation.header.xpos=alim[1] - 0.78 * span,
            plot.header.xpos=mean(alim)
        ))
    }
    column.count <- max(ncol(bundle$ilab$matrix), 1)
    ilab.left.gap <- if (column.count >= 4) 4.05 else 3.8
    ilab.right.gap <- if (column.count >= 4) 1.80 else 1.55
    ilab.xpos <- seq(alim[1] - ilab.left.gap * span, alim[1] - ilab.right.gap * span, length.out=column.count)
    column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
    group.xpos <- if (length(column.groups) > 0) {
        vapply(bundle$ilab$groups, function(group) {
            mean(ilab.xpos[column.groups == group])
        }, numeric(1))
    } else {
        numeric(0)
    }
    annotation.gap <- if (column.count >= 4) 0.72 else 0.36
    annotation.header.gap <- if (column.count >= 4) 1.02 else 0.78
    base.xlim <- c(alim[1] - (5.15 + label.extra * 0.095) * span, alim[2] + 0.25 * span)
    edge.pad <- 0.16 * span
    list(
        xlim=c(base.xlim[[1]] - edge.pad, base.xlim[[2]] + edge.pad),
        study.xpos=base.xlim[[1]],
        alim=alim,
        ilab.xpos=ilab.xpos,
        group.xpos=group.xpos,
        annotation.xpos=alim[1] - annotation.gap * span,
        annotation.header.xpos=alim[1] - annotation.header.gap * span,
        plot.header.xpos=mean(alim)
    )
}

rcmetar.forest.revman.axis.footer <- function(bundle, layout) {
    if (is.null(layout) || is.null(layout$alim)) {
        layout <- list(alim=graphics::par("usr")[1:2])
    }
    alim <- as.numeric(layout$alim)
    split.x <- 0
    if (!is.finite(split.x) || split.x <= alim[[1]] || split.x >= alim[[2]]) {
        split.x <- mean(alim)
    }
    direction.width <- if (!is.null(layout) && ncol(bundle$ilab$matrix) <= 1) 18 else 22
    direction.y <- if (direction.width <= 18) -4.05 else -3.68
    list(
        left.x=mean(c(alim[[1]], split.x)),
        right.x=mean(c(split.x, alim[[2]])),
        split.x=split.x,
        span=diff(alim),
        axis.x=mean(alim),
        left.max.width=(split.x - alim[[1]]) * 0.92,
        right.max.width=(alim[[2]] - split.x) * 0.92,
        direction.y=direction.y,
        axis.label.y=direction.y,
        direction.width=direction.width
    )
}

rcmetar.forest.revman.layout.preflight <- function(bundle, size.policy="export") {
    size <- rcmetar.forest.revman.device.metrics(bundle)
    size$size_policy <- size.policy
    layout <- rcmetar.forest.revman.layout.coordinates(bundle)
    k <- length(bundle$slab)
    rows <- list(
        k=k,
        study_rows=k:1,
        ylim=c(-5.8, k + 3),
        top=k + 3,
        manual_sequential_labels=FALSE,
        max_group_header_lines=if (length(layout$group.xpos) > 0) 2 else 1
    )
    rcmetar.forest.layout.plan(
        style="revman",
        template=if (ncol(bundle$ilab$matrix) <= 1) "sparse" else "standard",
        device=size,
        typography=list(cex=size$cex, cex.axis=size$cex, cex.lab=size$cex),
        rows=rows,
        x=list(
            xlim=layout$xlim,
            alim=layout$alim,
            at=rcmetar.revman.axis.ticks(bundle, layout$alim),
            refline=NA,
            xlab=""
        ),
        columns=list(
            ilab.xpos=layout$ilab.xpos,
            group.xpos=layout$group.xpos,
            annotation.xpos=layout$annotation.xpos,
            annotation.header.xpos=layout$annotation.header.xpos,
            plot.header.xpos=layout$plot.header.xpos
        ),
        headers=list(
            show=rcmetar.param.is.true(bundle$params, "fp_show_headers", TRUE),
            study=rcmetar.revman.study.header(bundle),
            effect=rcmetar.revman.metric.label(bundle),
            method=rcmetar.revman.method.label(bundle),
            groups=if (length(layout$group.xpos) > 0) names(layout$group.xpos) else character(0)
        ),
        footer=list(axis=rcmetar.forest.revman.axis.footer(bundle, layout)),
        warnings=rcmetar.forest.layout.cap.warnings(size),
        metrics=size,
        layout=layout
    )
}
