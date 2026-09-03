# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

rcmetar.summary.label <- function(value) {
  normalized <- trimws(as.character(value))
  compact <- tolower(gsub("[._-]+", " ", normalized))
  compact <- gsub("\\s+", " ", compact)
  compact <- trimws(compact)

  if (compact == "p value") {
    return("p-value")
  }
  if (compact == "het p value") {
    return("Het. p-value")
  }
  if (compact == "omnibus p value") {
    return("Omnibus p-value")
  }
  if (compact == "z value") {
    return("z-value")
  }
  normalized
}

rcmetar.scratch.path <- function(...) {
  scratch.dir <- Sys.getenv(
    "RCMS_ANALYSIS_SCRATCH_DIR",
    unset = file.path(tempdir(), "rc-metastudio-analysis")
  )
  dir.create(scratch.dir, recursive = TRUE, showWarnings = FALSE)
  file.path(scratch.dir, ...)
}

rcmetar.summary.cell.is.numeric <- function(value) {
  normalized <- trimws(as.character(value))
  if (normalized == "") {
    return(TRUE)
  }
  normalized <- gsub("%$", "", normalized)
  normalized <- trimws(gsub("^[<>]\\s*", "", normalized))
  grepl("^-?\\d+(\\.\\d+)?$", normalized)
}

rcmetar.summary.column.justification <- function(table.data, col.index) {
  if (col.index == 1) {
    return("left")
  }
  values <- as.character(table.data[-1, col.index])
  if (length(values) > 0 && all(vapply(values, rcmetar.summary.cell.is.numeric, logical(1)))) {
    return("right")
  }
  "left"
}

print.summary.display <- function(x, ...) {
  summary.disp <- x
  cat(summary.disp$model.title)
  arrays <- summary.disp$arrays
  count = 1
  printed.block <- FALSE
  for (name in arrays) {
    if (!is.na(summary.disp$table.titles[count])) {
      if (printed.block) {
        cat("\n")
      } else {
        cat("\n\n")
      }
      cat(rcmetar.summary.label(summary.disp$table.titles[count]))
      cat("\n")
      print.summary.data(name)
      printed.block <- TRUE
    }
    count = count + 1
   }
  if (!is.null(summary.disp$notes)) {
    for (note in summary.disp$notes) {
      if (printed.block) {
        cat("\n")
      } else {
        cat("\n\n")
      }
      cat(note)
      printed.block <- TRUE
    }
  }
  cat("\n")
}

print.summary.data <- function(x, ...) {
  table.data <- x
  num.rows <- length(table.data[,1])
  num.cols <- length(table.data[1,])
  col.spacing <- "  "
  col.widths <- c()
  table.data[1,] <- vapply(table.data[1,], rcmetar.summary.label, character(1))
  for (col.index in 1:num.cols) {
    col.widths <- c(col.widths, max(nchar(as.character(table.data[, col.index]), type="width")))
  }

  for (row.index in 1:num.rows) {
    cells <- c()
    for (col.index in 1:num.cols) {
      entry <- as.character(table.data[row.index, col.index])
      justify <- rcmetar.summary.column.justification(table.data, col.index)
      cells <- c(cells, format(entry, width=col.widths[col.index], justify=justify))
    }
    table.row <- paste(" ", paste(cells, collapse=col.spacing), sep="")
    cat(table.row)
    cat("\n")
  }
}

