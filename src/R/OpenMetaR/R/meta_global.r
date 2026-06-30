###############################################################################
# Package-private value set from python to control confidence level. At the
# moment, it only affects calc.box.sizes in plotting.R.
.openmetar.state <- new.env(parent=emptyenv())
.openmetar.state$CONF.LEVEL.GLOBAL <- 95

get.mult.from.conf.level <- function() {
	alpha <- 1.0-(get.global.conf.level()/100.0)
	mult <- abs(qnorm(alpha/2.0))
}

set.global.conf.level <- function(conf.level) {
	.openmetar.state$CONF.LEVEL.GLOBAL <- conf.level
	#cat("R: Confidence level is now", CONF.LEVEL.GLOBAL)
	return(.openmetar.state$CONF.LEVEL.GLOBAL)
}

get.global.conf.level <- function(NA.if.missing=FALSE) {
	if (!exists("CONF.LEVEL.GLOBAL", envir=.openmetar.state, inherits=FALSE)) {
		if (NA.if.missing) {
			return(NA)
		} else {
			stop("Global confidence level not defined")
		}
	}
	return(.openmetar.state$CONF.LEVEL.GLOBAL)
}
################################################################################
	
