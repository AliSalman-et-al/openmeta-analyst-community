# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# BMJ Forest Style templates for the metafor-backed forest renderer.

rcmetar.bmj.format.weight <- function(weights, n) {
    if (is.null(weights) || length(weights) == 0 || !any(is.finite(weights))) {
        weights <- rep(100 / max(n, 1), n)
    }
    labels <- rep("", length(weights))
    finite <- is.finite(weights)
    if (any(finite)) {
        labels[finite] <- round.display(as.numeric(weights[finite]), 1)
    }
    labels
}

rcmetar.bmj.combined.count <- function(events, totals) {
    events <- suppressWarnings(as.numeric(events))
    totals <- suppressWarnings(as.numeric(totals))
    ifelse(
        is.finite(events) & is.finite(totals),
        paste(rcmetar.format.metafor.raw(events), rcmetar.format.metafor.raw(totals), sep=" / "),
        ""
    )
}

rcmetar.bmj.ilab <- function(columns, n) {
    matrix <- do.call(cbind, lapply(columns, function(column) column$values))
    if (is.null(matrix)) {
        matrix <- matrix(character(0), nrow=n, ncol=0)
    }
    mode(matrix) <- "character"
    headers <- vapply(columns, function(column) column$header, character(1))
    colnames(matrix) <- headers
    groups <- unique(vapply(columns, function(column) column$group, character(1)))
    groups <- groups[nzchar(groups)]
    list(matrix=matrix, columns=columns, headers=headers, groups=groups)
}

rcmetar.bmj.binary.ilab <- function(binary.data, params, res=NULL) {
    n <- length(binary.data@study.names)
    groups <- rcmetar.revman.arm.labels(params)
    columns <- list()
    if (rcmetar.param.is.true(params, "fp_show_raw_counts", TRUE) &&
            rcmetar.has.binary.raw.columns(binary.data, n)) {
        experimental.total <- as.numeric(binary.data@g1O1) + as.numeric(binary.data@g1O2)
        control.total <- as.numeric(binary.data@g2O1) + as.numeric(binary.data@g2O2)
        experimental.columns <- list(
            list(
                key="experimental_events_total",
                group=groups[[1]],
                header="",
                values=rcmetar.bmj.combined.count(binary.data@g1O1, experimental.total)
            )
        )
        control.columns <- list(
            list(
                key="control_events_total",
                group=groups[[2]],
                header="",
                values=rcmetar.bmj.combined.count(binary.data@g2O1, control.total)
            )
        )
        if (rcmetar.param.is.true(params, "fp_show_col3", TRUE)) {
            columns <- c(columns, experimental.columns)
        }
        if (rcmetar.param.is.true(params, "fp_show_col4", TRUE)) {
            columns <- c(columns, control.columns)
        }
    }
    columns <- c(columns, list(
        list(key="weight", group="", header="Weight", values=rcmetar.bmj.format.weight(rcmetar.metafor.weights(res), n))
    ))
    rcmetar.bmj.ilab(columns, n)
}

rcmetar.bmj.continuous.ilab <- function(cont.data, params, res=NULL) {
    n <- length(cont.data@study.names)
    digits <- as.integer(params$digits)
    groups <- rcmetar.revman.arm.labels(params)
    columns <- list()
    if (rcmetar.param.is.true(params, "fp_show_raw_counts", TRUE) &&
            rcmetar.has.continuous.raw.columns(cont.data, n, params)) {
        if (rcmetar.param.is.true(params, "fp_show_col3", TRUE)) {
            columns <- list(
                list(key="experimental_total", group=groups[[1]], header="Total", values=rcmetar.format.metafor.raw(cont.data@N1)),
                list(key="experimental_mean", group=groups[[1]], header="Mean", values=rcmetar.revman.format.number(cont.data@mean1, digits)),
                list(key="experimental_sd", group=groups[[1]], header="SD", values=rcmetar.revman.format.number(cont.data@sd1, digits))
            )
        }
        if (as.character(params$measure) %in% continuous.two.arm.metrics &&
                rcmetar.param.is.true(params, "fp_show_col4", TRUE)) {
            columns <- c(columns, list(
                list(key="control_total", group=groups[[2]], header="Total", values=rcmetar.format.metafor.raw(cont.data@N2)),
                list(key="control_mean", group=groups[[2]], header="Mean", values=rcmetar.revman.format.number(cont.data@mean2, digits)),
                list(key="control_sd", group=groups[[2]], header="SD", values=rcmetar.revman.format.number(cont.data@sd2, digits))
            ))
        }
    }
    columns <- c(columns, list(
        list(key="weight", group="", header="Weight", values=rcmetar.bmj.format.weight(rcmetar.metafor.weights(res), n))
    ))
    rcmetar.bmj.ilab(columns, n)
}

rcmetar.bmj.ilab.for.data <- function(om.data, params, res=NULL) {
    if ("BinaryData" %in% class(om.data)) {
        return(rcmetar.bmj.binary.ilab(om.data, params, res))
    }
    if ("ContinuousData" %in% class(om.data)) {
        return(rcmetar.bmj.continuous.ilab(om.data, params, res))
    }
    ilab <- rcmetar.revman.ilab.for.data(om.data, params, res)
    weight.index <- which(vapply(ilab$columns, function(column) column$key, character(1)) == "weight")
    if (length(weight.index) == 1) {
        ilab$matrix[, weight.index] <- rcmetar.bmj.format.weight(rcmetar.metafor.weights(res), nrow(ilab$matrix))
        ilab$columns[[weight.index]]$values <- ilab$matrix[, weight.index]
    }
    ilab
}