rcmetar.method.references <- function(method) {
  refs <- list(
    "rma.uni.fixed"=c(
      "Fixed-effect inverse-variance meta-analysis: Cochran, W. G. (1954). The combination of estimates from different experiments. Biometrics, 10(1), 101-129. doi:10.2307/3001666.",
      "Implementation reference: Viechtbauer, W. (2010). Conducting meta-analyses in R with the metafor package. Journal of Statistical Software, 36(3), 1-48. doi:10.18637/jss.v036.i03."
    ),
    "rma.uni.random"=c(
      "Random-effects meta-analysis: DerSimonian, R., & Laird, N. (1986). Meta-analysis in clinical trials. Controlled Clinical Trials, 7(3), 177-188. doi:10.1016/0197-2456(86)90046-2.",
      "Random-effects meta-analysis: Hedges, L. V. (1983). A random effects model for effect sizes. Psychological Bulletin, 93(2), 388-395. doi:10.1037/0033-2909.93.2.388.",
      "Implementation reference: Viechtbauer, W. (2010). Conducting meta-analyses in R with the metafor package. Journal of Statistical Software, 36(3), 1-48. doi:10.18637/jss.v036.i03."
    ),
    "rma.mh"=c(
      "Mantel-Haenszel meta-analysis: Mantel, N., & Haenszel, W. (1959). Statistical aspects of the analysis of data from retrospective studies of disease. Journal of the National Cancer Institute, 22(4), 719-748. doi:10.1093/jnci/22.4.719.",
      "Common-effect sparse-data estimation: Greenland, S., & Robins, J. M. (1985). Estimation of a common effect parameter from sparse follow-up data. Biometrics, 41(1), 55-68. doi:10.2307/2530643.",
      "Implementation reference: Viechtbauer, W. (2010). Conducting meta-analyses in R with the metafor package. Journal of Statistical Software, 36(3), 1-48. doi:10.18637/jss.v036.i03."
    ),
    "rma.peto"=c(
      "Peto one-step odds-ratio method: Yusuf, S., Peto, R., Lewis, J., Collins, R., & Sleight, P. (1985). Beta blockade during and after myocardial infarction: An overview of the randomized trials. Progress in Cardiovascular Disease, 27(5), 335-371. doi:10.1016/S0033-0620(85)80003-7.",
      "Sparse-data comparison: Bradburn, M. J., Deeks, J. J., Berlin, J. A., & Localio, A. R. (2007). Much ado about nothing: A comparison of the performance of meta-analytical methods with rare events. Statistics in Medicine, 26(1), 53-77. doi:10.1002/sim.2528.",
      "Implementation reference: Viechtbauer, W. (2010). Conducting meta-analyses in R with the metafor package. Journal of Statistical Software, 36(3), 1-48. doi:10.18637/jss.v036.i03."
    ),
    "meta.regression"=c(
      "Random-effects meta-regression: Berkey, C. S., Hoaglin, D. C., Mosteller, F., & Colditz, G. A. (1995). A random-effects regression model for meta-analysis. Statistics in Medicine, 14(4), 395-411. doi:10.1002/sim.4780140406.",
      "Implementation reference: Viechtbauer, W. (2010). Conducting meta-analyses in R with the metafor package. Journal of Statistical Software, 36(3), 1-48. doi:10.18637/jss.v036.i03."
    ),
    "publication.bias.egger"=c(
      "Egger regression test: Egger, M., Davey Smith, G., Schneider, M., & Minder, C. (1997). Bias in meta-analysis detected by a simple, graphical test. BMJ, 315(7109), 629-634. doi:10.1136/bmj.315.7109.629."
    ),
    "publication.bias.egger.mixed"=c(
      "Mixed-effects regression test: Sterne, J. A. C., & Egger, M. (2005). Regression methods to detect publication and other bias in meta-analysis. In Publication Bias in Meta-Analysis: Prevention, Assessment and Adjustments (pp. 99-110). Wiley."
    ),
    "publication.bias.begg"=c(
      "Begg-Mazumdar rank test: Begg, C. B., & Mazumdar, M. (1994). Operating characteristics of a rank correlation test for publication bias. Biometrics, 50(4), 1088-1101. doi:10.2307/2533446."
    ),
    "publication.bias.harbord"=c(
      "Harbord test: Harbord, R. M., Egger, M., & Sterne, J. A. C. (2006). A modified test for small-study effects in meta-analyses of controlled trials with binary endpoints. Statistics in Medicine, 25(20), 3443-3457. doi:10.1002/sim.2380."
    ),
    "publication.bias.peters"=c(
      "Peters test: Peters, J. L., Sutton, A. J., Jones, D. R., Abrams, K. R., & Rushton, L. (2006). Comparison of two methods to detect publication bias in meta-analysis. JAMA, 295(6), 676-680. doi:10.1001/jama.295.6.676."
    ),
    "publication.bias.pustejovsky"=c(
      "Standardized-mean-difference asymmetry test: Pustejovsky, J. E., & Rodgers, M. A. (2019). Testing for funnel plot asymmetry of standardized mean differences. Research Synthesis Methods, 10(1), 57-71. doi:10.1002/jrsm.1332."
    ),
    "publication.bias.rucker"=c(
      "Arcsine asymmetry test: Rucker, G., Schwarzer, G., & Carpenter, J. R. (2008). Arcsine test for publication bias in meta-analyses with binary outcomes. Statistics in Medicine, 27(5), 746-763. doi:10.1002/sim.2971.",
      "Additive random-effects regression: Thompson, S. G., & Sharp, S. J. (1999). Explaining heterogeneity in meta-analysis: A comparison of methods. Statistics in Medicine, 18(20), 2693-2708."
    ),
    "publication.bias.deeks"=c(
      "Deeks test: Deeks, J. J., Macaskill, P., & Irwig, L. (2005). The performance of tests of publication bias and other sample size effects in systematic reviews of diagnostic test accuracy was assessed. Journal of Clinical Epidemiology, 58(9), 882-893. doi:10.1016/j.jclinepi.2004.06.012."
    ),
    "publication.bias.funnel"=c(
      "Funnel plot axis choice: Sterne, J. A. C., & Egger, M. (2001). Funnel plots for detecting bias in meta-analysis: Guidelines on choice of axis. Journal of Clinical Epidemiology, 54(10), 1046-1055. doi:10.1016/S0895-4356(01)00377-8."
    ),
    "publication.bias.contour"=c(
      "Contour-enhanced funnel plots: Peters, J. L., Sutton, A. J., Jones, D. R., Abrams, K. R., & Rushton, L. (2008). Contour-enhanced meta-analysis funnel plots help distinguish publication bias from other causes of asymmetry. Journal of Clinical Epidemiology, 61(10), 991-996. doi:10.1016/j.jclinepi.2007.11.010."
    ),
    "publication.bias.trimfill"=c(
      "Trim-and-fill method: Duval, S., & Tweedie, R. (2000). Trim and fill: A simple funnel-plot-based method of testing and adjusting for publication bias in meta-analysis. Biometrics, 56(2), 455-463. doi:10.1111/j.0006-341X.2000.00455.x."
    ),
    "publication.bias.implementation"=c(
      "Implementation reference: Viechtbauer, W. (2010). Conducting meta-analyses in R with the metafor package. Journal of Statistical Software, 36(3), 1-48. doi:10.18637/jss.v036.i03."
    ),
    "bootstrap"=c(
      "Bootstrap methods: Davison, A. C., & Hinkley, D. V. (1997). Bootstrap Methods and Their Application. Cambridge University Press.",
      "Bootstrap confidence intervals: DiCiccio, T. J., & Efron, B. (1996). Bootstrap confidence intervals. Statistical Science, 11(3), 189-228.",
      "Bootstrap methods: Efron, B., & Tibshirani, R. (1993). An Introduction to the Bootstrap. Chapman & Hall."
    ),
    "reitsma"=c(
      "Bivariate diagnostic meta-analysis: Reitsma, J. B., Glas, A. S., Rutjes, A. W., Scholten, R. J., Bossuyt, P. M., & Zwinderman, A. H. (2005). Bivariate analysis of sensitivity and specificity produces informative summary measures in diagnostic reviews. Journal of Clinical Epidemiology, 58(10), 982-990.",
      "Diagnostic accuracy model unification: Harbord, R. M., Deeks, J. J., Egger, M., Whiting, P., & Sterne, J. A. (2006). A unification of models for meta-analysis of diagnostic accuracy studies. Biostatistics, 8(2), 239-251.",
      "Statistical implementation: Doebler, P. (2025). mada: Meta-Analysis of Diagnostic Accuracy, version 0.5.12."
    ),
    "rutter.gatsonis"=c(
      "Equivalent SROC parameterization: Rutter, C. M., & Gatsonis, C. A. (2001). A hierarchical regression approach to meta-analysis of diagnostic accuracy evaluations. Statistics in Medicine, 20(19), 2865-2884."
    )
  )

  refs[[method]]
}

rcmetar.random.effects.methods <- function() {
  c("HE", "DL", "HS", "HSk", "SJ", "ML", "REML", "EB", "PM", "PMM")
}

rcmetar.random.effects.method.names <- function() {
  list(
    HE="Hedges-Olkin",
    DL="DerSimonian-Laird",
    HS="Hunter-Schmidt",
    HSk="Hunter-Schmidt with small-sample correction",
    SJ="Sidik-Jonkman",
    ML="Maximum Likelihood",
    REML="Restricted Maximum Likelihood",
    EB="Empirical Bayes",
    PM="Paule-Mandel",
    PMM="Median-unbiased Paule-Mandel"
  )
}

