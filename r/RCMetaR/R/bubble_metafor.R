# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

rcmetar.bubble.style <- function(params) {
    style <- params$bp_style
    if (!is.null(style) && length(style) > 0 && !is.na(style[1]) && nzchar(as.character(style[1]))) {
        params$fp_style <- style
    }
    rcmetar.forest.style(params)
}

rcmetar.is.metafor.bubble.bundle <- function(plot.data) {
    is.list(plot.data) &&
        identical(plot.data$render_engine, "metafor") &&
        identical(plot.data$plot_type, "meta_regression_bubble") &&
        inherits(plot.data$res, "rma")
}

rcmetar.create.metafor.bubble.bundle <- function(
        reg.data,
        params,
        res,
        cov.name=NULL,
        cov.values=NULL,
        fitted.line=NULL) {
    if (!rcmetar.is.plot.default.text(params$bp_xlabel)) {
        params$bp_xlabel <- rcmetar.limit.plot.input.text(params$bp_xlabel)
    }
    if (is.null(cov.name)) {
        cov.name <- if (is(reg.data, "OMData")) reg.data@covariates[[1]]@cov.name else names(reg.data)[[1]]
    }
    if (is.null(cov.values)) {
        cov.values <- if (is(reg.data, "OMData")) reg.data@covariates[[1]]@cov.vals else reg.data[[cov.name]]
    }
    study.labels <- if (is(reg.data, "OMData")) reg.data@study.names else as.character(reg.data$slab)
    yi <- if (is(reg.data, "OMData")) reg.data@y else reg.data$yi
    sei <- if (is(reg.data, "OMData")) reg.data@SE else sqrt(reg.data$vi)
    scale.str <- if (!is.null(params$measure)) get.scale(params) else g.get.scale(params$measure)
    xlabel <- as.character(cov.name)
    if (!rcmetar.is.plot.default.text(params$bp_xlabel) &&
            nzchar(as.character(params$bp_xlabel[1]))) {
        xlabel <- as.character(params$bp_xlabel[1])
    }
    xlabel <- rcmetar.truncate.plot.display.text(xlabel, rcmetar.plot.text.input.limit)
    list(
        render_engine="metafor",
        plot_type="meta_regression_bubble",
        res=res,
        params=params,
        bp_style=rcmetar.bubble.style(params),
        moderator=list(name=as.character(cov.name), values=as.numeric(cov.values)),
        slab=as.character(study.labels),
        effects=list(ES=as.numeric(yi), se=as.numeric(sei)),
        fitted.line=fitted.line,
        scale=scale.str,
        xlabel=xlabel,
        ylabel=rcmetar.bubble.default.ylabel(params)
    )
}

rcmetar.bubble.default.ylabel <- function(params) {
    metric <- pretty.metric.name(as.character(params$measure))
    scale.str <- get.scale(params)
    if (scale.str %in% c("log", "logit")) {
        return(paste0(metric, " (", scale.str, " scale)"))
    }
    metric
}

rcmetar.bubble.accent.color <- function(bundle) {
    color <- bundle$params$bp_accent_color
    if (is.null(color) || length(color) == 0 || is.na(color[1]) || !nzchar(as.character(color[1]))) {
        color <- bundle$params$fp_accent_color
    }
    if (!is.null(color) && length(color) > 0 && !is.na(color[1]) && nzchar(as.character(color[1]))) {
        return(as.character(color[1]))
    }
    switch(
        bundle$bp_style,
        revman="#111111",
        bmj="#6b58a6",
        "#2f5597"
    )
}

rcmetar.bubble.param.is.true <- function(bundle, name, default=TRUE) {
    rcmetar.param.is.true(bundle$params, name, default=default)
}