rcmetar.bmj.decorate.bundle <- function(bundle) {
    directions <- rcmetar.bmj.direction.labels(bundle)
    bundle$slab <- gsub(", ([0-9]{4})$", " \\1", bundle$slab)
    if (!is.null(bundle$effect$slab)) {
        bundle$effect$slab <- gsub(", ([0-9]{4})$", " \\1", bundle$effect$slab)
    }
    bundle$style_blocks <- list(
        heterogeneity=rcmetar.bmj.heterogeneity.label(bundle),
        test_overall=rcmetar.bmj.test.overall.label(bundle),
        totals=rcmetar.bmj.total.values(bundle),
        not_estimable=rcmetar.bmj.not_estimable(bundle),
        favours_left=directions$left,
        favours_right=directions$right,
        axis_label=directions$axis,
        journal="BMJ"
    )
    bundle
}

rcmetar.bmj.column.index <- function(bundle, key) {
    keys <- vapply(bundle$ilab$columns, function(column) column$key, character(1))
    which(keys == key)
}

rcmetar.bmj.total.values <- function(bundle) {
    totals <- list()
    for (key in c("experimental_events_total", "control_events_total")) {
        index <- rcmetar.bmj.column.index(bundle, key)
        if (length(index) != 1) {
            next
        }
        parts <- strsplit(bundle$ilab$matrix[, index], "/", fixed=TRUE)
        if (!all(vapply(parts, length, integer(1)) == 2)) {
            next
        }
        events <- suppressWarnings(as.numeric(trimws(vapply(parts, function(value) value[[1]], character(1)))))
        totals.raw <- suppressWarnings(as.numeric(trimws(vapply(parts, function(value) value[[2]], character(1)))))
        if (all(is.finite(events)) && all(is.finite(totals.raw))) {
            totals[[key]] <- paste(sum(events), sum(totals.raw), sep=" / ")
        }
    }
    for (key in c("experimental_total", "control_total")) {
        index <- rcmetar.bmj.column.index(bundle, key)
        if (length(index) == 1 && rcmetar.raw.values.complete(bundle$ilab$matrix[, index])) {
            totals[[key]] <- sum(suppressWarnings(as.numeric(bundle$ilab$matrix[, index])))
        }
    }
    weight.index <- rcmetar.bmj.column.index(bundle, "weight")
    if (length(weight.index) == 1) {
        totals[["weight"]] <- "100.0"
    }
    totals
}

rcmetar.bmj.not_estimable <- function(bundle) {
    if (!identical(bundle$data_type, "binary")) {
        return(rep(FALSE, nrow(bundle$ilab$matrix)))
    }
    experimental <- rcmetar.bmj.column.index(bundle, "experimental_events_total")
    control <- rcmetar.bmj.column.index(bundle, "control_events_total")
    if (length(experimental) != 1 || length(control) != 1) {
        return(rep(FALSE, nrow(bundle$ilab$matrix)))
    }
    total.from.label <- function(values) {
        parts <- strsplit(values, "/", fixed=TRUE)
        suppressWarnings(as.numeric(trimws(vapply(parts, function(value) value[[2]], character(1)))))
    }
    exp.total <- total.from.label(bundle$ilab$matrix[, experimental])
    ctrl.total <- total.from.label(bundle$ilab$matrix[, control])
    ifelse(is.na(exp.total) | is.na(ctrl.total), FALSE, exp.total + ctrl.total == 0)
}

rcmetar.bmj.direction.labels <- function(bundle) {
    if (identical(bundle$data_type, "diagnostic")) {
        return(list(left="", right="", axis=pretty.metric.name(as.character(bundle$params$measure))))
    }
    left <- "Favors control"
    right <- "Favors experimental"
    if (!is.null(bundle$params$fp_col4_str) && bundle$params$fp_col4_str != "[default]") {
        left <- paste("Favors", tolower(as.character(bundle$params$fp_col4_str)))
    }
    if (!is.null(bundle$params$fp_col3_str) && bundle$params$fp_col3_str != "[default]") {
        right <- paste("Favors", tolower(as.character(bundle$params$fp_col3_str)))
    }
    list(left=left, right=right, axis="")
}

rcmetar.bmj.xlab <- function(bundle) {
    rcmetar.revman.xlab(bundle)
}

rcmetar.bmj.study.header <- function(bundle) {
    rcmetar.revman.study.header(bundle)
}

rcmetar.bmj.effect.header <- function(bundle) {
    rcmetar.bmj.metric.label(bundle)
}

rcmetar.bmj.group.headers <- function(bundle) {
    if (length(bundle$ilab$groups) == 0) {
        return(character(0))
    }
    headers <- vapply(bundle$ilab$groups, rcmetar.revman.wrap.header, character(1))
    names(headers) <- bundle$ilab$groups
    headers
}

rcmetar.bmj.metric.label <- function(bundle) {
    label <- rcmetar.revman.metric.label(bundle)
    switch(
        label,
        "Risk Difference"="Risk difference",
        "Mean Difference"="Mean difference",
        "Standardized Mean Difference"="Standardized mean difference",
        label
    )
}

rcmetar.bmj.method.label <- function(bundle) {
    if (!is.null(bundle$params$rm.method) && bundle$params$rm.method != "FE") {
        return("IV, random")
    }
    "IV, fixed"
}

rcmetar.bmj.layout <- function(bundle) {
    rcmetar.forest.bmj.layout.coordinates(bundle)
}

rcmetar.bmj.axis.ticks <- function(bundle, alim) {
    if (!metric.is.log.scale(as.character(bundle$params$measure)) &&
            all(abs(alim - c(-1, 1)) < 1e-8)) {
        return(c(-1, -0.5, 0, 0.5, 1))
    }
    rcmetar.revman.axis.ticks(bundle, alim)
}