rcmetar.inference.methods <- function() {
  c("z", "t", "knha", "adhoc")
}

rcmetar.inference.method.names <- function() {
  list(
    z="Normal approximation",
    t="Student's t-distribution",
    knha="Knapp-Hartung",
    adhoc="Modified Knapp-Hartung"
  )
}

rcmetar.inference.method <- function(params) {
  method <- params$inference.method
  if (is.null(method) || length(method) == 0 || is.na(method[1]) || !nzchar(as.character(method[1]))) {
    return("z")
  }
  match.arg(as.character(method[1]), rcmetar.inference.methods())
}

rcmetar.validate.inference.method <- function(params, k, p=1) {
  method <- rcmetar.inference.method(params)
  if (method != "z" && k - p <= 0) {
    stop(sprintf(
      "The selected Inference Method requires positive residual degrees of freedom (studies: %d, fitted coefficients: %d).",
      k,
      p
    ), call.=FALSE)
  }
  method
}

rcmetar.inference.method.metadata <- function() {
  list(
    "pretty.name"="Inference method",
    "description"="Procedure used to compute coefficient tests and their corresponding confidence intervals",
    "inference.method.names"=rcmetar.inference.method.names()
  )
}

rcmetar.inference.method.references <- function(params) {
  method <- rcmetar.inference.method(params)
  if (!(method %in% c("knha", "adhoc"))) {
    return(character())
  }
  references <- c(
    "Knapp-Hartung inference: Knapp, G., & Hartung, J. (2003). Improved tests for a random effects meta-regression with a single covariate. Statistics in Medicine, 22(17), 2693-2710. doi:10.1002/sim.1482.",
    "Hartung-Knapp-Sidik-Jonkman inference: Sidik, K., & Jonkman, J. N. (2002). A simple confidence interval for meta-analysis. Statistics in Medicine, 21(21), 3153-3159. doi:10.1002/sim.1262."
  )
  if (method == "adhoc") {
    references <- c(
      references,
      "Modified Knapp-Hartung inference: Jackson, D., Law, M., Rucker, G., & Schwarzer, G. (2017). The Hartung-Knapp modification for random-effects meta-analysis: A useful refinement but are there any residual concerns? Statistics in Medicine, 36(25), 3923-3934. doi:10.1002/sim.7411."
    )
  }
  references
}

rcmetar.unique.references <- function(references) {
  unique(as.character(references))
}

if (!exists("validate.conf.level", mode="function")) {
  validate.conf.level <- function(conf.level) {
    if (length(conf.level) != 1 || is.na(conf.level) || !is.finite(conf.level) ||
        conf.level <= 0 || conf.level >= 100) {
      stop("conf.level must be a single finite number between 0 and 100.")
    }
    conf.level
  }
}

if (!exists("get.mult.from.conf.level", mode="function")) {
  get.mult.from.conf.level <- function(conf.level=get.global.conf.level()) {
    stats::qnorm((1 + validate.conf.level(conf.level) / 100) / 2)
  }
}

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


create.summary.disp <- function(om.data, params, res, model.title) {
  result.digits <- display.digits(params)
  se.digits <- display.digits(params, minimum=3L)
  digits.str <- paste("%.", result.digits, "f", sep="")
  se.digits.str <- paste("%.", se.digits, "f", sep="")
  transform.name <- get.transform.name(om.data)
  scale.str <- get.scale(params)
  tau2 <- format.numeric.display(res$tau2, digits.str)
  degf <- res$k - 1
  I2 <- format.percent.display(res$I2, "%.1f")
  QLabel =  paste("Q(df=", degf, ")", sep="")
  if (params$measure=="PFT" && length(om.data@g1O1) > 0 && length(om.data@g1O2) > 0) {
    n <- om.data@g1O1 + om.data@g1O2
  }
  else {
    n <- NULL
  }
  QE <- format.numeric.display(res$QE, digits.str)
  QEp <- format.p.value.display(res$QEp, params$digits)
  pVal <- format.p.value.display(res$pval, params$digits)

  res.title <- "Model Results"
  y.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(res$b, ni=n))
  lb.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(res$ci.lb, ni=n))
  ub.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(res$ci.ub, ni=n))
  se <- sprintf(se.digits.str, res$se)

  if (res$method=="FE") {
    het.col.labels <- c(QLabel, "Het. p-value")
    het.col.vals <-  c(QE, QEp)
    het.array <- rbind(het.col.labels, het.col.vals)
  } else {
    het.col.labels <- c("\u03c4\u00b2", QLabel, "Het. p-value", "I\u00b2")
    het.col.vals <-  c(tau2, QE, QEp, I2)
    het.array <- rbind(het.col.labels, het.col.vals)
  }
  class(het.array) <- "summary.data"
  het.title <- "Heterogeneity"

  if (scale.str == "log" || scale.str == "logit" || scale.str == "arcsine") {
    res.col.labels <- c("Estimate", display.confidence.interval.labels(params), "p-value")
    res.col.vals <- c(y.disp, lb.disp, ub.disp, pVal)
    res.array <- rbind(res.col.labels, res.col.vals)
    estCalc <- sprintf(digits.str, res$b)
    lbCalc <- sprintf(digits.str, res$ci.lb)
    ubCalc <- sprintf(digits.str, res$ci.ub)
    calc.note <- paste(
      "Calculation scale: ", scale.str,
      " - estimate: ", estCalc,
      ", lower: ", lbCalc,
      ", upper: ", ubCalc,
      ", std. error: ", se,
      sep=""
    )
    arrays <- list(arr1=res.array, arr2=het.array)
    table.titles <- c(res.title, het.title)
    notes <- c(calc.note)
  } else {
    col.labels <- c("Estimate", display.confidence.interval.labels(params), "Std. error", "p-value")
    col.vals <- c(y.disp, lb.disp, ub.disp, se, pVal)
    res.array <- rbind(col.labels, col.vals)
    arrays = list(arr1=res.array, arr2=het.array)
    table.titles <- c(res.title, het.title)
    notes <- NULL
  }


  summary.disp <- list(
    "model.title" = model.title,
    "table.titles" = table.titles,
    "arrays" = arrays,
    "notes" = notes,
    "MAResults" = res)
  class(summary.disp) <- "summary.display"
  summary.disp
}

save.plot.data <- function(plot.data, out.path=NULL) {
  if (is.null(out.path)){
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }
  save(plot.data, file=paste(out.path, ".plotdata", sep=""))
  out.path
}

