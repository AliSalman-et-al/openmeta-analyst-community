# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# Shared style registry and data seams for metafor-backed forest renderers.

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
        "revman" = "revman",
        "revman forest style" = "revman",
        "bmj" = "bmj",
        "bmj forest style" = "bmj",
        style
    )
}

rcmetar.forest.style <- function(params) {
    style <- rcmetar.forest.style.default(params)
    if (style %in% c("default", "revman", "bmj")) {
        return(style)
    }
    "default"
}

rcmetar.metafor.style.helper <- function(style, suffix) {
    style <- gsub("[^[:alnum:]_]+", "_", as.character(style))
    name <- paste0("rcmetar.", style, ".", suffix)
    if (exists(name, mode="function")) {
        return(get(name, mode="function"))
    }
    NULL
}

rcmetar.metafor.style.renderer <- function(style) {
    style <- gsub("[^[:alnum:]_]+", "_", as.character(style))
    name <- paste0("rcmetar.draw.", style, ".forest")
    if (exists(name, mode="function")) {
        return(get(name, mode="function"))
    }
    NULL
}

rcmetar.param.is.true <- function(params, name, default=TRUE) {
    value <- params[[name]]
    if (is.null(value) || length(value) == 0 || is.na(value[1])) {
        return(default)
    }
    if (is.logical(value)) {
        return(isTRUE(value[1]))
    }
    tolower(as.character(value[1])) %in% c("true", "t", "1", "yes")
}

rcmetar.forest.accent.color <- function(params) {
    color <- params$fp_accent_color
    if (!is.null(color) && length(color) > 0 && !is.na(color[1]) && nzchar(as.character(color[1]))) {
        return(as.character(color[1]))
    }
    switch(
        rcmetar.forest.style(params),
        revman="#000000",
        bmj="#6b58a6",
        "#2f5597"
    )
}

rcmetar.point.size.multiplier <- function(params) {
    value <- suppressWarnings(as.numeric(params$fp_point_size_multiplier))
    if (length(value) == 0 || !is.finite(value[1]) || value[1] <= 0) {
        return(1.0)
    }
    value[1]
}

rcmetar.is.metafor.forest.bundle <- function(plot.data) {
    is.list(plot.data) &&
        identical(plot.data$render_engine, "metafor") &&
        !is.null(plot.data$fp_style)
}

rcmetar.ilab.for.data <- function(om.data, params, res=NULL) {
    style <- rcmetar.forest.style(params)
    helper <- rcmetar.metafor.style.helper(style, "ilab.for.data")
    if (!is.null(helper)) {
        return(helper(om.data, params, res))
    }
    rcmetar.default.ilab.for.data(om.data, params)
}

rcmetar.decorate.metafor.bundle <- function(bundle) {
    helper <- rcmetar.metafor.style.helper(bundle$fp_style, "decorate.bundle")
    if (!is.null(helper)) {
        return(helper(bundle))
    }
    bundle$style_blocks <- list()
    bundle
}
