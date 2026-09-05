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