save.plot.data.and.params <- function(data, params, res, level, out.path=NULL) {
  if (is.null(out.path)){
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }

  save(data, file=paste(out.path, ".data", sep=""))

  save(params, file=paste(out.path, ".params", sep=""))

  save(res, file=paste(out.path, ".res", sep=""))

  save(level, file=paste(out.path, ".level", sep=""))

  out.path
}


save.data <- function(om.data, res, params, plot.data, out.path=NULL) {
  if (is.null(out.path)){
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }

  save(om.data, file=paste(out.path, ".data", sep=""))
  if (inherits(plot.data$regeneration_state, "rcmetar_forest_regeneration_state")) {
    res <- plot.data$regeneration_state
    for (param.name in names(res$param_overrides)) {
      params[[param.name]] <- res$param_overrides[[param.name]]
    }
  }
  save(res, file=paste(out.path, ".res", sep=""))

  save(plot.data, file=paste(out.path, ".plotdata", sep=""))
  save(params, file=paste(out.path, ".params", sep=""))
  out.path
}

update.changed.plot.params <- function(params, changed.params) {
  if (length(changed.params) == 0) {
    return(params)
  }
  for (param.name in names(changed.params)) {
    value <- changed.params[[param.name]]
    if (length(value) > 1) {
      value <- paste(value, collapse=", ")
    }
    params[[param.name]][1] <- value
  }
  params
}

rcmetar.regression.display.value <- function(value, digits, percent=FALSE) {
  if (display.value.is.missing(value) || length(value) != 1 || !is.finite(as.numeric(value))) {
    return("Not estimable")
  }
  if (percent) {
    return(sprintf(paste0("%.", digits, "f%%"), as.numeric(value)))
  }
  sprintf(paste0("%.", digits, "f"), as.numeric(value))
}

rcmetar.regression.summary.array <- function(rows, headers=c("Statistic", "Value")) {
  values <- do.call(rbind, rows)
  result <- rbind(headers, values)
  class(result) <- "summary.data"
  result
}

rcmetar.regression.factor.tests <- function(res, display.data, params) {
  factor.levels <- display.data$factor.n.levels
  factor.names <- display.data$factor.cov.names
  if (!inherits(res, "rma") || length(factor.levels) == 0 || length(factor.names) != length(factor.levels)) {
    return(list())
  }
  coefficient.index <- 2 + display.data$n.cont.covs
  tests <- list()
  for (index in seq_along(factor.levels)) {
    coefficient.count <- factor.levels[index] - 1
    btt <- coefficient.index:(coefficient.index + coefficient.count - 1)
    test <- tryCatch(anova(res, btt=btt), error=function(e) NULL)
    if (!is.null(test)) {
      tests[[factor.names[index]]] <- list(result=test, df1=coefficient.count)
    }
    coefficient.index <- coefficient.index + coefficient.count
  }
  tests
}

rcmetar.regression.test.row <- function(label, statistic, df1, p.value, df2=NULL, digits=3L) {
  display.df <- function(value) {
    if (display.value.is.missing(value) || length(value) != 1 || !is.finite(as.numeric(value))) {
      return("Not estimable")
    }
    as.character(as.numeric(value))
  }
  df <- if (is.null(df2) || display.value.is.missing(df2)) {
    display.df(df1)
  } else {
    paste(display.df(df1), display.df(df2), sep=", ")
  }
  formatted.p <- if (display.value.is.missing(p.value) || length(p.value) != 1 ||
                     !is.finite(as.numeric(p.value))) "Not estimable" else
    format.p.value.display(p.value, digits)
  c(label, rcmetar.regression.display.value(statistic, digits), df,
    formatted.p)
}

