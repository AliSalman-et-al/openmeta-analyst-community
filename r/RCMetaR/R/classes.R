# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

####################################
#                                  #
# RC MetaStudio                #
# ----                             #
# classes.R                        #
# contains RCMetaR data class      #
# definitions.                     #
#                                  #    
# (note that classes in R are      #
#   basically structs)             #
####################################

#
# This is the base class for RCMetaR study-data containers.
setClass("OMData", representation(study.names="character", notes="character", 
         years="integer", covariates="list"))

####
# BinaryData type
#
setClass("BinaryData", 
               representation(g1O1="numeric", g1O2="numeric", g2O1="numeric", g2O2="numeric",
               y="numeric", SE="numeric",
               g1.name="character", g2.name="character"), 
               contains="OMData")
        

####
# DiagnosticData type
#       
setClass("DiagnosticData", 
               representation(TP="numeric", FN="numeric", TN="numeric", FP="numeric", 
               y="numeric", SE="numeric", g1.name="character"), 
               contains="OMData")
               
####
# ContinuousData type
#       
setClass("ContinuousData", 
               representation(N1="numeric", mean1="numeric", sd1="numeric",
               N2="numeric", mean2="numeric", sd2="numeric",
               y="numeric", SE="numeric",
               g1.name="character", g2.name="character"), 
               contains="OMData")
               
               
#
# The specificiation class contains parameters, etc., for the method to be run
#
setClass("AnalysisSpecification", 
                representation(parameters="data.frame"))

#
# The covariate class contains covariate values.
#
setClass("CovariateValues", representation(cov.name="character", cov.vals="vector", cov.type="character", ref.var="character"))

get.subset <- function(omdata, indices, make.unique.names=FALSE) {
  if (!is(omdata, "OMData")) stop("RCMetaR data expected.")

  subset.slot <- function(values) {
    if (length(values) == 0) {
      return(values)
    }
    values[indices]
  }

  study.names <- omdata@study.names[indices]
  if (make.unique.names) {
    study.names <- make.unique(study.names)
  }
  covariates <- lapply(omdata@covariates, function(covariate) {
    new("CovariateValues",
        cov.name=covariate@cov.name,
        cov.vals=covariate@cov.vals[indices],
        cov.type=covariate@cov.type,
        ref.var=covariate@ref.var)
  })
  common.slots <- list(
    y=subset.slot(omdata@y),
    SE=subset.slot(omdata@SE),
    study.names=study.names,
    years=subset.slot(omdata@years),
    covariates=covariates,
    notes=omdata@notes
  )

  if (is(omdata, "BinaryData")) {
    return(do.call(new, c(list("BinaryData"), common.slots, list(
      g1O1=subset.slot(omdata@g1O1),
      g1O2=subset.slot(omdata@g1O2),
      g2O1=subset.slot(omdata@g2O1),
      g2O2=subset.slot(omdata@g2O2),
      g1.name=omdata@g1.name,
      g2.name=omdata@g2.name
    ))))
  }
  if (is(omdata, "ContinuousData")) {
    return(do.call(new, c(list("ContinuousData"), common.slots, list(
      N1=subset.slot(omdata@N1),
      mean1=subset.slot(omdata@mean1),
      sd1=subset.slot(omdata@sd1),
      N2=subset.slot(omdata@N2),
      mean2=subset.slot(omdata@mean2),
      sd2=subset.slot(omdata@sd2),
      g1.name=omdata@g1.name,
      g2.name=omdata@g2.name
    ))))
  }
  if (is(omdata, "DiagnosticData")) {
    return(do.call(new, c(list("DiagnosticData"), common.slots, list(
      TP=subset.slot(omdata@TP),
      FN=subset.slot(omdata@FN),
      TN=subset.slot(omdata@TN),
      FP=subset.slot(omdata@FP),
      g1.name=omdata@g1.name
    ))))
  }

  stop("Unsupported RCMetaR data class.")
}
