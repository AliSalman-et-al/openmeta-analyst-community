% Generated for RCMetaR's guided small-study effects interface.
\name{RCMetaR-publication-bias}
\alias{rcmetar.run.small.study.effects}
\alias{rcmetar.regenerate.small.study.funnel}
\title{Guided small-study effects analysis}
\description{Computes method-specific eligibility, selected asymmetry procedures, pooled display models, and funnel plot artifacts in one serialized RCMetaR operation. Results describe associations between study size or precision and observed effects; they do not establish that publication bias exists.}
\usage{
rcmetar.run.small.study.effects(om.data, params = list())
rcmetar.regenerate.small.study.funnel(om.data, res, params, output.path = NULL)
}
\arguments{
  \item{om.data}{An RCMetaR analysis data object.}
  \item{params}{A named request list.}
  \item{res}{The persisted pooled model for the run.}
  \item{output.path}{Optional output image path.}
}
\value{A typed eligibility report, analysis result list, or regenerated funnel path.}