create.regression.display <- function(res, params, display.data) {
  bootstrap.type <- if (is.null(params$bootstrap.type)) "" else as.character(params$bootstrap.type)
  cov.display.col <- display.data$cov.display.col
  levels.display.col <- display.data$levels.display.col
  studies.display.col <- display.data$studies.display.col
  factor.n.levels <- display.data$factor.n.levels
  n.cont.covs <- display.data$n.cont.covs
  n.cont.rows <- n.cont.covs + 1
  n.factor.covs <- length(factor.n.levels)
  n.rows <- length(cov.display.col) + 1
  result.digits <- display.digits(params)
  se.digits <- display.digits(params, minimum=3L)
  digits.str <- paste("%.", result.digits, "f", sep="")
  inference.method <- rcmetar.inference.method(params)
  t.inference <- inference.method %in% c("t", "knha", "adhoc")
  ci.labels <- display.confidence.interval.labels(params)

  if (n.factor.covs == 0) {
    col.labels <- if (bootstrap.type == "boot.meta.reg") {
      c("Covariate", "Estimate", ci.labels)
    } else if (t.inference) {
      c("Covariate", "Estimate", ci.labels, "Std. error", "t", "df", "p-value")
    } else {
      c("Covariate", "Estimate", ci.labels, "Std. error", "z", "p-value")
    }
  } else {
    col.labels <- if (bootstrap.type == "boot.meta.reg") {
      c("Covariate", "Level", "Studies", "Estimate", ci.labels)
    } else if (t.inference) {
      c("Covariate", "Level", "Studies", "Estimate", ci.labels, "Std. error", "t", "df", "p-value")
    } else {
      c("Covariate", "Level", "Studies", "Estimate", ci.labels, "Std. error", "z", "p-value")
    }
  }

  reg.array <- array(dim=c(length(cov.display.col) + 1, length(col.labels)), dimnames=list(NULL, col.labels))
  reg.array[1,] <- col.labels
  display.values <- function(values, digits) {
    vapply(seq_along(res$b), function(index) {
      value <- if (length(values) >= index) values[index] else NULL
      rcmetar.regression.display.value(value, digits)
    }, character(1))
  }
  display.p.values <- function(values) {
    vapply(seq_along(res$b), function(index) {
      value <- if (length(values) >= index) values[index] else NULL
      if (display.value.is.missing(value) || length(value) != 1 || !is.finite(as.numeric(value))) {
        "Not estimable"
      } else {
        format.p.value.display(value, params$digits)
      }
    }, character(1))
  }
  coeffs <- display.values(res$b, result.digits)
  lbs <- display.values(res$ci.lb, result.digits)
  ubs <- display.values(res$ci.ub, result.digits)
  coeffs.tmp <- coeffs[1:n.cont.rows]
  lbs.tmp <- lbs[1:n.cont.rows]
  ubs.tmp <- ubs[1:n.cont.rows]

  if (bootstrap.type != "boot.meta.reg") {
    se <- display.values(res$se, se.digits)
    pvals <- display.p.values(res$pval)
    statistics <- display.values(res$zval, se.digits)
    dfs <- rep(if (!is.null(res$ddf)) res$ddf else res$k - res$p, length(res$b))
    se.tmp <- se[1:n.cont.rows]
    pvals.tmp <- pvals[1:n.cont.rows]
    statistics.tmp <- statistics[1:n.cont.rows]
    dfs.tmp <- dfs[1:n.cont.rows]
  }

  if (n.factor.covs > 0) {
    insert.row <- n.cont.rows + 1
    for (count in seq_len(n.factor.covs)) {
      n.levels <- factor.n.levels[count]
      coefficient.range <- insert.row:(insert.row + n.levels - 2)
      coeffs.tmp <- c(coeffs.tmp, "", coeffs[coefficient.range])
      lbs.tmp <- c(lbs.tmp, "", lbs[coefficient.range])
      ubs.tmp <- c(ubs.tmp, "", ubs[coefficient.range])
      if (bootstrap.type != "boot.meta.reg") {
        se.tmp <- c(se.tmp, "", se[coefficient.range])
        pvals.tmp <- c(pvals.tmp, "", pvals[coefficient.range])
        statistics.tmp <- c(statistics.tmp, "", statistics[coefficient.range])
        dfs.tmp <- c(dfs.tmp, "", dfs[coefficient.range])
      }
      insert.row <- insert.row + n.levels - 1
    }
    reg.array[2:n.rows, "Level"] <- levels.display.col
    reg.array[2:n.rows, "Studies"] <- studies.display.col
  }

  reg.array[2:n.rows, "Covariate"] <- cov.display.col
  reg.array[2:n.rows, "Estimate"] <- coeffs.tmp
  reg.array[2:n.rows, ci.labels[[1]]] <- lbs.tmp
  reg.array[2:n.rows, ci.labels[[2]]] <- ubs.tmp
  if (bootstrap.type != "boot.meta.reg") {
    reg.array[2:n.rows, "Std. error"] <- se.tmp
    reg.array[2:n.rows, if (t.inference) "t" else "z"] <- statistics.tmp
    if (t.inference) reg.array[2:n.rows, "df"] <- dfs.tmp
    reg.array[2:n.rows, "p-value"] <- pvals.tmp
  }
  class(reg.array) <- "summary.data"

  metric.name <- pretty.metric.name(as.character(params$measure))
  if (bootstrap.type == "boot.meta.reg") {
    model.title <- paste("Bootstrapped Meta-Regression based on ", params$num.bootstrap.replicates,
                         " replicates.\n\n", params$extra.attempts,
                         " resampling attempts failed.\n\nMetric: ", metric.name, sep="")
    reg.disp <- list(model.title=model.title, table.titles="Coefficient estimates",
                     arrays=list(reg.array), MAResults=res)
    class(reg.disp) <- "summary.display"
    return(reg.disp)
  }

  model.title <- paste("Meta-Regression\n\nMetric: ", metric.name, sep="")
  method.names <- rcmetar.random.effects.method.names()
  estimator <- if (identical(as.character(res$method), "FE")) {
    "Fixed effect"
  } else if (as.character(res$method) %in% names(method.names)) {
    method.names[[as.character(res$method)]]
  } else {
    as.character(res$method)
  }
  inference.label <- rcmetar.inference.method.names()[[inference.method]]
  residual.df <- res$k - res$p
  overview <- rcmetar.regression.summary.array(list(
    c("Studies analyzed", as.character(res$k)),
    c("Model coefficients", as.character(res$p)),
    c("Residual degrees of freedom", as.character(residual.df)),
    c("Heterogeneity estimator", estimator),
    c("Inference Method", inference.label)
  ))

  specification.rows <- list()
  continuous.names <- display.data$cont.cov.names
  continuous.ranges <- display.data$cont.cov.ranges
  if (is.null(continuous.names)) continuous.names <- cov.display.col[seq_len(n.cont.covs) + 1]
  for (name in continuous.names) {
    observed.range <- continuous.ranges[[name]]
    range.label <- if (length(observed.range) == 2 && all(is.finite(observed.range))) {
      paste0("Continuous; observed range ", sprintf(digits.str, observed.range[1]),
             " to ", sprintf(digits.str, observed.range[2]))
    } else {
      "Continuous"
    }
    specification.rows[[length(specification.rows) + 1]] <- c(name, range.label)
  }
  factor.names <- display.data$factor.cov.names
  factor.references <- display.data$factor.ref.levels
  if (!is.null(factor.names)) {
    for (index in seq_along(factor.names)) {
      specification.rows[[length(specification.rows) + 1]] <- c(
        factor.names[index], paste0("Categorical; reference level: ", factor.references[index]))
    }
  }
  zero.outside <- any(vapply(continuous.names, function(name) {
    observed.range <- continuous.ranges[[name]]
    length(observed.range) == 2 && all(is.finite(observed.range)) &&
      (0 < observed.range[1] || 0 > observed.range[2])
  }, logical(1)))
  intercept.note <- "Estimated effect at continuous moderator value zero and categorical reference levels"
  if (zero.outside) intercept.note <- paste0(intercept.note, "; extrapolated beyond an observed continuous range")
  specification.rows <- c(list(c("Intercept", intercept.note)), specification.rows)
  specification <- rcmetar.regression.summary.array(specification.rows, c("Term", "Specification"))

  scale <- get.scale(params)
  coefficient.title <- if (scale %in% c("log", "logit", "arcsine")) {
    paste0("Coefficient estimates (", scale, " scale)")
  } else {
    "Coefficient estimates"
  }

  arrays <- list(overview, specification, reg.array)
  titles <- c("Model overview", "Model specification", coefficient.title)

  if (!identical(as.character(res$method), "FE")) {
    heterogeneity <- rcmetar.regression.summary.array(list(
      c("Residual heterogeneity (\u03c4\u00b2)", rcmetar.regression.display.value(res$tau2, result.digits)),
      c("SE of \u03c4\u00b2", rcmetar.regression.display.value(res$se.tau2, se.digits)),
      c("Residual heterogeneity (\u03c4)", rcmetar.regression.display.value(sqrt(res$tau2), result.digits)),
      c("Residual I\u00b2", rcmetar.regression.display.value(res$I2, 1L, percent=TRUE)),
      c("Residual H\u00b2", rcmetar.regression.display.value(res$H2, result.digits)),
      c("Heterogeneity explained (R\u00b2)", rcmetar.regression.display.value(res$R2, 1L, percent=TRUE))
    ))
    arrays <- c(arrays, list(heterogeneity))
    titles <- c(titles, "Residual heterogeneity")
  }

  moderator.df2 <- if (t.inference) residual.df else NULL
  moderator.label <- if (t.inference) "Overall moderators (F)" else "Overall moderators (Q\u2098)"
  test.rows <- list(rcmetar.regression.test.row(
    moderator.label, res$QM, res$m, res$QMp, moderator.df2, params$digits))
  factor.tests <- rcmetar.regression.factor.tests(res, display.data, params)
  for (name in names(factor.tests)) {
    factor.test <- factor.tests[[name]]$result
    statistic <- if (!is.null(factor.test$QM)) factor.test$QM else factor.test$F
    df1 <- factor.tests[[name]]$df1
    test.rows[[length(test.rows) + 1]] <- rcmetar.regression.test.row(
      paste0(name, " (joint)"), statistic, df1, factor.test$QMp,
      if (t.inference) residual.df else NULL, params$digits)
  }
  test.rows[[length(test.rows) + 1]] <- rcmetar.regression.test.row(
    "Residual heterogeneity (Q\u2091)", res$QE, residual.df, res$QEp,
    NULL, params$digits)
  tests <- rcmetar.regression.summary.array(test.rows, c("Test", "Statistic", "df", "p-value"))
  arrays <- c(arrays, list(tests))
  titles <- c(titles, "Model tests")

  notes <- if (!identical(as.character(res$method), "FE")) {
    "Heterogeneity explained (R\u00b2) is the proportional reduction in estimated between-study heterogeneity relative to the corresponding model without moderators."
  } else {
    NULL
  }
  reg.disp <- list(model.title=model.title, table.titles=titles, arrays=arrays,
                   notes=notes, MAResults=res)
  class(reg.disp) <- "summary.display"
  reg.disp
}