rcmetar.bmj.axis.labels <- function(bundle, ticks) {
    rcmetar.revman.axis.labels(bundle, ticks)
}

rcmetar.bmj.axis.footer.layout <- function(bundle, layout) {
    if (is.null(layout) || is.null(layout$alim)) {
        layout <- list(alim=graphics::par("usr")[1:2])
    }
    alim <- as.numeric(layout$alim)
    split.x <- 0
    if (!is.finite(split.x) || split.x <= alim[[1]] || split.x >= alim[[2]]) {
        split.x <- mean(alim)
    }
    list(
        left.x=mean(c(alim[[1]], split.x)),
        right.x=mean(c(split.x, alim[[2]])),
        split.x=split.x,
        span=diff(alim),
        axis.x=mean(alim),
        left.max.width=(split.x - alim[[1]]) * 0.92,
        right.max.width=(alim[[2]] - split.x) * 0.92,
        direction.width=22,
        direction.y=-2.82,
        axis.label.y=-2.82
    )
}

rcmetar.bmj.summary.result <- function(bundle) {
    rcmetar.revman.summary.result(bundle)
}

rcmetar.bmj.heterogeneity.label <- function(bundle) {
    label <- rcmetar.revman.heterogeneity.label(bundle)
    label <- gsub("Tau² = ", "Tau²=", label, fixed=TRUE)
    label <- gsub("Chi² = ", "Chi²=", label, fixed=TRUE)
    label <- gsub(", df = ", ", df=", label, fixed=TRUE)
    label <- gsub(" (P ", ", P ", label, fixed=TRUE)
    label <- gsub("); I² = ", "; I²=", label, fixed=TRUE)
    label <- gsub("P = ", "P=", label, fixed=TRUE)
    label <- gsub("P < ", "P<", label, fixed=TRUE)
    label
}

rcmetar.bmj.test.overall.label <- function(bundle) {
    label <- rcmetar.revman.test.overall.label(bundle)
    label <- sub(" \\((P [^)]+)\\)$", ", \\1", label)
    label <- gsub("Z = ", "Z=", label, fixed=TRUE)
    label <- gsub("P = ", "P=", label, fixed=TRUE)
    gsub("P < ", "P<", label, fixed=TRUE)
}

rcmetar.bmj.heterogeneity.display.label <- function(label) {
    sub("^Heterogeneity:", "Test for heterogeneity:", label)
}

rcmetar.bmj.compact.p.value.label <- function(p.value, digits=2) {
    label <- rcmetar.revman.p.value.label(p.value)
    label <- gsub("P = ", "P=", label, fixed=TRUE)
    gsub("P < ", "P<", label, fixed=TRUE)
}

rcmetar.bmj.heterogeneity.expression <- function(res) {
    if (is.null(res) || is.null(res$QE)) {
        return(NULL)
    }
    as.expression(bquote(paste(
        "Test for heterogeneity: ",
        tau^2, "=", .(round.display(res$tau2, 2)), "; ",
        chi^2, "=", .(round.display(res$QE, 2)),
        ", df=", .(res$k - res$p), ", ",
        .(rcmetar.bmj.compact.p.value.label(res$QEp, 2)), "; ",
        I^2, "=", .(round.display(res$I2, 0)), "%"
    )))
}

rcmetar.measure.bmj.forest.device <- function(bundle) {
    rcmetar.forest.bmj.device.metrics(bundle)
}

rcmetar.bmj.effect.values <- function(bundle) {
    effect <- NULL
    if (inherits(bundle$res, "rma") && !identical(bundle$forest_variant, "subgroup")) {
        effect <- list(
            yi=as.numeric(bundle$res$yi),
            ci.lb=as.numeric(bundle$res$ci.lb),
            ci.ub=as.numeric(bundle$res$ci.ub)
        )
    } else if (!is.null(bundle$effect)) {
        effect <- bundle$effect
    }
    if (is.null(effect)) {
        return(character(0))
    }
    transform <- rcmetar.bundle.transform(bundle)
    finite <- is.finite(effect$yi) & is.finite(effect$ci.lb) & is.finite(effect$ci.ub)
    labels <- rep("Not estimable", length(effect$yi))
    if (any(finite)) {
        labels[finite] <- rcmetar.bmj.effect.label(
            transform$display.scale(effect$yi[finite]),
            transform$display.scale(effect$ci.lb[finite]),
            transform$display.scale(effect$ci.ub[finite]),
            bundle$params$digits
        )
    }
    labels
}

rcmetar.bmj.summary.label.for.bundle <- function(bundle) {
    res <- rcmetar.bmj.summary.result(bundle)
    if (is.null(res) || is.null(res$b) || is.null(res$ci.lb) || is.null(res$ci.ub)) {
        return("")
    }
    transform <- rcmetar.bundle.transform(bundle)
    rcmetar.bmj.effect.label(
        transform$display.scale(res$b),
        transform$display.scale(res$ci.lb),
        transform$display.scale(res$ci.ub),
        bundle$params$digits
    )
}

rcmetar.bmj.column.widths <- function(bundle, cex) {
    if (ncol(bundle$ilab$matrix) == 0) {
        return(numeric(0))
    }
    widths <- vapply(seq_len(ncol(bundle$ilab$matrix)), function(index) {
        values <- c(bundle$ilab$matrix[, index], bundle$ilab$headers[[index]])
        key <- bundle$ilab$columns[[index]]$key
        if (identical(key, "weight")) {
            values <- c(values, "Weight", "(%)", "100.0")
        } else {
            values <- c(values, rcmetar.bmj.header.lines(bundle$ilab$columns[[index]]$group))
        }
        max(graphics::strwidth(values, units="inches", cex=cex), na.rm=TRUE)
    }, numeric(1))
    pmax(widths, 0.42)
}

