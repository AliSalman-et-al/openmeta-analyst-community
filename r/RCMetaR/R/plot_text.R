# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

rcmetar.plot.text.input.limit <- 80L

rcmetar.is.plot.default.text <- function(value) {
    if (is.null(value) || length(value) == 0L || is.na(value[[1L]])) {
        return(TRUE)
    }
    tolower(trimws(as.character(value[[1L]]))) %in%
        c("", "[default]", "<default>", "(default)", "default")
}

rcmetar.limit.plot.input.text <- function(value, limit=rcmetar.plot.text.input.limit) {
    if (is.null(value) || length(value) == 0 || is.na(value[[1]]) ||
            identical(value[[1]], "[default]")) {
        return(value)
    }
    substr(as.character(value[[1]]), 1L, limit)
}

rcmetar.truncate.plot.display.text <- function(value, limit=72L) {
    value <- as.character(value)
    over <- !is.na(value) & nchar(value, type="chars") > limit
    if (any(over, na.rm=TRUE)) {
        suffix.width <- 13L
        prefix.width <- limit - suffix.width - 3L
        value[over] <- paste0(
            substr(value[over], 1L, prefix.width),
            "...",
            substr(value[over], nchar(value[over], type="chars") - suffix.width + 1L,
                   nchar(value[over], type="chars"))
        )
    }
    value
}

rcmetar.normalize.plot.text.params <- function(params, limit=rcmetar.plot.text.input.limit) {
    for (name in c("fp_xlabel", "bp_xlabel")) {
        if (name %in% names(params) && rcmetar.is.plot.default.text(params[[name]])) {
            params[[name]] <- NULL
        }
    }
    for (name in c("fp_col1_str", "fp_col2_str", "fp_col3_str", "fp_col4_str", "fp_xlabel")) {
        value <- params[[name]]
        if (!is.null(value) && length(value) > 0 && !is.na(value[[1]]) &&
                !identical(value[[1]], "[default]")) {
            params[[name]] <- rcmetar.limit.plot.input.text(value, limit)
        }
    }
    params
}
