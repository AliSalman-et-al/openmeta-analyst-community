# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

####################################
#                                  #
# RC MetaStudio                #
# ----                             #
# utilities.R                      #
#                                  #
# Utilities for pretty-printing    #
# results.                         #
####################################


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
  #
  # Prints a summary results
  # summary.disp is a list containing the following named items
  # - model.title - a string that appears at the top of the summary.
  # - table.titles - a vector of titles for the results tables
  #   Setting a table title to NA prevents the table from being printed.
  # - arrays - a list of arrays, of the same length as table.titles,
  #   which are pretty-printed by print.summary.data 
  #
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
  # Prints an array table.data.
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
    "bootstrap"=c(
      "Bootstrap methods: Davison, A. C., & Hinkley, D. V. (1997). Bootstrap Methods and Their Application. Cambridge University Press.",
      "Bootstrap confidence intervals: DiCiccio, T. J., & Efron, B. (1996). Bootstrap confidence intervals. Statistical Science, 11(3), 189-228.",
      "Bootstrap methods: Efron, B., & Tibshirani, R. (1993). An Introduction to the Bootstrap. Chapman & Hall."
    ),
    "hsroc"=c(
      "HSROC model: Rutter, C. M., & Gatsonis, C. A. (2001). A hierarchical regression approach to meta-analysis of diagnostic accuracy evaluations. Statistics in Medicine, 20(19), 2865-2884.",
      "HSROC without a gold standard: Dendukuri, N., Schiller, I., Joseph, L., & Pai, M. (2012). Bayesian meta-analysis of the accuracy of a test for tuberculosis pleuritis in the absence of a gold-standard reference. Biometrics. doi:10.1111/j.1541-0420.2012.01773.x"
    ),
    "diagnostic.bivariate"=c(
      "Bivariate diagnostic meta-analysis: Reitsma, J. B., Glas, A. S., Rutjes, A. W., Scholten, R. J., Bossuyt, P. M., & Zwinderman, A. H. (2005). Bivariate analysis of sensitivity and specificity produces informative summary measures in diagnostic reviews. Journal of Clinical Epidemiology, 58(10), 982-990.",
      "Diagnostic accuracy model unification: Harbord, R. M., Deeks, J. J., Egger, M., Whiting, P., & Sterne, J. A. (2006). A unification of models for meta-analysis of diagnostic accuracy studies. Biostatistics, 8(2), 239-251.",
      "Fitting engine reference: Bates, D., Maechler, M., Bolker, B., & Walker, S. (2015). Fitting linear mixed-effects models using lme4. Journal of Statistical Software, 67(1), 1-48. doi:10.18637/jss.v067.i01."
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
  # Adds spaces to beginning and end of entry
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
  # creates a string in which symbol is repeated num.repeats times
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

g.round.display.zval <- function(x, digits) {
  # just for use in # create.subgroup.display for rounding the (single) zvals
  if (display.value.is.missing(x)) {
    return("")
  }
  digits.str <- paste("%.", digits, "f", sep="")
  x.disp <- c()
  
  x.disp[x < 0 && abs(x) < 10^(-digits)] <- paste(">","-",10^(-digits)," & <0",sep="")
  x.disp[x < 0 && abs(x) >= 10^(-digits)] <- sprintf(digits.str, x[x < 0 && abs(x)>=10^(-digits)])
  
  x.disp[x>0 && x < 10^(-digits)] <- paste("< ", 10^(-digits), sep="")
  x.disp[x>0 && x >= 10^(-digits)] <- sprintf(digits.str, x[x>0 && x>=10^(-digits)])
  x.disp
}
  

create.summary.disp <- function(om.data, params, res, model.title) {
  # create tables for diplaying summary of ma results
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
  # Set n, the vector of numbers of studies, for PFT metric.
  if (params$measure=="PFT" && length(om.data@g1O1) > 0 && length(om.data@g1O2) > 0) {
    n <- om.data@g1O1 + om.data@g1O2  # Number of subjects - needed for Freeman-Tukey double arcsine trans.
  }
  else {
    n <- NULL # don't need n except for PFT (freeman-tukey)
  }
  QE <- format.numeric.display(res$QE, digits.str)
  QEp <- format.p.value.display(res$QEp, params$digits)
  pVal <- format.p.value.display(res$pval, params$digits)

  res.title <- "Model Results"
  #y.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(res$b, list(ni=n)))
  #lb.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(res$ci.lb, list(ni=n)))
  #ub.disp <- sprintf(digits.str, eval(call(transform.name, params$measure))$display.scale(res$ci.ub, list(ni=n)))
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
    # display and calculation scales are different - create two tables for results
    res.col.labels <- c("Estimate", "Lower bound", "Upper bound","p-value")
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
    # display and calculation scales are the same - create one table for results
    col.labels <- c("Estimate", "Lower bound", "Upper bound", "Std. error", "p-value")
    col.vals <- c(y.disp, lb.disp, ub.disp, se, pVal)
    res.array <- rbind(col.labels, col.vals)
    arrays = list(arr1=res.array, arr2=het.array)
    table.titles <- c(res.title, het.title)
    notes <- NULL
  }
  
  #if (transform.name == "binary.transform.f") {
    # Add raw data title and array 
    # raw.data.array <- create.binary.data.array(om.data, params, res)
    # table.titles <- c(" Study Data", table.titles)
    # raw.data.list <- list("arr0"=raw.data.array)
    # arrays <- c(raw.data.list, arrays)
  #} else if (transform.name == "continuous.transform.f") {
    #raw.data.array <- create.cont.data.array(om.data, params, res)
    #table.titles <- c(" Study Data", table.titles)
    #raw.data.list <- list("arr0"=raw.data.array)
    #arrays <- c(raw.data.list, arrays)
  #}
  # Above code can be re-enabled when write.x.study.data.to.file is fixed.
  
  summary.disp <- list(
    "model.title" = model.title,
    "table.titles" = table.titles,
    "arrays" = arrays,
    "notes" = notes,
    "MAResults" = res)
  class(summary.disp) <- "summary.display"
  summary.disp
}