rcmetar.bmj.wrap.header <- function(label, width=24) {
    label <- as.character(label)
    wrapped <- strwrap(label, width=width)
    if (length(wrapped) == 0) {
        return(label)
    }
    paste(wrapped, collapse="\n")
}

rcmetar.bmj.header.lines <- function(label, width=24) {
    lines <- strsplit(rcmetar.bmj.wrap.header(label, width=width), "\n", fixed=TRUE)[[1]]
    lines[nzchar(lines)]
}

rcmetar.bmj.wrap.direction <- function(label, width=22) {
    if (is.null(label) || !nzchar(label)) {
        return("")
    }
    wrapped.label <- strwrap(label, width=width)
    if (length(wrapped.label) <= 1) {
        return(label)
    }
    if (grepl("^Favors\\s+", label)) {
        arm.label <- sub("^Favors\\s+", "", label)
        arm.lines <- strwrap(arm.label, width=max(16, width - 7))
        return(paste(c("Favors", arm.lines), collapse="\n"))
    }
    rcmetar.bmj.wrap.header(label, width=width)
}

rcmetar.bmj.constrained.direction.label <- function(label, cex, max.width, preferred.width) {
    widths <- sort(unique(pmax(16, c(preferred.width, 24, 22, 20, 18, 16))), decreasing=TRUE)
    for (width in widths) {
        wrapped <- rcmetar.bmj.wrap.direction(label, width)
        lines <- unlist(strsplit(wrapped, "\n", fixed=TRUE), use.names=FALSE)
        if (length(lines) == 0 || length(lines) <= 3 ||
                max(graphics::strwidth(lines, units="user", cex=cex), na.rm=TRUE) <= max.width) {
            return(wrapped)
        }
    }
    rcmetar.bmj.wrap.direction(label, 16)
}

rcmetar.bmj.line.count <- function(label) {
    if (is.null(label) || !nzchar(label)) {
        return(0)
    }
    length(strsplit(label, "\n", fixed=TRUE)[[1]])
}

rcmetar.bmj.text.width <- function(values, cex, minimum=0) {
    values <- as.character(values)
    values <- values[nzchar(values)]
    if (length(values) == 0) {
        return(minimum)
    }
    max(minimum, max(graphics::strwidth(values, units="inches", cex=cex), na.rm=TRUE))
}

rcmetar.forest.bmj.device.metrics <- function(bundle) {
    rcmetar.forest.with.measurement.device({
        display.rows <- rcmetar.forest.display.row.count(bundle)
        text.floor <- if (display.rows <= 16) 0.82 else if (display.rows <= 28) 0.76 else 0.70
        cex <- max(text.floor, min(1.02, 1.02 - max(display.rows - 10, 0) * 0.014))
        header.lines <- max(c(1, vapply(bundle$ilab$groups, function(group) {
            length(rcmetar.bmj.header.lines(group))
        }, integer(1))))
        direction.lines <- max(
            rcmetar.bmj.line.count(rcmetar.bmj.wrap.direction(bundle$style_blocks$favours_left)),
            rcmetar.bmj.line.count(rcmetar.bmj.wrap.direction(bundle$style_blocks$favours_right)),
            1
        )
        column.widths <- rcmetar.bmj.column.widths(bundle, cex)
        weight.index <- rcmetar.bmj.column.index(bundle, "weight")
        left.indexes <- setdiff(seq_along(column.widths), weight.index)
        weight.width <- if (length(weight.index) == 1) column.widths[[weight.index]] else 0
        column.gap <- 0.32
        group.gap <- 0.42
        study.width <- rcmetar.bmj.text.width(
            c(bundle$slab, "Study or\nsubgroup", rcmetar.bmj.study.header(bundle)),
            cex,
            minimum=1.35
        )
        left.table.width <- if (length(left.indexes) > 0) {
            sum(column.widths[left.indexes]) + column.gap * max(length(left.indexes) - 1, 0)
        } else {
            0
        }
        group.header.width <- rcmetar.bmj.text.width(
            c(bundle$ilab$groups, "No of events / total"),
            cex,
            minimum=left.table.width
        )
        if (length(left.indexes) > 0 && group.header.width > left.table.width) {
            left.table.width <- group.header.width
        }
        metric.header <- paste0(
            rcmetar.bmj.metric.label(bundle), ", IV,\n",
            sub("^IV, ", "", rcmetar.bmj.method.label(bundle)),
            " (", bundle$params$conf.level, "% CI)"
        )
        effect.width <- rcmetar.bmj.text.width(
            c(metric.header, rcmetar.bmj.effect.values(bundle), rcmetar.bmj.summary.label.for.bundle(bundle)),
            cex,
            minimum=1.85
        )
        footer.width <- rcmetar.bmj.text.width(
            c(bundle$style_blocks$heterogeneity, bundle$style_blocks$test_overall),
            cex,
            minimum=study.width
        )
        plot.width <- max(3.4, min(4.6, 3.7 + max(0, display.rows - 8) * 0.035))
        study.gap <- 0.55
        left.plot.gap <- 0.58
        right.plot.gap <- 0.45
        weight.effect.gap <- 0.48
        right.margin <- 0.35
        left.width <- max(study.width + study.gap + left.table.width + left.plot.gap, footer.width + 0.25)
        right.width <- right.plot.gap + weight.width + weight.effect.gap + effect.width + right.margin
        width <- max(10.8, left.width + plot.width + right.width)
        if (width > 18) {
            shrink <- 18 / width
            cex <- max(text.floor, cex * shrink)
            column.widths <- rcmetar.bmj.column.widths(bundle, cex)
            weight.width <- if (length(weight.index) == 1) column.widths[[weight.index]] else 0
            left.table.width <- if (length(left.indexes) > 0) {
                sum(column.widths[left.indexes]) + column.gap * max(length(left.indexes) - 1, 0)
            } else {
                0
            }
            group.header.width <- rcmetar.bmj.text.width(
                c(bundle$ilab$groups, "No of events / total"),
                cex,
                minimum=left.table.width
            )
            if (length(left.indexes) > 0 && group.header.width > left.table.width) {
                left.table.width <- group.header.width
            }
            study.width <- rcmetar.bmj.text.width(
                c(bundle$slab, "Study or\nsubgroup", rcmetar.bmj.study.header(bundle)),
                cex,
                minimum=1.35
            )
            effect.width <- rcmetar.bmj.text.width(
                c(metric.header, rcmetar.bmj.effect.values(bundle), rcmetar.bmj.summary.label.for.bundle(bundle)),
                cex,
                minimum=1.85
            )
            footer.width <- rcmetar.bmj.text.width(
                c(bundle$style_blocks$heterogeneity, bundle$style_blocks$test_overall),
                cex,
                minimum=study.width
            )
            left.width <- max(study.width + study.gap + left.table.width + left.plot.gap, footer.width + 0.25)
            right.width <- right.plot.gap + weight.width + weight.effect.gap + effect.width + right.margin
            width <- max(10.8, left.width + plot.width + right.width)
        }
        height.extra <- max(0, header.lines - 2) * 0.28 + max(0, direction.lines - 2) * 0.20
        list(
            width=min(width, 18),
            height=max(5.0, min(18, 3.35 + 0.35 * display.rows + height.extra)),
            cex=cex,
            text_floor=text.floor,
            bg="white",
            display_rows=display.rows,
            header_lines=header.lines,
            direction_lines=direction.lines,
            study_width=study.width,
            column_widths=column.widths,
            left_indexes=left.indexes,
            weight_index=weight.index,
            left_table_width=left.table.width,
            plot_width=plot.width,
            weight_width=weight.width,
            effect_width=effect.width,
            footer_width=footer.width,
            column_gap=column.gap,
            group_gap=group.gap,
            study_gap=study.gap,
            left_plot_gap=left.plot.gap,
            right_plot_gap=right.plot.gap,
            weight_effect_gap=weight.effect.gap,
            right_margin=right.margin,
            left_width=left.width,
            right_width=right.width
        )
    })
}

