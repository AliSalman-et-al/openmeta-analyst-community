###############################################################################
# Package-private value set from python to control confidence level. At the
# moment, it only affects calc.box.sizes in plotting.R.
.rcmetar.state <- new.env(parent=emptyenv())
.rcmetar.state$CONF.LEVEL.GLOBAL <- 95

validate.conf.level <- function(conf.level) {
	if (length(conf.level) != 1 || !is.numeric(conf.level) ||
			is.na(conf.level) || !is.finite(conf.level) ||
			conf.level <= 0 || conf.level >= 100) {
		stop("Confidence level must be greater than 0 and less than 100.")
	}
	return(as.numeric(conf.level))
}

get.mult.from.conf.level <- function(conf.level=get.global.conf.level()) {
	conf.level <- validate.conf.level(conf.level)
	alpha <- 1.0-(conf.level/100.0)
	mult <- abs(qnorm(alpha/2.0))
	if (!is.finite(mult)) {
		stop("Confidence level produced a non-finite interval multiplier.")
	}
	return(mult)
}

set.global.conf.level <- function(conf.level) {
	conf.level <- validate.conf.level(conf.level)
	.rcmetar.state$CONF.LEVEL.GLOBAL <- conf.level
	#cat("R: Confidence level is now", CONF.LEVEL.GLOBAL)
	return(.rcmetar.state$CONF.LEVEL.GLOBAL)
}

get.global.conf.level <- function(NA.if.missing=FALSE) {
	if (!exists("CONF.LEVEL.GLOBAL", envir=.rcmetar.state, inherits=FALSE)) {
		if (NA.if.missing) {
			return(NA)
		} else {
			stop("Global confidence level not defined")
		}
	}
	return(.rcmetar.state$CONF.LEVEL.GLOBAL)
}
################################################################################
	