rcmetar.bubble.axis.ticks <- function(bundle, ylim=NULL) {
    measure <- as.character(bundle$params$measure)
    if (!is.null(bundle$params$bp_yticks) &&
            !identical(bundle$params$bp_yticks[1], "[default]") &&
            !all(is.na(bundle$params$bp_yticks))) {
        ticks <- as.numeric(bundle$params$bp_yticks)
        if (metric.is.log.scale(measure)) {
            return(log(ticks))
        }
        if (metric.is.logit.scale(measure)) {
            return(logit(pmin(pmax(ticks, .Machine$double.eps), 1 - .Machine$double.eps)))
        }
        return(ticks)
    }
    if (is.null(ylim) || length(ylim) != 2 || any(!is.finite(ylim))) {
        y <- as.numeric(bundle$effects$ES)
        y <- y[is.finite(y)]
        if (length(y) > 0) {
            pad <- max(diff(range(y)), 0.25) * 0.25
            ylim <- range(y) + c(-pad, pad)
        }
    }
    if (metric.is.log.scale(measure)) {
        candidates <- log(c(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 10, 20, 100))
        return(rcmetar.bubble.ticks.in.range(candidates, ylim))
    }
    if (metric.is.logit.scale(measure)) {
        candidates <- logit(c(0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99))
        return(rcmetar.bubble.ticks.in.range(candidates, ylim))
    }
    NULL
}

rcmetar.bubble.ticks.in.range <- function(candidates, range) {
    if (is.null(range) || length(range) != 2 || any(!is.finite(range))) {
        return(candidates)
    }
    ticks <- candidates[candidates >= range[[1]] & candidates <= range[[2]]]
    if (length(ticks) >= 2) {
        return(ticks)
    }
    pretty(range)
}

rcmetar.bubble.atransf <- function(bundle) {
    measure <- as.character(bundle$params$measure)
    if (metric.is.log.scale(measure)) {
        return(exp)
    }
    if (metric.is.logit.scale(measure)) {
        return(invlogit)
    }
    if (metric.is.arcsine.scale(measure)) {
        return(invarcsine.sqrt)
    }
    NULL
}

rcmetar.bubble.measure.device <- function(bundle) {
    rcmetar.forest.with.measurement.device({
        cex <- max(0.86, min(1.05, 1.05 - max(length(bundle$slab) - 30, 0) * 0.004))
        label.width <- max(strwidth(c(bundle$xlabel, bundle$ylabel, bundle$slab), units="inches", cex=cex), na.rm=TRUE)
        legend.width <- if (rcmetar.bubble.param.is.true(bundle, "bp_show_legend", FALSE)) 2.55 else 0
        list(
            width=max(7.2, min(14.5, 6.5 + min(label.width, 4) * 0.55 + legend.width)),
            height=max(5.0, min(8.0, 4.8 + if (rcmetar.bubble.param.is.true(bundle, "bp_label_studies", FALSE)) 0.7 else 0)),
            cex=cex,
            bg="white",
            dpi=300
        )
    })
}

rcmetar.bubble.style.args <- function(bundle) {
    accent <- rcmetar.bubble.accent.color(bundle)
    point.bg <- grDevices::adjustcolor(accent, alpha.f=0.28)
    ci.shade <- grDevices::adjustcolor(accent, alpha.f=0.12)
    pi.shade <- grDevices::adjustcolor(accent, alpha.f=0.06)
    style.args <- switch(
        bundle$bp_style,
        revman=list(
            pch=21,
            col="#111111",
            bg=grDevices::adjustcolor("#111111", alpha.f=0.18),
            lcol="#111111",
            lwd=1.6,
            lty=c("solid", "dashed", "dotted"),
            shade=c(grDevices::adjustcolor("#888888", alpha.f=0.16), grDevices::adjustcolor("#888888", alpha.f=0.08)),
            grid=TRUE,
            bty="l",
            las=1
        ),
        bmj=list(
            pch=21,
            col=accent,
            bg=grDevices::adjustcolor(accent, alpha.f=0.34),
            lcol=accent,
            lwd=2.2,
            lty=c("solid", "solid", "dashed"),
            shade=c(grDevices::adjustcolor(accent, alpha.f=0.10), grDevices::adjustcolor(accent, alpha.f=0.045)),
            grid=FALSE,
            bty="l",
            las=1
        ),
        list(
            pch=21,
            col=accent,
            bg=point.bg,
            lcol=accent,
            lwd=2,
            lty=c("solid", "dashed", "dotted"),
            shade=c(ci.shade, pi.shade),
            grid=TRUE,
            bty="l",
            las=1
        )
    )
    point.multiplier <- suppressWarnings(as.numeric(bundle$params$bp_point_size_multiplier[1]))
    if (length(point.multiplier) == 0 || !is.finite(point.multiplier) || point.multiplier <= 0) {
        point.multiplier <- 1
    }
    style.args$plim <- c(0.5, 3) * point.multiplier
    style.args
}