rcmetar.forest.bmj.alim <- function(bundle) {
    measure <- as.character(bundle$params$measure)
    if (metric.is.log.scale(measure)) {
        return(log(c(0.01, 100)))
    }
    if (identical(measure, "RD")) {
        return(c(-1, 1))
    }
    alim <- rcmetar.metafor.alim(bundle)
    alim <- range(c(alim, 0), finite=TRUE)
    padding <- max(diff(alim) * 0.12, 0.1)
    c(alim[[1]] - padding, alim[[2]] + padding)
}

rcmetar.forest.bmj.layout.coordinates <- function(bundle) {
    size <- rcmetar.forest.bmj.device.metrics(bundle)
    rcmetar.forest.bmj.layout.coordinates.from_size(bundle, size)
}

rcmetar.forest.bmj.layout.coordinates.from_size <- function(bundle, size) {
    alim <- rcmetar.forest.bmj.alim(bundle)
    span <- max(diff(alim), 1)
    user.per.inch <- span / size$plot_width
    base.xlim <- c(
        alim[[1]] - size$left_width * user.per.inch,
        alim[[2]] + size$right_width * user.per.inch
    )
    edge.pad <- 0.16 * span
    xlim <- c(base.xlim[[1]] - edge.pad, base.xlim[[2]] + edge.pad)
    plot.start <- size$left_width
    plot.end <- plot.start + size$plot_width
    ilab.inches <- numeric(length(size$column_widths))
    if (length(size$left_indexes) > 0) {
        left.start <- size$study_width + size$study_gap
        left.centers <- left.start +
            cumsum(size$column_widths[size$left_indexes]) -
            size$column_widths[size$left_indexes] / 2 +
            size$column_gap * (seq_along(size$left_indexes) - 1)
        ilab.inches[size$left_indexes] <- left.centers
    }
    if (length(size$weight_index) == 1) {
        ilab.inches[size$weight_index] <- plot.end + size$right_plot_gap + size$weight_width / 2
    }
    ilab.xpos <- base.xlim[[1]] + ilab.inches * user.per.inch
    column.groups <- vapply(bundle$ilab$columns, function(column) column$group, character(1))
    group.xpos <- if (length(column.groups) > 0) {
        vapply(bundle$ilab$groups, function(group) {
            mean(ilab.xpos[column.groups == group])
        }, numeric(1))
    } else {
        numeric(0)
    }
    annotation.left <- plot.end + size$right_plot_gap + size$weight_width + size$weight_effect_gap
    list(
        xlim=xlim,
        study.xpos=base.xlim[[1]],
        alim=alim,
        ilab.xpos=ilab.xpos,
        group.xpos=group.xpos,
        annotation.xpos=base.xlim[[1]] + annotation.left * user.per.inch,
        annotation.header.xpos=base.xlim[[1]] + (annotation.left + size$effect_width / 2) * user.per.inch,
        plot.header.xpos=mean(alim)
    )
}

