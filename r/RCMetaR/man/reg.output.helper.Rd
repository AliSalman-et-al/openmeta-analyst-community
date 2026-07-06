\name{reg.output.helper}
\alias{reg.output.helper}
\title{Format meta-regression output sections}
\usage{
reg.output.helper(theData, rma.results, model.formula, digits)
}
\arguments{
\item{theData}{The data frame supplied to the meta-regression model.}
\item{rma.results}{A fitted meta-regression result object.}
\item{model.formula}{The model formula used for the fitted result.}
\item{digits}{Number of digits used when formatting coefficient output.}
}
\value{
A named list of formatted meta-regression output sections.
}
\description{
Builds textual coefficient, omnibus-test, and model-data sections for RCMetaR meta-regression summaries.
}