rcmetar.bubble.xlim <- function(bundle) {
    lower <- bundle$params$bp_plot_lb
    upper <- bundle$params$bp_plot_ub
    if (!is.null(lower) && !is.null(upper) &&
            !identical(lower[1], "[default]") && !identical(upper[1], "[default]")) {
        bounds <- suppressWarnings(as.numeric(c(lower[[1]], upper[[1]])))
        if (length(bounds) == 2 && all(is.finite(bounds)) && bounds[[1]] < bounds[[2]]) {
            return(bounds)
        }
    }
    x <- as.numeric(bundle$moderator$values)
    x <- x[is.finite(x)]
    if (length(x) == 0) {
        return(NULL)
    }
    range <- range(x)
    width <- diff(range)
    if (!is.finite(width) || width <= 0) {
        pad <- max(abs(range[[1]]) * 0.1, 1)
    } else {
        pad <- width * 0.12
    }
    c(range[[1]] - pad, range[[2]] + pad)
}

rcmetar.bubble.ylim <- function(bundle) {
    NULL
}

rcmetar.bubble.x.ticks <- function(bundle) {
    ticks <- bundle$params$bp_xticks
    if (is.null(ticks) || length(ticks) == 0 || identical(ticks[1], "[default]")) {
        limits <- rcmetar.bubble.xlim(bundle)
        if (is.null(limits)) {
            return(NULL)
        }
        ticks <- pretty(limits, n=5)
        return(ticks[ticks >= limits[[1]] & ticks <= limits[[2]]])
    }
    if (length(ticks) == 1 && is.character(ticks)) {
        ticks <- strsplit(ticks, ",", fixed=TRUE)[[1]]
    }
    ticks <- suppressWarnings(as.numeric(trimws(ticks)))
    ticks[is.finite(ticks)]
}

rcmetar.bubble.refline <- function(bundle, ylim=NULL) {
    refline <- 0
    if (!is.null(ylim) && length(ylim) == 2 && all(is.finite(ylim)) && (refline < ylim[[1]] || refline > ylim[[2]])) {
        return(NA)
    }
    refline
}

rcmetar.bubble.compact.args <- function(args) {
    args[!vapply(args, is.null, logical(1))]
}

rcmetar.bubble.legend.labels <- function(bundle) {
    level <- if (!is.null(bundle$params$conf.level) && length(bundle$params$conf.level)) {
        suppressWarnings(as.numeric(bundle$params$conf.level[[1]]))
    } else {
        NA_real_
    }
    if (!length(level) || !is.finite(level) || level <= 0 || level >= 100) level <- 95
    level <- trimws(formatC(level, format="fg", digits=4))
    labels <- c("Studies", "Regression line", paste0(level, "% CI"))
    if (rcmetar.bubble.param.is.true(bundle, "bp_show_prediction_interval", FALSE)) {
        labels <- c(labels, paste0(level, "% PI"))
    }
    labels
}

