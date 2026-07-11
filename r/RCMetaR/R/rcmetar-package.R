#' RCMetaR: R component for RC MetaStudio
#'
#' R component for RC MetaStudio, a graphical user interface for performing
#' meta-analysis.
#'
#' RCMetaR contains the statistical routines used by RC MetaStudio. The
#' package-level interface is the \code{rcmetar.*} core facade documented in
#' \code{\link{RCMetaR-core-api}}; older method, plotting, transformation, and
#' data-completion functions are private implementation details behind that
#' facade.
#'
#' @seealso
#' \code{\link{RCMetaR-core-api}},
#' \code{\link{RCMetaR-data-classes}},
#' \code{\link{RCMetaR-binary-methods}},
#' \code{\link{RCMetaR-continuous-methods}},
#' \code{\link{RCMetaR-diagnostic-methods}},
#' \code{\link{RCMetaR-repeated-analyses}},
#' \code{\link{RCMetaR-meta-regression}},
#' \code{\link{RCMetaR-plotting}},
#' \code{\link{RCMetaR-data-completion}},
#' \code{\link{RCMetaR-hsroc-helpers}}
#'
#' @keywords internal
"_PACKAGE"

#' Namespace directives for RCMetaR's core package interface
#'
#' The Python application calls the small \code{rcmetar.*} facade. Legacy
#' implementation functions stay loadable inside the package namespace but are
#' intentionally not exported as caller-facing interface.
#'
#' @import boot
#' @import grDevices
#' @import graphics
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