adjusted_means_display <- function(res, params, display.data) {
  display.scale <- function(x, metric) {
    if (metric.is.log.scale(metric)) {
      exp(x)
    } else if (metric.is.logit.scale(metric)) {
      invlogit(x)
    } else if (metric.is.arcsine.scale(metric)) {
      invarcsine.sqrt(x)
    } else {
      x
    }
  }

  factor.n.levels <- display.data$factor.n.levels
  if (length(factor.n.levels) != 1) {
    stop("adjusted_means_display requires exactly one factor covariate")
  }
  if (!is.null(display.data$n.cont.covs) && display.data$n.cont.covs != 0) {
    stop("adjusted_means_display does not support continuous covariates")
  }

  n.levels <- factor.n.levels[[1]]
  if (n.levels < 2) {
    stop("adjusted_means_display requires at least two factor levels")
  }
  levels.display.col <- display.data$levels.display.col
  studies.display.col <- display.data$studies.display.col

  coefficient.count <- length(as.vector(res$b))
  if (coefficient.count < n.levels) {
    stop("meta-regression result has fewer coefficients than factor levels")
  }

  mult <- get.mult.from.conf.level(params$conf.level)
  digits.str <- paste("%.", display.digits(params), "f", sep="")
  se.digits.str <- paste("%.", display.digits(params, minimum=3L), "f", sep="")

  design.matrix <- cbind(
    Intercept=rep(1, n.levels),
    rbind(rep(0, n.levels - 1), diag(n.levels - 1))
  )
  betas <- as.matrix(res$b[1:n.levels, , drop=FALSE])
  covariance <- as.matrix(res$vb[1:n.levels, 1:n.levels, drop=FALSE])

  estimates <- as.vector(design.matrix %*% betas)
  variances <- diag(design.matrix %*% covariance %*% t(design.matrix))
  se <- sqrt(variances)
  ci.lb <- estimates - mult * se
  ci.ub <- estimates + mult * se

  estimates.disp <- display.scale(estimates, params$measure)
  ci.lb.disp <- display.scale(ci.lb, params$measure)
  ci.ub.disp <- display.scale(ci.ub, params$measure)

  ci.labels <- display.confidence.interval.labels(params)
  adj.array <- array(
    dim=c(n.levels + 1, 6),
    dimnames=list(NULL, c("Level", "Studies", "Estimate", ci.labels, "Std. error"))
  )
  adj.array[1,] <- c("Level", "Studies", "Estimate", ci.labels, "Std. error")
  level.start <- display.data$n.cont.covs + 2
  level.end <- level.start + n.levels - 1
  if (length(levels.display.col) < level.end || length(studies.display.col) < level.end) {
    stop("display data does not contain factor levels")
  }
  adj.array[2:(n.levels + 1), "Level"] <- levels.display.col[level.start:level.end]
  adj.array[2:(n.levels + 1), "Studies"] <- studies.display.col[level.start:level.end]
  adj.array[2:(n.levels + 1), "Estimate"] <- sprintf(digits.str, estimates.disp)
  adj.array[2:(n.levels + 1), ci.labels[[1]]] <- sprintf(digits.str, ci.lb.disp)
  adj.array[2:(n.levels + 1), ci.labels[[2]]] <- sprintf(digits.str, ci.ub.disp)
  adj.array[2:(n.levels + 1), "Std. error"] <- sprintf(se.digits.str, se)

  metric.name <- pretty.metric.name(as.character(params$measure))
  model.title <- paste("Adjusted Means\n\nMetric: ", metric.name, sep="")
  adj.disp <- list(
    "model.title" = model.title,
    "table.titles" = c("Adjusted Means"),
    "arrays" = list(arr1=adj.array),
    "MAResults" = list(b=estimates, se=se, ci.lb=ci.lb, ci.ub=ci.ub)
  )
  class(adj.disp) <- "summary.display"
  adj.disp
}