rcmetar.bubble.draw.legend <- function(bundle, style.args) {
    if (!rcmetar.bubble.param.is.true(bundle, "bp_show_legend", FALSE)) {
        return(invisible(NULL))
    }
    usr <- graphics::par("usr")
    x.span <- diff(usr[1:2])
    x <- usr[[2]] + 0.012 * x.span
    y <- usr[[4]]
    labels <- rcmetar.bubble.legend.labels(bundle)
    lty <- c(NA, "solid", style.args$lty[[2]])
    lwd <- c(NA, style.args$lwd, style.args$lwd)
    pch <- c(style.args$pch, NA, NA)
    col <- c(style.args$col, style.args$lcol, style.args$lcol)
    pt.bg <- c(style.args$bg, NA, NA)
    if (rcmetar.bubble.param.is.true(bundle, "bp_show_prediction_interval", FALSE)) {
        lty <- c(lty, style.args$lty[[3]])
        lwd <- c(lwd, style.args$lwd)
        pch <- c(pch, NA)
        col <- c(col, style.args$lcol)
        pt.bg <- c(pt.bg, NA)
    }
    graphics::legend(
        x=x,
        y=y,
        legend=labels,
        pch=pch,
        pt.bg=pt.bg,
        col=col,
        lty=lty,
        lwd=lwd,
        bty="n",
        xpd=NA,
        cex=max(0.68, graphics::par("cex") * 0.74),
        xjust=0,
        yjust=1,
        text.col="#222222"
    )
    invisible(NULL)
}

rcmetar.draw.metafor.bubble <- function(bundle, outpath) {
    size <- rcmetar.bubble.measure.device(bundle)
    display.path <- rcmetar.plot.display_path_for_bundle(bundle, outpath, "bp")
    rcmetar.render.plot_file(outpath, size, function() {
        old.par <- graphics::par(no.readonly=TRUE)
        on.exit(graphics::par(old.par), add=TRUE)
        graphics::par(
            mar=c(4.6, 5.2, 1.1, if (rcmetar.bubble.param.is.true(bundle, "bp_show_legend", FALSE)) 7.2 else 1.1),
            mgp=c(2.9, 0.75, 0),
            cex=size$cex,
            family="sans"
        )
        args <- rcmetar.bubble.style.args(bundle)
        ylim <- rcmetar.bubble.ylim(bundle)
        at <- rcmetar.bubble.axis.ticks(bundle, ylim)
        x.ticks <- rcmetar.bubble.x.ticks(bundle)
        args <- c(
            list(
                x=bundle$res,
                mod=bundle$moderator$name,
                pred=rcmetar.bubble.param.is.true(bundle, "bp_show_regression_line", TRUE),
                ci=rcmetar.bubble.param.is.true(bundle, "bp_show_confidence_band", TRUE),
                pi=rcmetar.bubble.param.is.true(bundle, "bp_show_prediction_interval", FALSE),
                xlab=bundle$xlabel,
                ylab=bundle$ylabel,
                xlim=rcmetar.bubble.xlim(bundle),
                ylim=ylim,
                predlim=range(as.numeric(bundle$moderator$values), na.rm=TRUE),
                refline=rcmetar.bubble.refline(bundle, ylim),
                atransf=rcmetar.bubble.atransf(bundle),
                at=at,
                digits=as.integer(bundle$params$digits),
                slab=bundle$slab,
                label=FALSE,
                labsize=max(0.68, size$cex * 0.84),
                legend=FALSE
            ),
            args
        )
        if (length(x.ticks) > 0) {
            args$xaxt <- "n"
        }
        args <- rcmetar.bubble.compact.args(args)
        result <- tryCatch(
            do.call(metafor::regplot, args),
            error=function(e) {
                args$mod <- 1
                do.call(metafor::regplot, args)
            }
        )
        if (length(x.ticks) > 0) {
            graphics::axis(1, at=x.ticks)
        }
        rcmetar.bubble.draw.legend(bundle, args)
        invisible(result)
    }, display.path=display.path)
}
