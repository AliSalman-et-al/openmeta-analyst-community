# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

pad.with.spaces <- function(entry, begin.num, end.num) {
  repeat.string.begin <- ""
  if (begin.num > 0) {
    repeat.string.begin <- create.repeat.string(" ", begin.num)
  }
  repeat.string.end <- ""
  if (end.num > 0) {
    repeat.string.end <- create.repeat.string(" ", end.num)
  }
  padded.entry <- paste(repeat.string.begin, entry, repeat.string.end, sep="")
  padded.entry
}

create.repeat.string <- function(symbol, num.repeats) {
  repeat.string <- NULL
  for (count in 1:num.repeats) {
    repeat.string <- paste(repeat.string, symbol, sep="")
  }
  repeat.string
}

RCMETAR_DEFAULT_DISPLAY_DIGITS <- 2L
RCMETAR_MINIMUM_P_VALUE_DIGITS <- 3L

display.digits <- function(params=NULL, minimum=0L) {
  digits <- RCMETAR_DEFAULT_DISPLAY_DIGITS
  if (!is.null(params) && !is.null(params$digits) && length(params$digits) > 0) {
    candidate <- suppressWarnings(as.integer(params$digits[[1]]))
    if (!is.na(candidate) && candidate >= 0) {
      digits <- candidate
    }
  }
  max(as.integer(minimum), digits)
}

p.value.display.digits <- function(digits=RCMETAR_DEFAULT_DISPLAY_DIGITS) {
  candidate <- suppressWarnings(as.integer(digits[[1]]))
  if (length(candidate) == 0 || is.na(candidate) || candidate < 0) {
    candidate <- RCMETAR_DEFAULT_DISPLAY_DIGITS
  }
  max(RCMETAR_MINIMUM_P_VALUE_DIGITS, candidate)
}

round.display <- function(x, digits) {
  digits.str <- paste("%.", digits, "f", sep="")
  x.disp <- rep("", length(x))
  finite <- is.finite(x)
  x.disp[finite] <- sprintf(digits.str, x[finite])
  x.disp[!finite & is.na(x)] <- NA_character_
  x.disp
}

display.value.is.missing <- function(value) {
  is.null(value) || length(value) == 0 || all(is.na(value))
}

format.numeric.display <- function(value, digits.str) {
  if (display.value.is.missing(value)) {
    return("")
  }
  sprintf(digits.str, value)
}

format.percent.display <- function(value, digits.str) {
  if (display.value.is.missing(value)) {
    return("")
  }
  paste(sprintf(digits.str, value), "%", sep="")
}

format.p.value.display <- function(value, digits) {
  if (display.value.is.missing(value)) {
    return("")
  }
  digits <- p.value.display.digits(digits)
  threshold <- 10^(-digits)
  formatted <- round.display(value, digits)
  small.nonnegative <- is.finite(value) & value >= 0 & value < threshold
  formatted[small.nonnegative] <- paste("< ", threshold, sep="")
  formatted
}

display.confidence.level <- function(params=NULL) {
  level <- if (!is.null(params) && !is.null(params$conf.level) && length(params$conf.level)) {
    suppressWarnings(as.numeric(params$conf.level[[1]]))
  } else {
    NA_real_
  }
  if (!length(level) || !is.finite(level) || level <= 0 || level >= 100) 95 else level
}

display.confidence.interval.labels <- function(params=NULL) {
  level <- trimws(formatC(display.confidence.level(params), format="fg", digits=4))
  c(paste0("Lower bound (", level, "% CI)"), paste0("Upper bound (", level, "% CI)"))
}

g.round.display.zval <- function(x, digits) {
  if (display.value.is.missing(x)) {
    return("")
  }
  digits.str <- paste("%.", digits, "f", sep="")
  x.disp <- round.display(x, digits)

  negative.small <- is.finite(x) & x < 0 & abs(x) < 10^(-digits)
  negative <- is.finite(x) & x < 0 & abs(x) >= 10^(-digits)
  x.disp[negative.small] <- paste(">","-",10^(-digits)," & <0",sep="")
  x.disp[negative] <- sprintf(digits.str, x[negative])

  positive.small <- is.finite(x) & x > 0 & x < 10^(-digits)
  positive <- is.finite(x) & x > 0 & x >= 10^(-digits)
  x.disp[positive.small] <- paste("< ", 10^(-digits), sep="")
  x.disp[positive] <- sprintf(digits.str, x[positive])
  x.disp
}