rcmetar.forest.bmj.layout.preflight <- function(bundle, size.policy="export") {
    size <- rcmetar.forest.bmj.device.metrics(bundle)
    size$size_policy <- size.policy
    layout <- rcmetar.forest.bmj.layout.coordinates.from_size(bundle, size)
    k <- length(bundle$slab)
    top.padding <- if (size$header_lines > 2) 3.75 else 3.2
    bottom.padding <- if (size$direction_lines > 2) 4.65 else 3.95
    rows <- list(
        k=k,
        study_rows=k:1,
        ylim=c(-bottom.padding, k + top.padding),
        top=k + top.padding,
        manual_sequential_labels=FALSE,
        max_group_header_lines=size$header_lines
    )
    rcmetar.forest.layout.plan(
        style="bmj",
        template=if (ncol(bundle$ilab$matrix) <= 1) "sparse" else "standard",
        device=size,
        typography=list(cex=size$cex, cex.axis=size$cex, cex.lab=size$cex),
        rows=rows,
        x=list(
            xlim=layout$xlim,
            alim=layout$alim,
            at=rcmetar.bmj.axis.ticks(bundle, layout$alim),
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
            study=rcmetar.bmj.study.header(bundle),
            effect=rcmetar.bmj.metric.label(bundle),
            method=rcmetar.bmj.method.label(bundle),
            groups=if (length(layout$group.xpos) > 0) names(layout$group.xpos) else character(0)
        ),
        footer=list(axis=rcmetar.bmj.axis.footer.layout(bundle, layout)),
        warnings=rcmetar.forest.layout.cap.warnings(size),
        metrics=size,
        layout=layout
    )
}

rcmetar.draw.bmj.forest <- function(bundle, outpath) {
    if (!inherits(bundle$res, "rma") && isTRUE(bundle$single_study)) {
        return(rcmetar.draw.bmj.sequential.forest(bundle, outpath))
    }
    if (!inherits(bundle$res, "rma") || identical(bundle$forest_variant, "subgroup")) {
        return(rcmetar.draw.bmj.default_like.forest(bundle, outpath))
    }

    plan <- rcmetar.forest.bmj.layout.preflight(bundle)
    size <- plan$device
    rcmetar.render.plot_file(outpath, size, function() {

    op <- graphics::par(no.readonly=TRUE)
    on.exit(graphics::par(op), add=TRUE)
    old.options <- options(na.action="na.pass")
    on.exit(options(old.options), add=TRUE)
    accent <- rcmetar.forest.accent.color(bundle$params)
    graphics::par(
        bg="white",
        mar=c(1.0, 0, 1.6, 0.8),
        mgp=c(3, 0.2, 0),
        tcl=-0.2,
        fg="#111111",
        col.axis="#111111",
        col.lab="#111111",
        family="sans"
    )

    layout <- plan$layout
    effect <- rcmetar.revman.study.effects(bundle)
    summary <- rcmetar.bmj.summary.effect(bundle)
    bundle$style_blocks$heterogeneity <- rcmetar.bmj.heterogeneity.label(within(bundle, res <- summary$res))
    bundle$style_blocks$test_overall <- rcmetar.bmj.test.overall.label(within(bundle, res <- summary$res))
    ilab <- rcmetar.bmj.display.ilab(bundle, summary$weights)
    method <- rcmetar.bmj.method.label(bundle)
    metric <- rcmetar.bmj.metric.label(bundle)
    k <- plan$rows$k
    rows <- plan$rows$study_rows

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
        lty=c(0, 0, 0),
        refline=NA,
        ilab=ilab$matrix,
        ilab.xpos=layout$ilab.xpos,
        ilab.pos=NULL,
        cex=plan$typography$cex,
        cex.lab=plan$typography$cex.lab,
        cex.axis=plan$typography$cex.axis,
        header=FALSE,
        pch=18,
        psize=summary$psize,
        col=accent,
        annotate=FALSE,
        ylim=plan$rows$ylim,
        rows=rows
    ))

    graphics::par(xpd=NA)
    rcmetar.draw.bmj.effects(effect, rows, layout$alim, accent, summary$psize)
    graphics::segments(plot.info$xlim[1], k + 1.55, plot.info$xlim[2], k + 1.55, lwd=0.9, col="#a9a9a9")
    graphics::segments(0, -1.0, 0, k + 1.55, lwd=0.85, col="#a9a9a9")
    graphics::segments(summary$yi, 0, summary$yi, k, lwd=0.9, lty=2, col=accent)

    graphics::par(cex=plot.info$cex, font=2, col="#111111")
    rcmetar.draw.bmj.headers(bundle, layout, ilab, k, metric, method, plan$headers$show)

    graphics::text(layout$annotation.xpos, 0, summary$label, pos=4, font=1)
    rcmetar.draw.revman.summary.diamond(summary, 0, accent)
    rcmetar.draw.bmj.axis(bundle, layout, plot.info$cex)

    graphics::par(cex=plot.info$cex, font=1, col="#111111")
    graphics::text(rcmetar.forest.study.x(layout), rows, bundle$slab, pos=4, cex=plot.info$cex, col="#111111")
    rcmetar.draw.bmj.study.effect.labels(bundle, effect, layout, rows, plot.info$cex)
    rcmetar.draw.bmj.bottom.blocks(bundle, rcmetar.forest.study.x(layout), plot.info$cex, layout, summary$res)

    invisible(bundle$changed.params)
    })
}

rcmetar.bmj.summary.effect <- function(bundle) {
    summary <- rcmetar.revman.summary.effect(bundle)
    transform <- rcmetar.bundle.transform(bundle)
    pred <- c(transform$display.scale(summary$yi), transform$display.scale(summary$ci.lb), transform$display.scale(summary$ci.ub))
    summary$label <- rcmetar.bmj.effect.label(pred[[1]], pred[[2]], pred[[3]], bundle$params$digits)
    finite.weights <- is.finite(summary$weights)
    if (any(finite.weights)) {
        scaled <- rep(NA_real_, length(summary$weights))
        weight.range <- range(summary$weights[finite.weights])
        if (diff(weight.range) > 0) {
            scaled[finite.weights] <- 1.2 + (summary$weights[finite.weights] - weight.range[[1]]) / diff(weight.range)
        } else {
            scaled[finite.weights] <- 1.45
        }
        summary$psize <- scaled
    }
    summary
}

