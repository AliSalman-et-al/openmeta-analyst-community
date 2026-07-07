# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# BMJ Forest Style templates for the metafor-backed forest renderer.

rcmetar.bmj.ilab.for.data <- function(om.data, params, res=NULL) {
    rcmetar.revman.ilab.for.data(om.data, params, res)
}

rcmetar.bmj.decorate.bundle <- function(bundle) {
    bundle <- rcmetar.revman.decorate.bundle(bundle)
    bundle$style_blocks$journal <- "BMJ"
    bundle
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
    rcmetar.revman.metric.label(bundle)
}

rcmetar.bmj.method.label <- function(bundle) {
    rcmetar.revman.method.label(bundle)
}

rcmetar.bmj.layout <- function(bundle) {
    rcmetar.forest.revman.layout.coordinates(bundle)
}

rcmetar.bmj.axis.ticks <- function(bundle, alim) {
    rcmetar.revman.axis.ticks(bundle, alim)
}

rcmetar.bmj.axis.labels <- function(bundle, ticks) {
    rcmetar.revman.axis.labels(bundle, ticks)
}

rcmetar.bmj.axis.footer.layout <- function(bundle, layout) {
    rcmetar.revman.axis.footer.layout(bundle, layout)
}

rcmetar.bmj.summary.result <- function(bundle) {
    rcmetar.revman.summary.result(bundle)
}

rcmetar.bmj.heterogeneity.label <- function(bundle) {
    rcmetar.revman.heterogeneity.label(bundle)
}

rcmetar.bmj.test.overall.label <- function(bundle) {
    rcmetar.revman.test.overall.label(bundle)
}

rcmetar.measure.bmj.forest.device <- function(bundle) {
    rcmetar.forest.revman.device.metrics(bundle)
}

rcmetar.draw.bmj.forest <- function(bundle, outpath) {
    if (!inherits(bundle$res, "rma") && isTRUE(bundle$single_study)) {
        return(rcmetar.draw.bmj.sequential.forest(bundle, outpath))
    }
    if (!inherits(bundle$res, "rma") || identical(bundle$forest_variant, "subgroup")) {
        return(rcmetar.draw.bmj.default_like.forest(bundle, outpath))
    }

    plan <- rcmetar.forest.revman.layout.preflight(bundle)
    size <- plan$device
    rcmetar.render.plot_file(outpath, size, function() {

    op <- graphics::par(no.readonly=TRUE)
    on.exit(graphics::par(op), add=TRUE)
    old.options <- options(na.action="na.pass")
    on.exit(options(old.options), add=TRUE)
    accent <- rcmetar.forest.accent.color(bundle$params)
    graphics::par(
        bg="white",
        mar=c(1.0, 0, 1.9, 1.0),
        mgp=c(3, 0.2, 0),
        tcl=-0.2,
        fg="#222222",
        col.axis="#222222",
        col.lab="#222222",
        family="sans"
    )

    layout <- plan$layout
    effect <- rcmetar.revman.study.effects(bundle)
    summary <- rcmetar.revman.summary.effect(bundle)
    bundle$style_blocks$heterogeneity <- rcmetar.bmj.heterogeneity.label(within(bundle, res <- summary$res))
    bundle$style_blocks$test_overall <- rcmetar.bmj.test.overall.label(within(bundle, res <- summary$res))
    ilab <- rcmetar.revman.display.ilab(bundle, summary$weights)
    method <- rcmetar.bmj.method.label(bundle)
    metric <- rcmetar.bmj.metric.label(bundle)
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
        textpos=c(layout$xlim[1], layout$annotation.xpos),
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
        col=accent,
        annotate=FALSE,
        ylim=plan$rows$ylim,
        rows=rows
    ))

    graphics::par(xpd=NA)
    rcmetar.draw.metafor.effect.accent(
        effect=effect,
        rows=rows,
        alim=layout$alim,
        color=accent,
        psize=summary$psize,
        lwd=1.25
    )
    graphics::segments(plot.info$xlim[1], k + 1, plot.info$xlim[2], k + 1, lwd=1.1, col=accent)
    graphics::segments(0, -2, 0, k + 1, lwd=0.8, col="#555555")

    graphics::par(cex=plot.info$cex, font=2, col="#222222")
    if (show.headers) {
        graphics::text(layout$xlim[[1]], k + 2, rcmetar.bmj.study.header(bundle), pos=4)
        graphics::text(layout$ilab.xpos, k + 2, ilab$headers)
    }
    if (show.headers && length(layout$group.xpos) > 0) {
        graphics::text(layout$group.xpos, k + 3, vapply(names(layout$group.xpos), rcmetar.revman.wrap.header, character(1)))
    }
    if (show.headers) {
        graphics::text(layout$annotation.header.xpos, k + 3, metric)
        graphics::text(layout$annotation.header.xpos, k + 2, paste0(method, ", ", bundle$params$conf.level, "% CI"))
        graphics::text(layout$plot.header.xpos, k + 3, metric)
        graphics::text(layout$plot.header.xpos, k + 2, paste0(method, ", ", bundle$params$conf.level, "% CI"))
    }

    graphics::rect(layout$annotation.xpos, -1.5, layout$ilab.xpos[[length(layout$ilab.xpos)]], -0.5, col="white", border=NA)
    graphics::text(layout$annotation.xpos, -1, summary$label, pos=2, font=2)
    rcmetar.draw.revman.summary.diamond(summary, -1, accent)
    rcmetar.draw.bmj.axis(bundle, layout, plot.info$cex, accent)

    graphics::par(cex=plot.info$cex, font=1, col="#222222")
    graphics::text(layout$xlim[[1]], rows, bundle$slab, pos=4, cex=plot.info$cex, col="#222222")
    rcmetar.draw.revman.study.effect.labels(bundle, effect, layout, rows, plot.info$cex)
    rcmetar.draw.bmj.bottom_blocks(bundle, layout$xlim[1], plot.info$cex, layout)

    invisible(bundle$changed.params)
    })
}

rcmetar.draw.bmj.sequential.forest <- function(bundle, outpath) {
    rcmetar.draw.revman.sequential.forest(bundle, outpath)
}

rcmetar.draw.bmj.default_like.forest <- function(bundle, outpath) {
    default.bundle <- within(bundle, fp_style <- "default")
    default.bundle$params$fp_accent_color <- rcmetar.forest.accent.color(bundle$params)
    rcmetar.draw.default.metafor.forest(default.bundle, outpath)
}

rcmetar.draw.bmj.axis <- function(bundle, layout, cex, accent) {
    ticks <- rcmetar.bmj.axis.ticks(bundle, layout$alim)
    labels <- rcmetar.bmj.axis.labels(bundle, ticks)
    y.axis <- -2.3
    y.tick <- -2.12
    y.label <- -2.78
    span <- max(diff(layout$alim), 1)
    graphics::rect(layout$alim[[1]] - 0.04 * span, -5.4, layout$alim[[2]] + 0.04 * span, -2.05, col="white", border=NA)
    graphics::segments(layout$alim[[1]], y.axis, layout$alim[[2]], y.axis, lwd=1.0, col=accent)
    graphics::segments(ticks, y.axis, ticks, y.tick, lwd=0.8, col=accent)
    graphics::text(ticks, y.label, labels, cex=cex, col="#222222")
    invisible(NULL)
}

rcmetar.draw.bmj.bottom_blocks <- function(bundle, x, cex, layout=NULL) {
    rcmetar.draw.revman.bottom.blocks(bundle, x, cex, layout)
}