create.overall.display <- function(res, study.names, params, model.title, data.type) {
  if (data.type == "continuous") {
    transform.name <- "continuous.transform.f"
  } else if (data.type == "diagnostic") {
    transform.name <- "diagnostic.transform.f"
  }  else {
    transform.name <- "binary.transform.f"
  }
  scale.str <- get.scale(params)
  overall.array <- array(dim=c(length(study.names) + 1, 6))

  overall.array[1,] <- c("Studies", "Estimate", display.confidence.interval.labels(params), "Std. error", "p-value")

  for (count in 1:length(res)) {
    y <- res[[count]]$b
    lb <- res[[count]]$ci.lb
    ub <- res[[count]]$ci.ub
    se <- res[[count]]$se
    digits.str <- paste("%.", display.digits(params), "f", sep="")
    se.digits.str <- paste("%.", display.digits(params, minimum=3L), "f", sep="")
    y.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(y, n=NULL))
    lb.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(lb, n=NULL))
    ub.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(ub, n=NULL))
    se.disp <- sprintf(se.digits.str, se)

    pVal <- format.p.value.display(res[[count]]$pval, params$digits)
    overall.array[count+1,] <- c(study.names[count], y.disp, lb.disp, ub.disp, se.disp, pVal)
  }

  table.titles <- c("Model Results")
  arrays <- list(arr1=overall.array)
  overall.disp <- list("model.title" = model.title, "table.titles" = table.titles, "arrays" = arrays,
             "MAResults" = res )
  class(overall.disp) <- "summary.display"
  overall.disp
}

create.subgroup.display <- function(res, study.names, params, model.title, data.type) {
  if (data.type == "continuous") {
    transform.name <- "continuous.transform.f"
  } else if (data.type == "diagnostic") {
    transform.name <- "diagnostic.transform.f"
  }  else {
    transform.name <- "binary.transform.f"
  }
  scale.str <- "standard"
  if (metric.is.log.scale(params$measure)){
    scale.str <- "log"
  } else if (metric.is.logit.scale(params$measure)) {
    scale.str <- "logit"
  }
  subgroup.array <- array(dim=c(length(study.names) + 1, 8))
  het.array <- array(dim=c(length(study.names) + 1, 4))

  n <- length(study.names)

  subgroup.array[1,] <- c("Subgroups", "Studies", "Estimate", display.confidence.interval.labels(params), "Std. error", "p-value", "z-value")
  het.array[1,] <- c("Studies", "Q (df)",
               "Het. p-value", "I\u00b2")
  for (count in 1:length(study.names)) {
    num.studies <- res[[count]]$k
    y <- res[[count]]$b
    lb <- res[[count]]$ci.lb
    ub <- res[[count]]$ci.ub
    se <- res[[count]]$se
    digits.str <- paste("%.", display.digits(params), "f", sep="")
    se.digits.str <- paste("%.", display.digits(params, minimum=3L), "f", sep="")
    y.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(y, n))
    lb.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(lb, n))
    ub.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(ub, n))
    se.disp <- sprintf(se.digits.str, se)
    if (!display.value.is.missing(res[[count]]$QE)) {
      degf <- res[[count]]$k - 1
      QE <- sprintf(digits.str, res[[count]]$QE)
      QE <- paste(QE, " (", degf,")", sep="")
    } else {
      QE <- ""
    }
    I2 <- format.percent.display(res[[count]]$I2, "%.1f")
    QEp <- format.p.value.display(res[[count]]$QEp, params$digits)
    pVal <- format.p.value.display(res[[count]]$pval, params$digits)
    zVal <- g.round.display.zval(res[[count]]$zval, digits=params$digits)

    if (is.null(num.studies))
      num.studies <- 1

    subgroup.array[count+1,] <- c(study.names[count], num.studies, y.disp, lb.disp, ub.disp, se.disp, pVal, zVal)
    het.array[count+1,] <- c(study.names[count], QE, QEp, I2)
  }

  table.titles <- c("Model Results", "Heterogeneity")
  arrays <- list(arr1=subgroup.array, arr2=het.array)
  subgroup.disp <- list("model.title" = model.title, "table.titles" = table.titles, "arrays" = arrays,
             "MAResults" = res )
  class(subgroup.disp) <- "summary.display"
  subgroup.disp
}


results.short.list <- function(res) {
  res.short <- list("b"=res$b[1], "ci.lb"=res$ci.lb, "ci.ub"=res$ci.ub)
}

calc.ci.bounds <- function(om.data, params, ...) {
  y <- om.data@y
  se <- om.data@SE
  mult <- get.mult.from.conf.level(params$conf.level)
  lb <- y - mult*om.data@SE
  ub <- y + mult*om.data@SE
  extra.args <- list(...)
  if (params$measure=="PR") {
    for (i in 1:length(lb)) {
      lb[i] <- max(lb[i], 0)
      ub[i] <- min(ub[i], 1)
    }
  }
  if (params$measure=="PAS") {
    for (i in 1:length(lb)) {
      lb[i] <- max(lb[i], asin(0))
      ub[i] <- min(ub[i], asin(1))
    }
  }
  if (params$measure=="PFT") {
    n <- extra.args[['ni']]
    for (i in 1:length(lb)) {
      lb[i] <- max(lb[i], transf.pft(0, n[i]))
      ub[i] <- min(ub[i], transf.pft(1, n[i]))
    }
  }

  study.ci.bounds <- list(lb=lb, ub=ub)
}

write.results.to.file <- function(om.data, params, res, outpath) {
  transform.name <- get.transform.name(om.data)
  results.df <- data.frame("Summary.estimate" = eval(call(transform.name, params$measure))$display.scale(res$b, n),
               "Lower.bound" = eval(call(transform.name, params$measure))$display.scale(res$ci.lb, n),
               "Upper.bound" = eval(call(transform.name, params$measure))$display.scale(res$ci.ub, n),
               "p-value" = res$pval)
  write.csv(results.df, file=outpath, row.names=FALSE)
}

get.transform.name <- function(om.data) {
  if ("ContinuousData" %in% class(om.data)) {
    transform.name <-"continuous.transform.f"
    data.type <- "continuous"
  } else if ("DiagnosticData" %in% class(om.data)) {
    transform.name <- "diagnostic.transform.f"
    data.type <- "diagnostic"
  } else if ("BinaryData" %in% class(om.data)) {
    transform.name <- "binary.transform.f"
    data.type <- "binary"
  }
  transform.name
}

get.scale <- function(params) {
  if (metric.is.log.scale(params$measure)){
    scale <- "log"
  } else if (metric.is.logit.scale(params$measure)) {
    scale <- "logit"
  } else if (metric.is.arcsine.scale(params$measure)) {
    scale <- "arcsine"
  } else {
    scale <- "standard"
  }
  scale
}

metric.is.log.scale <- function(metric){
  metric %in% c(binary.log.metrics, diagnostic.log.metrics)
}

metric.is.logit.scale <- function(metric) {
  metric %in% c(binary.logit.metrics, diagnostic.logit.metrics)
}

metric.is.arcsine.scale <- function(metric) {
  metric %in% c(binary.arcsine.metrics)
}

metric.is.freeman_tukey.scale <- function(metric) {
  metric %in% c(binary.freeman_tukey.metrics)
}