rcmetar.bmj.display.ilab <- function(bundle, weights) {
    ilab <- bundle$ilab
    weight.index <- rcmetar.bmj.column.index(bundle, "weight")
    if (length(weight.index) == 1 && length(weights) == nrow(ilab$matrix)) {
        ilab$matrix[, weight.index] <- rcmetar.bmj.format.weight(weights, length(weights))
    }
    ilab
}

rcmetar.bmj.group.header.rules <- function(bundle, layout, ilab) {
    if (length(layout$group.xpos) == 0 || length(ilab$columns) == 0 || length(layout$ilab.xpos) == 0) {
        return(data.frame(group=character(0), left=numeric(0), right=numeric(0)))
    }
    column.groups <- vapply(ilab$columns, function(column) column$group, character(1))
    rules <- lapply(names(layout$group.xpos), function(group) {
        indexes <- which(column.groups == group)
        indexes <- indexes[indexes <= length(layout$ilab.xpos)]
        indexes <- indexes[is.finite(layout$ilab.xpos[indexes])]
        if (length(indexes) < 2) {
            return(NULL)
        }
        xpos <- as.numeric(layout$ilab.xpos[indexes])
        sorted <- sort(unique(xpos))
        spacing <- if (length(sorted) >= 2) min(diff(sorted)) else diff(layout$alim) * 0.05
        pad <- max(spacing * 0.35, diff(layout$alim) * 0.008)
        data.frame(
            group=group,
            left=min(xpos) - pad,
            right=max(xpos) + pad,
            stringsAsFactors=FALSE
        )
    })
    rules <- Filter(Negate(is.null), rules)
    if (length(rules) == 0) {
        return(data.frame(group=character(0), left=numeric(0), right=numeric(0)))
    }
    do.call(rbind, rules)
}

rcmetar.draw.bmj.effects <- function(effect, rows, alim, color, psize) {
    yi <- as.numeric(effect$yi)
    ci.lb <- as.numeric(effect$ci.lb)
    ci.ub <- as.numeric(effect$ci.ub)
    finite <- is.finite(yi) & is.finite(ci.lb) & is.finite(ci.ub)
    if (!any(finite)) {
        return(invisible(NULL))
    }
    graphics::segments(pmax(ci.lb[finite], alim[[1]]), rows[finite], pmin(ci.ub[finite], alim[[2]]), rows[finite], col=color, lwd=1.5)
    inside <- yi[finite] >= alim[[1]] & yi[finite] <= alim[[2]]
    if (any(inside)) {
        graphics::points(yi[finite][inside], rows[finite][inside], pch=18, col="white", cex=psize[finite][inside] * 1.15)
        graphics::points(yi[finite][inside], rows[finite][inside], pch=18, col=color, cex=psize[finite][inside])
    }
    invisible(NULL)
}

rcmetar.draw.bmj.headers <- function(bundle, layout, ilab, k, metric, method, show.headers) {
    if (!show.headers) {
        return(invisible(NULL))
    }
    graphics::text(rcmetar.forest.study.x(layout), k + 2.35, "Study or\nsubgroup", pos=4)
    if (identical(bundle$data_type, "binary") && length(bundle$ilab$groups) >= 2 && ncol(ilab$matrix) == 3) {
        group.labels <- vapply(names(layout$group.xpos)[1:2], rcmetar.bmj.wrap.header, character(1))
        group.lines <- max(vapply(group.labels, rcmetar.bmj.line.count, integer(1)), 1)
        group.y <- if (group.lines > 2) k + 2.08 else k + 2.35
        event.y <- if (group.lines > 2) k + 3.45 else k + 3.15
        rule.y <- if (group.lines > 2) k + 2.92 else k + 2.75
        graphics::text(mean(layout$ilab.xpos[1:2]), event.y, "No of events / total")
        graphics::segments(layout$ilab.xpos[[1]] - 0.28, rule.y, layout$ilab.xpos[[2]] + 0.28, rule.y, lwd=0.8)
        graphics::text(
            layout$ilab.xpos[1:2],
            group.y,
            group.labels
        )
        graphics::text(layout$ilab.xpos[[3]], k + 2.55, "Weight\n(%)")
    } else {
        graphics::text(layout$ilab.xpos, k + 2.2, ilab$headers)
        if (length(layout$group.xpos) > 0) {
            group.labels <- vapply(names(layout$group.xpos), rcmetar.bmj.wrap.header, character(1))
            graphics::text(layout$group.xpos, k + 3.0, group.labels)
            rules <- rcmetar.bmj.group.header.rules(bundle, layout, ilab)
            if (nrow(rules) > 0) {
                graphics::segments(rules$left, k + 2.65, rules$right, k + 2.65, lwd=0.8, col="#111111")
            }
        }
    }
    header <- paste0(metric, ", IV,\n", sub("^IV, ", "", method), " (", bundle$params$conf.level, "% CI)")
    graphics::text(layout$plot.header.xpos, k + 2.55, header)
    graphics::text(layout$annotation.header.xpos, k + 2.55, header)
    invisible(NULL)
}

rcmetar.bmj.format.effect.number <- function(values, digits) {
    values <- as.numeric(values)
    labels <- formatC(values, digits=as.integer(digits), format="f")
    labels[is.na(values)] <- ""
    labels
}

