#' OpenMetaR: R component for Open Meta-Analyst
#'
#' R component for Open Meta-Analyst, a graphical user interface for performing
#' meta-analysis.
#'
#' OpenMetaR contains the statistical routines used by Open Meta-Analyst. The
#' package-level interface is the \code{openmetar.*} core facade documented in
#' \code{\link{openmetar-core-api}}; older method, plotting, transformation, and
#' data-completion functions are private implementation details behind that
#' facade.
#'
#' @seealso
#' \code{\link{openmetar-core-api}},
#' \code{\link{openmetar-data-classes}},
#' \code{\link{openmetar-binary-methods}},
#' \code{\link{openmetar-continuous-methods}},
#' \code{\link{openmetar-diagnostic-methods}},
#' \code{\link{openmetar-repeated-analyses}},
#' \code{\link{openmetar-meta-regression}},
#' \code{\link{openmetar-plotting}},
#' \code{\link{openmetar-data-completion}},
#' \code{\link{openmetar-hsroc-helpers}}
#'
#' @keywords internal
"_PACKAGE"

#' Namespace directives for OpenMetaR's core package interface
#'
#' The Python application calls the small \code{openmetar.*} facade. Legacy
#' implementation functions stay loadable inside the package namespace but are
#' intentionally not exported as caller-facing interface.
#'
#' @import boot
#' @import grDevices
#' @import graphics
#' @import grid
#' @import HSROC
#' @import lme4
#' @import metafor
#' @import pdftools
#' @import stats
#' @import utils
#' @importFrom methods is new setClass
#' @rawNamespace S3method(print,summary.data)
#' @rawNamespace S3method(print,summary.display)
#' @rawNamespace exportClasses(AnalysisSpecification, BinaryData, ContinuousData, CovariateValues, DiagnosticData, OMData)
#' @noRd
NULL

if (getRversion() >= "2.15.1") {
    utils::globalVariables(c(
        "CONF.LEVEL.GLOBAL",
        "adjusted_means_display",
        "boot.cond.means.display",
        "cond_means_display",
        "cov.names",
        "create.regression.disp",
        "extract.plot.options",
        "forest.plot.of.regression.coefficients",
        "format.effect.size.col",
        "generate.a.matrix",
        "n",
        "om.data",
        "res",
        "selected.cov",
        "summary.est",
        "types",
        "user.ticks",
        "x",
        "yi"
    ))
}