logit <- function(x) {
  log(x/(1-x))
}

invlogit <- function(x) {
  exp(x) / (1 + exp(x))
}

arcsine.sqrt <- function(x) {
  asin(sqrt(x))
}

invarcsine.sqrt <- function(x) {
  (sin(x))^2
}

freeman_tukey <- function(x,n) {
  if (length(x)==1) {
    hm <- 1/mean(1/n)
    y <- transf.pft(xi=x, ni=hm)
  } else {
    y <- transf.pft(xi=x, ni=n)
  }
  y
}

invfreeman_tukey <- function(x, n) {
   if (length(x)==1) {
     y <- transf.ipft.hm(xi=x, targs=list(ni=n))
   } else {
     y <- transf.ipft(x, n)
   }

   y

}


rma.uni.value.info <- function() {
  list(
    b    = list(type="vector", description='estimated coefficients of the model.'),
    se     = list(type="vector", description='standard errors of the coefficients.'),
    zval   = list(type="vector", description='test statistics of the coefficients.'),
    pval   = list(type="vector", description='p-values for the test statistics.'),
    ci.lb  = list(type="vector", description='lower bound of the confidence intervals for the coefficients.'),
    ci.ub  = list(type="vector", description='upper bound of the confidence intervals for the coefficients.'),
    vb     = list(type="vector", description='variance-covariance matrix of the estimated coefficients.'),
    tau2   = list(type="vector", description='estimated amount of (residual) heterogeneity. Always 0 when method="FE".'),
    se.tau2  = list(type="vector", description='estimated standard error of the estimated amount of (residual) heterogeneity.'),
    k    = list(type="vector", description='number of outcomes included in the model fitting.'),
    p    = list(type="vector", description='number of coefficients in the model (including the intercept).'),
    m    = list(type="vector", description='number of coefficients included in the omnibus test of coefficients.'),
    QE     = list(type="vector", description='test statistic for the test of (residual) heterogeneity.'),
    QEp    = list(type="vector", description='p-value for the test of (residual) heterogeneity.'),
    QM     = list(type="vector", description='test statistic for the omnibus test of coefficients.'),
    QMp    = list(type="vector", description='p-value for the omnibus test of coefficients.'),
    I2     = list(type="vector", description='value of I2. See print.rma.uni for more details.'),
    H2     = list(type="vector", description='value of H2. See print.rma.uni for more details.'),
    R2     = list(type="vector", description='value of R2. See print.rma.uni for more details.'),
    int.only = list(type="vector", description='logical that indicates whether the model is an intercept-only model.'),
    yi     = list(type="vector", description='the vector of outcomes'),
    vi     = list(type="vector", description='the corresponding sample variances'),
    X    = list(type="matrix", description='the model matrix of the model'),
    fit.stats= list(type="data.frame", description='a list with the log-likelihood, deviance, AIC, BIC, and AICc values under the unrestricted and restricted likelihood.'),

    weights = list(type="vector", description="weights in % given to the observed effects")
  )
}

cumul.rma.uni.value.info <- function() {
  list(
    estimate = list(type="vector", description='estimated coefficients of the model.'),
    se     = list(type="vector", description='standard errors of the coefficients. NA if transf is used to transform the coefficients.'),
    zval   = list(type="vector", description='test statistics of the coefficients.'),
    pval   = list(type="vector", description='p-values for the test statistics.'),
    ci.lb  = list(type="vector", description='lower bounds of the confidence intervals for the coefficients.'),
    ci.ub  = list(type="vector", description='upper bounds of the confidence intervals for the coefficients.'),
    QE     = list(type="vector", description='test statistics for the tests of heterogeneity.'),
    QEp    = list(type="vector", description='p-values for the tests of heterogeneity.'),
    tau2   = list(type="vector", description='estimated amounts of (residual) heterogeneity (only for random-effects models).'),
    I2     = list(type="vector", description='values of I2 .'),
    H2     = list(type="vector", description='values of H2 .')
    )
}

cumul.rma.mh.value.info <- function () {
  list(
    estimate = list(type="vector", description='estimated coefficients of the model.'),
    se     = list(type="vector", description='standard errors of the coefficients. NA if transf is used to transform the coefficients.'),
    zval   = list(type="vector", description='test statistics of the coefficients.'),
    pval   = list(type="vector", description='p-values for the test statistics.'),
    ci.lb  = list(type="vector", description='lower bounds of the confidence intervals for the coefficients.'),
    ci.ub  = list(type="vector", description='upper bounds of the confidence intervals for the coefficients.'),
    QE     = list(type="vector", description='test statistics for the tests of heterogeneity.'),
    QEp    = list(type="vector", description='p-values for the tests of heterogeneity.')
    )
}

loo.rma.uni.value.info <- function () {
  list(
    estimate = list(type="vector", description='estimated coefficients of the model.'),
    se     = list(type="vector", description='standard errors of the coefficients. NA if transf is used to transform the coefficients.'),
    zval   = list(type="vector", description='test statistics of the coefficients.'),
    pval   = list(type="vector", description='p-values for the test statistics.'),
    ci.lb  = list(type="vector", description='lower bounds of the confidence intervals for the coefficients.'),
    ci.ub  = list(type="vector", description='upper bounds of the confidence intervals for the coefficients.'),
    Q    = list(type="vector", description='test statistics for the tests of heterogeneity.'),
    Qp     = list(type="vector", description='p-values for the tests of heterogeneity.'),
    tau2   = list(type="vector", description='estimated amounts of (residual) heterogeneity (only for random-effects models).'),
    I2     = list(type="vector", description='values of I2 .'),
    H2     = list(type="vector", description='values of H2 .')
    )
}

loo.rma.mh.value.info <- function () {
  list(
    estimate = list(type="vector", description='estimated coefficients of the model.'),
    se     = list(type="vector", description='standard errors of the coefficients. NA if transf is used to transform the coefficients.'),
    zval   = list(type="vector", description='test statistics of the coefficients.'),
    pval   = list(type="vector", description='p-values for the test statistics.'),
    ci.lb  = list(type="vector", description='lower bounds of the confidence intervals for the coefficients.'),
    ci.ub  = list(type="vector", description='upper bounds of the confidence intervals for the coefficients.'),
    Q    = list(type="vector", description='test statistics for the tests of heterogeneity.'),
    Qp     = list(type="vector", description='p-values for the tests of heterogeneity.')
  )
}

capture.output.and.collapse <- function (x) {
  output <- paste(capture.output(print(x)), collapse="\n")
  output
}