rcmetar.bmj.effect.label <- function(center, lower, upper, digits) {
    paste0(
        rcmetar.bmj.format.effect.number(center, digits),
        " (",
        rcmetar.bmj.format.effect.number(lower, digits),
        " to ",
        rcmetar.bmj.format.effect.number(upper, digits),
        ")"
    )
}

rcmetar.draw.bmj.study.effect.labels <- function(bundle, effect, layout, rows, cex) {
    transform <- rcmetar.bundle.transform(bundle)
    labels <- rep("Not estimable", length(effect$yi))
    finite <- is.finite(effect$yi) & is.finite(effect$ci.lb) & is.finite(effect$ci.ub)
    if (any(finite)) {
        labels[finite] <- rcmetar.bmj.effect.label(
            transform$display.scale(effect$yi[finite]),
            transform$display.scale(effect$ci.lb[finite]),
            transform$display.scale(effect$ci.ub[finite]),
            bundle$params$digits
        )
    }
    graphics::text(layout$annotation.xpos, rows, labels, pos=4, cex=cex)
}

rcmetar.draw.bmj.sequential.forest <- function(bundle, outpath) {
    rcmetar.draw.revman.sequential.forest(bundle, outpath)
}

rcmetar.draw.bmj.default_like.forest <- function(bundle, outpath) {
    default.bundle <- within(bundle, fp_style <- "default")
    default.bundle$params$fp_accent_color <- rcmetar.forest.accent.color(bundle$params)
    rcmetar.draw.default.metafor.forest(default.bundle, outpath)
}

rcmetar.draw.bmj.axis <- function(bundle, layout, cex) {
    ticks <- rcmetar.bmj.axis.ticks(bundle, layout$alim)
    labels <- rcmetar.bmj.axis.labels(bundle, ticks)
    y.axis <- -1.72
    y.tick <- -1.56
    y.label <- -2.18
    span <- max(diff(layout$alim), 1)
    graphics::rect(layout$alim[[1]] - 0.04 * span, -5.4, layout$alim[[2]] + 0.04 * span, -1.46, col="white", border=NA)
    graphics::segments(layout$alim[[1]], y.axis, layout$alim[[2]], y.axis, lwd=0.9, col="#a9a9a9")
    graphics::segments(ticks, y.axis, ticks, y.tick, lwd=0.8, col="#a9a9a9")
    graphics::text(ticks, y.label, labels, cex=cex, col="#111111")
    invisible(NULL)
}

rcmetar.draw.bmj.bottom.blocks <- function(bundle, x, cex, layout=NULL, summary.res=NULL) {
    graphics::par(xpd=NA)
    if (!is.null(layout)) {
        rcmetar.draw.bmj.total.row(bundle, x, layout, cex)
    }
    if (nzchar(bundle$style_blocks$heterogeneity)) {
        heterogeneity.label <- rcmetar.bmj.heterogeneity.expression(summary.res)
        if (is.null(heterogeneity.label)) {
            heterogeneity.label <- rcmetar.bmj.heterogeneity.display.label(bundle$style_blocks$heterogeneity)
        }
        graphics::text(x, -1, heterogeneity.label, pos=4, cex=cex)
    }
    if (nzchar(bundle$style_blocks$test_overall)) {
        graphics::text(x, -2, bundle$style_blocks$test_overall, pos=4, cex=cex)
    }
    axis.footer <- rcmetar.bmj.axis.footer.layout(bundle, layout)
    left.label <- ""
    right.label <- ""
    if (nzchar(bundle$style_blocks$favours_left)) {
        left.label <- rcmetar.bmj.constrained.direction.label(
            bundle$style_blocks$favours_left,
            cex,
            axis.footer$left.max.width,
            axis.footer$direction.width
        )
    }
    if (nzchar(bundle$style_blocks$favours_right)) {
        right.label <- rcmetar.bmj.constrained.direction.label(
            bundle$style_blocks$favours_right,
            cex,
            axis.footer$right.max.width,
            axis.footer$direction.width
        )
    }
    direction.y <- axis.footer$direction.y -
        max(0, max(rcmetar.bmj.line.count(left.label), rcmetar.bmj.line.count(right.label)) - 2) * 0.32
    label.wraps.deeply <- max(rcmetar.bmj.line.count(left.label), rcmetar.bmj.line.count(right.label)) > 2
    left.x <- axis.footer$left.x
    right.x <- axis.footer$right.x
    left.adj <- 0.5
    right.adj <- 0.5
    if (label.wraps.deeply) {
        label.gap <- max(axis.footer$span * 0.035, 0.08)
        left.x <- axis.footer$split.x - label.gap
        right.x <- axis.footer$split.x + label.gap
        left.adj <- 1
        right.adj <- 0
    }
    if (nzchar(left.label)) {
        graphics::text(left.x, direction.y, left.label, cex=cex, font=2, adj=left.adj)
    }
    if (nzchar(right.label)) {
        graphics::text(right.x, direction.y, right.label, cex=cex, font=2, adj=right.adj)
    }
    if (nzchar(bundle$style_blocks$axis_label)) {
        graphics::text(axis.footer$axis.x, axis.footer$axis.label.y, bundle$style_blocks$axis_label, cex=cex)
    }
    invisible(NULL)
}

rcmetar.draw.bmj.total.row <- function(bundle, x, layout, cex) {
    graphics::text(x, 0, paste0("Total (", bundle$params$conf.level, "% CI)"), pos=4, font=1, cex=cex)
    for (key in names(bundle$style_blocks$totals)) {
        index <- rcmetar.bmj.column.index(bundle, key)
        if (length(index) == 1) {
            graphics::text(layout$ilab.xpos[[index]], 0, bundle$style_blocks$totals[[key]], font=1, cex=cex)
        }
    }
    invisible(NULL)
}
