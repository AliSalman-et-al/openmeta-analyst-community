\name{get.subset}
\alias{get.subset}
\title{Subset RCMetaR data}
\usage{
get.subset(omdata, indices, make.unique.names = FALSE)
}
\arguments{
\item{omdata}{An RCMetaR data object derived from \code{OMData}.}
\item{indices}{Study row indices to keep.}
\item{make.unique.names}{Whether duplicated study names should be made unique in the returned object.}
}
\value{
An object of the same RCMetaR data class containing only the selected study rows.
}
\description{
Creates a row subset of a binary, continuous, or diagnostic RCMetaR data object while preserving study metadata and covariates.
}