# save.plot.data intentionally persists only plot data; save.data stores the
# broader analysis payload.
save.plot.data <- function(plot.data, out.path=NULL) {
  # saves plot data to the RC MetaStudio scratch directory
  if (is.null(out.path)){
    # Use the current system time as a unique-enough default filename.
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }
  ### save plot data *only*
  save(plot.data, file=paste(out.path, ".plotdata", sep=""))
  out.path
}

# Save plot data, parameters, and model results for editable forest plots.
save.plot.data.and.params <- function(data, params, res, level, out.path=NULL) {
  # saves plot data to the RC MetaStudio scratch directory
  if (is.null(out.path)){
    # Use the current system time as a unique-enough default filename.
    out.path <- rcmetar.scratch.path(as.character(as.numeric(Sys.time())))
  }
  
  ### save plot data
  save(data, file=paste(out.path, ".data", sep=""))
  
  ### save params
  save(params, file=paste(out.path, ".params", sep=""))
  
  ### save res
  save(res, file=paste(out.path, ".res", sep=""))
  
  ### save level
  save(level, file=paste(out.path, ".level", sep=""))
  
  out.path
}


save.data <- function(om.data, res, params, plot.data, out.path=NULL) {
  # this saves *all* the data for certain types of plots, in contrast
  # to the above method (save.plot.data), which saves only the plot.data
  # object.
  #
  # save the data, result and plot parameters to a tmp file on disk
  if (is.null(out.path)){
    # by default, we use thecurrent system time as a 'unique enough' filename
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

create.regression.display <- function(res, params, display.data) {
  
  if (is.null(params$bootstrap.type))
    bootstrap.type <- ""
  else
    bootstrap.type <- as.character(params$bootstrap.type) # will be null if not bootstrap
  
  
  # create table for diplaying summary of regression ma results
  cov.display.col <- display.data$cov.display.col
  levels.display.col <- display.data$levels.display.col
  studies.display.col <- display.data$studies.display.col
  # first two columns of table
  factor.n.levels <- display.data$factor.n.levels
  n.cont.covs <- display.data$n.cont.covs
  n.cont.rows <- n.cont.covs + 1 # extra row for intercept
  n.factor.covs <- length(factor.n.levels)
  n.rows <- length(cov.display.col) + 1
  # extra row for col. labels
  if (n.factor.covs==0) {
    col.labels <- switch(bootstrap.type,
               boot.meta.reg=c("Covariate", "Coefficients", "Lower bound", "Upper bound"),
               c("Covariate", "Coefficients", "Lower bound", "Upper bound", "Std. error", "p-value"))
    #col.labels <- c("Covariate", "Coefficients", "Lower bound", "Upper bound", "Std. error", "p-value")
  } else {
    col.labels <- switch(bootstrap.type,
        boot.meta.reg=col.labels <- c("Covariate", "Level", "Studies", "Coefficients", "Lower bound", "Upper bound"),
        col.labels <- c("Covariate", "Level", "Studies", "Coefficients", "Lower bound", "Upper bound", "Std. error", "p-value"))
    #col.labels <- c("Covariate", "Level", "Studies", "Coefficients", "Lower bound", "Upper bound", "Std. error", "p-value")
  }
    
  reg.array <- array(dim=c(length(cov.display.col)+1, length(col.labels)), dimnames=list(NULL, col.labels))
  reg.array[1,] <- col.labels
  result.digits <- display.digits(params)
  se.digits <- display.digits(params, minimum=3L)
  digits.str <- paste("%.", result.digits, "f", sep="")
  coeffs <- sprintf(digits.str, res$b)#; print(paste(c("coeffs:", coeffs))); ###
  if (bootstrap.type!="boot.meta.reg") {
    se <- round.display(res$se, digits=se.digits)
    pvals <- format.p.value.display(res$pval, params$digits)
  }
  lbs <- sprintf(digits.str, res$ci.lb)
  ubs <- sprintf(digits.str, res$ci.ub)
  
  coeffs.tmp <- coeffs[1:n.cont.rows]
  # extra row for intercept
  if (bootstrap.type!="boot.meta.reg") {
    se.tmp <- se[1:n.cont.rows]
    pvals.tmp <- pvals[1:n.cont.rows]
  }
  lbs.tmp <- lbs[1:n.cont.rows]
  ubs.tmp <- ubs[1:n.cont.rows]
  if (n.factor.covs > 0) {
    # there are factor covariants - insert spaces for reference var. row.
    insert.row <- n.cont.rows + 1
    for (count in 1:n.factor.covs) {
    n.levels <- factor.n.levels[count]
    #print(paste(c("n.levels", n.levels))) #####
    coeffs.tmp <- c(coeffs.tmp,"", coeffs[insert.row:(insert.row + n.levels - 2)])
    if (bootstrap.type!="boot.meta.reg") {
      se.tmp <- c(se.tmp,"", se[insert.row:(insert.row + n.levels - 2)])
      pvals.tmp <- c(pvals.tmp,"",pvals[insert.row:(insert.row + n.levels - 2)])
    }
    lbs.tmp <- c(lbs.tmp,"",lbs[insert.row:(insert.row + n.levels - 2)])
    ubs.tmp <- c(ubs.tmp,"",ubs[insert.row:(insert.row + n.levels - 2)])
    insert.row <- insert.row + n.levels - 1
    #print(paste(c("insert.row after: ", insert.row))) ######
    }   
    reg.array[2:n.rows, "Level"] <- levels.display.col
    reg.array[2:n.rows, "Studies"] <- studies.display.col
  }

  
  
  # add data to array
  reg.array[2:n.rows,"Covariate"] <- cov.display.col
  reg.array[2:n.rows,"Coefficients"] <- coeffs.tmp
  reg.array[2:n.rows, "Lower bound"] <- lbs.tmp
  reg.array[2:n.rows, "Upper bound"] <- ubs.tmp
  if (bootstrap.type!="boot.meta.reg") {
    reg.array[2:n.rows,"Std. error"] <- se.tmp
    reg.array[2:n.rows, "p-value"] <- pvals.tmp
    
    omnibus.pval.array <- array(dim=c(1,1))
    omnibus.pval.array[1,1] <- format.p.value.display(res$QMp, params$digits)
    arrays <- list(arr1=reg.array, arr2=omnibus.pval.array)
  } else {
    arrays <- list(arr1=reg.array)
  }
  
  metric.name <- pretty.metric.name(as.character(params$measure)) 
  
  if (bootstrap.type!="boot.meta.reg") {
    model.title <- paste("Meta-Regression\n\nMetric: ", metric.name, sep="")
    reg.disp <- list("model.title" = model.title, "table.titles" = c("Model Results", "Omnibus p-value"), "arrays" = arrays, "MAResults" = res)
  } else {
    model.title <- paste("Bootstrapped Meta-Regression based on ", params$num.bootstrap.replicates, " replicates.\n\n", params$extra.attempts, " resampling attempts failed.\n\nMetric: ", metric.name, sep="")
    reg.disp <- list("model.title" = model.title, "table.titles" = c("Model Results"), "arrays" = arrays, "MAResults" = res)
  }
  

  class(reg.disp) <-  "summary.display"
  return(reg.disp)
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

  adj.array <- array(
    dim=c(n.levels + 1, 6),
    dimnames=list(NULL, c("Level", "Studies", "Estimate", "Lower bound", "Upper bound", "Std. error"))
  )
  adj.array[1,] <- c("Level", "Studies", "Estimate", "Lower bound", "Upper bound", "Std. error")
  level.start <- display.data$n.cont.covs + 2
  level.end <- level.start + n.levels - 1
  if (length(levels.display.col) < level.end || length(studies.display.col) < level.end) {
    stop("display data does not contain factor levels")
  }
  adj.array[2:(n.levels + 1), "Level"] <- levels.display.col[level.start:level.end]
  adj.array[2:(n.levels + 1), "Studies"] <- studies.display.col[level.start:level.end]
  adj.array[2:(n.levels + 1), "Estimate"] <- sprintf(digits.str, estimates.disp)
  adj.array[2:(n.levels + 1), "Lower bound"] <- sprintf(digits.str, ci.lb.disp)
  adj.array[2:(n.levels + 1), "Upper bound"] <- sprintf(digits.str, ci.ub.disp)
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
  # create tables for diplaying summary of meta-methods (cumulative and leave-one-out) results.
  if (data.type == "continuous") {
    transform.name <- "continuous.transform.f"
  } else if (data.type == "diagnostic") {
    transform.name <- "diagnostic.transform.f"
  }  else {  
    transform.name <- "binary.transform.f"
  }
  scale.str <- get.scale(params)
  overall.array <- array(dim=c(length(study.names) + 1, 6))
    #QLabel =  paste("Q(df = ", degf, ")", sep="")
  
  overall.array[1,] <- c("Studies", "Estimate", "Lower bound", "Upper bound", "Std. error", "p-value")
  
  # unpack the data
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
  # create table for diplaying summary of overall ma results
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
  #QLabel =  paste("Q(df = ", degf, ")", sep="")

  # hmm....
  n <- length(study.names)

  subgroup.array[1,] <- c("Subgroups", "Studies", "Estimate", "Lower bound", "Upper bound", "Std. error", "p-value", "z-value")
  het.array[1,] <- c("Studies", "Q (df)",
               "Het. p-value", "I\u00b2")
  # unpack the data
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

    # Single-study subgroup results may omit num.studies; treat that case as
    # one study for display formatting.
    if (is.null(num.studies))
      num.studies <- 1
     
    subgroup.array[count+1,] <- c(study.names[count], num.studies, y.disp, lb.disp, ub.disp, se.disp, pVal, zVal)
    het.array[count+1,] <- c(study.names[count], QE, QEp, I2)
  }

  table.titles <- c("Model Results", "Heterogeneity")
  arrays <- list(arr1=subgroup.array, arr2=het.array)
  #}
  subgroup.disp <- list("model.title" = model.title, "table.titles" = table.titles, "arrays" = arrays,
             "MAResults" = res )
  class(subgroup.disp) <- "summary.display"
  subgroup.disp
}


results.short.list <- function(res) {
  # extracts res$b, res$ci.lb, and res$ci.ub from res
  res.short <- list("b"=res$b[1], "ci.lb"=res$ci.lb, "ci.ub"=res$ci.ub)
}

calc.ci.bounds <- function(om.data, params, ...) {
  #  Calulate confidence interval bounds using normal approximation.
  y <- om.data@y
  se <- om.data@SE
  mult <- get.mult.from.conf.level(params$conf.level)
  lb <- y - mult*om.data@SE
  ub <- y + mult*om.data@SE
  extra.args <- list(...)
  # Check that bounds are in the range of the transformation and truncate if necessary.
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
  # write results to file
  transform.name <- get.transform.name(om.data) 
  results.df <- data.frame("Summary.estimate" = eval(call(transform.name, params$measure))$display.scale(res$b, n),
               "Lower.bound" = eval(call(transform.name, params$measure))$display.scale(res$ci.lb, n),
               "Upper.bound" = eval(call(transform.name, params$measure))$display.scale(res$ci.ub, n),
               "p-value" = res$pval)
  write.csv(results.df, file=outpath, row.names=FALSE)
}

get.transform.name <- function(om.data) { 
  # Get transform name for converting between display and calculation scales 
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
  # Get the transformation scale
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
   # n is either a 
   if (length(x)==1) {
     y <- transf.ipft.hm(xi=x, targs=list(ni=n))
   } else {
     y <- transf.ipft(x, n)
   }
    
   y
   # See "The Inverse of the Freeman-Tukey Double Arcsine Transformations,"
   # The American Statistician, Nov. 1978, Vol. 32, No. 4.
   
   #p <- 0.5 * (1 - sign(cos(2*x)) * (1 - (sin(2*x) + (sin(2*x) - 1/sin(2*x)) / n)^2)^0.5)
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

    # not part of rma.uni output
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
