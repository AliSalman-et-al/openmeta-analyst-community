isnt.null <- function(x){
    ! is.null(x)
}

isnt.na <- function(x) {
	!is.na(x)
}

IMAGINARY.THRESHOLD <- 1E-8


gimpute.bin.data <- function(bin.data) {
	metric <- as.character(bin.data[["metric"]])
	est    <- bin.data[["estimate"]]
	lower  <- bin.data[["lower"]]
	upper  <- bin.data[["upper"]]
	treatment_sample_size    <- bin.data[["N_A"]]
	control_sample_size    <- bin.data[["N_B"]]
	conf.level <- bin.data[["conf.level"]]

	effect_interval_complete <- isnt.null(est) & (isnt.null(lower) | isnt.null(upper))
	effect_interval_complete <- effect_interval_complete | (isnt.null(lower) & isnt.null(upper))
	has_required_inputs <- isnt.null(metric) & isnt.null(treatment_sample_size) & isnt.null(control_sample_size) &
						 effect_interval_complete & isnt.null(conf.level)
	if (!has_required_inputs) {
		return(list(FAIL=NA))
	}

	if (is.null(est))   est   <- NA
	if (is.null(lower)) lower <- NA
	if (is.null(upper)) upper <- NA

	mult <- get.mult.from.conf.level(conf.level)
	n <- control_sample_size + treatment_sample_size

	complete_effect_and_variance <- function (d=NA, lower=NA, upper=NA) {
		if (is.na(d))   d   <- (lower + upper)/2;
		if (is.na(upper)) upper <- 2*d - lower;
		if (is.na(lower)) lower <- 2*d - upper;

		b <- ((upper - d) / mult)^2
		res <- list(d=d, upper=upper, lower=lower, b=b)
	}

	impute_from_risk_difference <- function () {
		res <- complete_effect_and_variance(d=est, lower=lower, upper=upper)
		d <- res[["d"]]; b <- res[["b"]]

		A <- n;
		B <- (2*control_sample_size*d-n);
		C <- control_sample_size*(treatment_sample_size*b-d*(1-d));

		p0.op1 <- (-B+sqrt(B^2-4*A*C))/(2*A)
		p0.op2 <- (-B-sqrt(B^2-4*A*C))/(2*A)
		p1.op1 <- d + p0.op1
		p1.op2 <- d + p0.op2

		res <- list(op1=list(p0=p0.op1, p1=p1.op1), op2=list(p0=p0.op2, p1=p1.op2))
	}

	impute_from_log_odds_ratio <- function () {
		res <- complete_effect_and_variance(d=log(est), lower=log(lower), upper=log(upper))
		d <- res[["d"]]; b <- res[["b"]]

		d <- exp(d)

		A <- control_sample_size*(1-d)^2+b*d*control_sample_size*treatment_sample_size
		B <- -1*(2*control_sample_size*(1-d)+b*d*control_sample_size*treatment_sample_size)
		C <- control_sample_size + d*treatment_sample_size

		p0.op1 <- (-B+sqrt(B^2-4*A*C))/(2*A)
		p0.op2 <- (-B-sqrt(B^2-4*A*C))/(2*A)
		p1.op1 <- d*p0.op1/(d*p0.op1+1-p0.op1)
		p1.op2 <- d*p0.op2/(d*p0.op2+1-p0.op2)

		res <- list(op1=list(p0=p0.op1, p1=p1.op1), op2=list(p0=p0.op2, p1=p1.op2))
		return(res)
	}

	impute_from_log_risk_ratio <- function () {
		res <- complete_effect_and_variance(d=log(est), lower=log(lower), upper=log(upper))
		d <- res[["d"]]; b <- res[["b"]]

		d <- exp(d)

		p0.op1 <- (control_sample_size+d*treatment_sample_size)/(d*(b*treatment_sample_size*control_sample_size+treatment_sample_size+control_sample_size))
		p1.op1 <- p0.op1*d

		res <- list(op1=list(p0=p0.op1, p1=p1.op1))
	}

	res <- switch(metric, "RD"=impute_from_risk_difference(),
			              "OR"=impute_from_log_odds_ratio(),
						  "RR"=impute_from_log_risk_ratio())

	a <- res$op1$p1 * treatment_sample_size; a <- round(a, digits=0);
	b <- treatment_sample_size
	c <- res$op1$p0 * control_sample_size; c <- round(c, digits=0);
	d <- control_sample_size
	op1 <- list(a=a, b=b, c=c, d=d)
	if (is.nan(a)|is.nan(b)|is.nan(c)|is.nan(d)) {
		return(list(FAIL=NA))
	}

	if (isnt.null(res$op2)) {
		a <- res$op2$p1 * treatment_sample_size; a <- round(a, digits=0);
		b <- treatment_sample_size
		c <- res$op2$p0 * control_sample_size; c <- round(c, digits=0);
		d <- control_sample_size
		op2 <- list(a=a, b=b, c=c, d=d)
		if (is.nan(a)|is.nan(b)|is.nan(c)|is.nan(d)) {
			return(list(FAIL=NA))
		}
	}
	else {
		op2 <- NULL;
	}

	if (is.null(op2)) {
		res <- list(op1=op1)
	}
	else {
		res <- list(op1=op1, op2=op2)
	}


	return(res)
}

check.1spell.res <- function(n, se) {
    succeeded <- TRUE
    comment <- ""

    if (!is.na(n)) {
        if (n<=1) {
            comment <- "n<=1"
            succeeded <- FALSE
        }
    }

	if (!is.na(se)) {
	    if (se<=0) {
	        comment <- paste("se<=0", comment, sep=", ")
	        succeeded <- FALSE
		}
	}

    return(list(succeeded=succeeded, comment=comment))

}

fillin.cont.1spell <- function(n=NA, mean=NA, sd=NA, se=NA, var=NA,
                         low=NA, high=NA, pval=NA, alpha=0.05) {
    succeeded <- FALSE
    comment <- ""
    res <- list(succeeded=succeeded)

    z <- abs(qnorm(alpha/2))

    input.vector <- c(n, mean, sd, se, var, low, high, pval)
    input.pattern <- !(is.na(input.vector))

	get.mean <- function(high=NA, low=NA) {
		if(is.na(mean))
			mean = (high+low)/2
		return(mean)
	}

	get.se <- function(sd=NA, n=NA, low=NA, high=NA, mean=NA, pval=NA) {
		if(is.na(se))
			se <- try(  sd/sqrt(n)  , silent=TRUE)

		if(is.na(se))
			se <- try(  abs(high-low)/(2*z)  ,silent=TRUE)

		if(is.na(se))
			se <- try(  abs(mean-low)/z  ,silent=TRUE)

		if(is.na(se))
			se <- try(  abs(high-mean)/z  ,silent=TRUE)

		if(is.na(se))
			se <- try(  abs(mean)/abs(qnorm(pval/2))  ,silent=TRUE)

		return(se)
	}

	get.var <- function(sd=NA) {
		if (is.na(var))
			var <- try(  sd^2  , silent=TRUE)
		return(var)
	}

	get.sd <- function(var=NA, n=NA, se=NA) {
		if (is.na(sd))
			sd <- try(  sqrt(var)  ,silent=TRUE)

		if (is.na(sd))
			sd <- try(  sqrt(n)*se  ,silent=TRUE)

		return(sd)
	}

	get.n <- function(sd=NA, se=NA, var=NA) {
		if (is.na(n))
			n <- (sd/se)^2
		if (is.na(n))
			n <- var/(se^2)
		return(n)
	}

	dirty <- TRUE
	while (dirty) {
		dirty <- FALSE

		if (is.na(mean)) {
	    	mean <- get.mean(high=high, low=low)
			if (!is.na(mean)) {
				dirty <- TRUE
			}

		}
		if (is.na(se)) {
			se <- get.se(sd=sd, n=n, low=low, high=high, mean=mean, pval=pval)
			if (!is.na(se)) {
				dirty <- TRUE
			}
		}
		if (is.na(var)) {
			var <- get.var(sd=sd)
			if (!is.na(var)) {
				dirty <- TRUE
			}
		}
		if(is.na(low)) {
	        low <- mean - z*se
			if (!is.na(low)) {
				dirty <- TRUE
			}
		}
		if(is.na(high)) {
	        high <- mean + z*se
			if (!is.na(high)) {
				dirty <- TRUE
			}
		}
		if(is.na(pval)) {
	        pval <- 2*pnorm(-abs(mean/se))
			if (!is.na(pval)) {
				dirty <- TRUE
			}
		}
		if(is.na(sd)) {
	        sd = get.sd(var=var, n=n, se=se)
			if (!is.na(sd)) {
				dirty = TRUE
			}
		}
		if(is.na(n)) {
			n <- get.n(sd=sd, se=se, var=var)
			if (!is.na(n)) {
				dirty <- TRUE
			}
		}

	}

	succeeded <- check.1spell.res(n=n, se=se)$succeeded
	comment   <- check.1spell.res(n=n, se=se)$comment

	if (is.na(mean)) {
		comment <- paste(comment, "no info on mean", sep="|")
	}
	if (is.na(se)) {
		comment <- paste(comment, "no info on dispersion", sep="|")
	}
	if(is.na(sd)) {
		comment <- paste(comment, "{n & sd} missing")
	}

    output.vector <- c(n, mean, sd, se, var, low, high, pval)
    output.names <- c("n", "mean", "sd", "se", "var", "low", "high", "pval")
    names(output.vector) <- output.names

    res<- list(succeeded=succeeded, input.pattern=input.pattern, output=output.vector, comment=comment)
    return(res)

}


fillin.missing.effect.quantity <- function(est=NA, low=NA, high=NA) {
	difference <- high-est
	if (is.na(difference))
		difference <- est - low

	if (is.na(est))
		est <- (high-low)/2.0

	if (is.na(low))
		low <- est - difference

	if (is.na(high))
		high <- est + difference

	return(list(est=est, low=low, high=high))
}

gimpute.cont.data <- function(group1, group2, effect_data, conf.level=95.0) {
	n1    <- group1[["n"]]
	n2    <- group2[["n"]]
	mean1 <- group1[["mean"]]
	mean2 <- group2[["mean"]]
	sd1   <- group1[["sd"]]
	sd2   <- group2[["sd"]]
	est   <- effect_data[["est"]]
	low   <- effect_data[["low"]]
	high  <- effect_data[["high"]]
	metric <- effect_data[["metric"]]
	met.param <- effect_data[["met.param"]]

	if (is.null(n1))    n1    <- NA
	if (is.null(n2))    n2    <- NA
	if (is.null(mean1)) mean1 <- NA
	if (is.null(mean2)) mean2 <- NA
	if (is.null(sd1))   sd1   <- NA
	if (is.null(sd2))   sd2   <- NA
	if (is.null(est))   est   <- NA
	if (is.null(low))   low   <- NA
	if (is.null(high))  high  <- NA
	if (is.null(metric)) metric <- NA
	if (is.null(met.param)) met.param <- NA
	if (is.null(conf.level)) conf.level <- NA

	metric <- as.character(metric)

	if (is.na(metric) | is.na(conf.level) | is.na(met.param)) {
		return(list("FAIL"=NA))
	}

	effect.and.ci <- fillin.missing.effect.quantity(est=est, low=low, high=high)
	est  <- effect.and.ci[["est"]]
	low  <- effect.and.ci[["low"]]
	high <- effect.and.ci[["high"]]

	mult <- get.mult.from.conf.level(conf.level)
	se <- (high-low)/(2*mult)
	var <- se^2

	positive_real_values <- function(res.vector) {
		res.vector <- res.vector[!is.na(res.vector)]
		res.vector <- res.vector[Re(res.vector) > 0]
		res.vector <- res.vector[abs(Im(res.vector)) < IMAGINARY.THRESHOLD]
		res.vector <- Re(res.vector)

		if (length(res.vector)==0)
			res.vector <- NA;
		return(res.vector)
	}

	impute.from.MD <- function() {
		D <- est; Y1 <- mean1; Y2 <- mean2;

		if (is.na(Y1) & isnt.na(Y2))
			Y1 <- D + Y2
		if (is.na(Y2) & isnt.na(Y1))
			Y2 <- Y1 - D
		if (met.param) {
			if (is.na(n1)) {
				n1.op1 <- (1/2)*(n2*sd1^2-sd1^2-var*n2^2+2*var*n2+sd2^2*n2-sd2^2+sqrt(var^2*n2^4-4*var^2*n2^3+4*var^2*n2^2+sd1^4+sd2^4+n2^2*sd1^4+2*n2*sd1^4+2*sd1^2*sd2^2+sd2^4*n2^2-2*sd2^4*n2-2*n2^3*sd1^2*var+2*n2^2*sd1^2*var-2*n2^2*sd1^2*sd2^2-4*sd1^2*var*n2+2*var*n2^3*sd2^2+2*var*n2^2*sd2^2-4*var*n2*sd2^2))/(-sd1^2+var*n2)
				n1.op2 <- -(1/2)*(-n2*sd1^2+sd1^2+var*n2^2-2*var*n2-sd2^2*n2+sd2^2+sqrt(var^2*n2^4-4*var^2*n2^3+4*var^2*n2^2+sd1^4+sd2^4+n2^2*sd1^4+2*n2*sd1^4+2*sd1^2*sd2^2+sd2^4*n2^2-2*sd2^4*n2-2*n2^3*sd1^2*var+2*n2^2*sd1^2*var-2*n2^2*sd1^2*sd2^2-4*sd1^2*var*n2+2*var*n2^3*sd2^2+2*var*n2^2*sd2^2-4*var*n2*sd2^2))/(-sd1^2+var*n2)
				n1.op1 <- round(n1.op1, digits = 0)
				n1.op2 <- round(n1.op2, digits = 0)
				n1 <- positive_real_values(c(n1.op1,n1.op2))
                n1 <- round(n1)
			}
			if (is.na(n2)) {
				n2.op1 <- (1/2)*(n1*sd2^2-var*n1^2+2*var*n1+sd1^2*n1-sd1^2-sd2^2+sqrt(sd1^4+sd2^4+2*sd1^2*sd2^2+n1^2*sd2^4+2*n1*sd2^4+var^2*n1^4-4*var^2*n1^3+4*var^2*n1^2+sd1^4*n1^2-2*sd1^4*n1-2*n1^3*sd2^2*var+2*n1^2*sd2^2*var-2*n1^2*sd2^2*sd1^2+2*var*n1^3*sd1^2+2*var*n1^2*sd1^2-4*var*n1*sd1^2-4*var*n1*sd2^2))/(var*n1-sd2^2)
				n2.op2 <- -(1/2)*(-n1*sd2^2+var*n1^2-2*var*n1-sd1^2*n1+sd1^2+sd2^2+sqrt(sd1^4+sd2^4+2*sd1^2*sd2^2+n1^2*sd2^4+2*n1*sd2^4+var^2*n1^4-4*var^2*n1^3+4*var^2*n1^2+sd1^4*n1^2-2*sd1^4*n1-2*n1^3*sd2^2*var+2*n1^2*sd2^2*var-2*n1^2*sd2^2*sd1^2+2*var*n1^3*sd1^2+2*var*n1^2*sd1^2-4*var*n1*sd1^2-4*var*n1*sd2^2))/(var*n1-sd2^2)
				n2.op1 <- round(n2.op1, digits=0)
				n2.op2 <- round(n2.op2, digits=0)
				n2 <- positive_real_values(c(n2.op1, n2.op2))
                n2 <- round(n2)
			}
			if (is.na(sd1)) {
				sd1.op1 <- sqrt((n1^2-n1+n1*n2-n2)*(var*n1^2*n2+var*n1*n2^2-2*var*n1*n2-n1*sd2^2*n2+n1*sd2^2-sd2^2*n2^2+sd2^2*n2))/(n1^2-n1+n1*n2-n2)
				sd1.op2 <- -sqrt((n1^2-n1+n1*n2-n2)*(var*n1^2*n2+var*n1*n2^2-2*var*n1*n2-n1*sd2^2*n2+n1*sd2^2-sd2^2*n2^2+sd2^2*n2))/(n1^2-n1+n1*n2-n2)
				sd1 <- positive_real_values(c(sd1.op1, sd1.op2))
			}
			if (is.na(sd2)) {
				sd2.op1 <- sqrt((n1*n2-n1+n2^2-n2)*(var*n1^2*n2+var*n1*n2^2-2*var*n1*n2-sd1^2*n1^2+sd1^2*n1-n2*sd1^2*n1+n2*sd1^2))/(n1*n2-n1+n2^2-n2)
				sd2.op2 <- -sqrt((n1*n2-n1+n2^2-n2)*(var*n1^2*n2+var*n1*n2^2-2*var*n1*n2-sd1^2*n1^2+sd1^2*n1-n2*sd1^2*n1+n2*sd1^2))/(n1*n2-n1+n2^2-n2)
				sd2 <- positive_real_values(c(sd2.op1, sd2.op2))
			}
		}
		else {
			if (is.na(n1)) {
				n1 <- n2*sd1^2/(var*n2-sd2^2)
                n1 <- round(n1)
			}
			if (is.na(n2)) {
				n2 <- n1*sd2^2/(var*n1-sd1^2)
                n2 <- round(n2)
			}
			if (is.na(sd1)) {
				sd1.op1 <- sqrt(n2*n1*(var*n2-sd2^2))/n2
				sd1.op2 <- -sqrt(n2*n1*(var*n2-sd2^2))/n2
				sd1 <- positive_real_values(c(sd1.op1, sd1.op2))
			}
			if (is.na(sd2)) {
				sd2.op1 <- sqrt(n1*n2*(var*n1-sd1^2))/n1
				sd2.op2 <- -sqrt(n1*n2*(var*n1-sd1^2))/n1
				sd2 <- positive_real_values(c(sd2.op1, sd2.op2))
			}
		}

		res <- list(n1=n1, n2=n2, mean1=Y1, mean2=Y2, sd1=sd1, sd2=sd2)
		return(res)
	}

	impute.from.SMD <- function() {
	sdw <- sqrt(((n1-1)*sd1^2+(n2-1)*sd2^2)/(n1+n2-2))
		D <- est; Y1 <- mean1; Y2 <- mean2;

		if (is.na(Y1)) Y1 <- D*sdw+Y2
		if (is.na(Y2)) Y2 <- -D*sdw+Y1
		if (is.na(n1)) {
			n1 <- -(-sd1^2*D^2+sd2^2*n2*D^2-sd2^2*D^2-n2*Y1^2+2*n2*Y1*Y2-n2*Y2^2+2*Y1^2-4*Y1*Y2+2*Y2^2)/(sd1^2*D^2-Y1^2+2*Y1*Y2-Y2^2)
            n1 <- round(n1)
		}
		if (is.na(n2)) {
			n2 <- -(sd1^2*n1*D^2-sd1^2*D^2-sd2^2*D^2-n1*Y1^2+2*n1*Y1*Y2-n1*Y2^2+2*Y1^2-4*Y1*Y2+2*Y2^2)/(sd2^2*D^2-Y1^2+2*Y1*Y2-Y2^2)
            n2 <- round(n2)
		}
		if (is.na(sd1)) {
			sd1.op1 <- (sqrt(-(n1-1)*(-n1*Y1^2+2*n1*Y1*Y2+sd2^2*n2*D^2-sd2^2*D^2+2*n2*Y1*Y2-n2*Y2^2-n1*Y2^2-n2*Y1^2+2*Y2^2+2*Y1^2-4*Y1*Y2)))/((n1-1)*D)
			sd1.op2 <- -(sqrt(-(n1-1)*(-n1*Y1^2+2*n1*Y1*Y2+sd2^2*n2*D^2-sd2^2*D^2+2*n2*Y1*Y2-n2*Y2^2-n1*Y2^2-n2*Y1^2+2*Y2^2+2*Y1^2-4*Y1*Y2)))/((n1-1)*D)
			sd1 <- positive_real_values(c(sd1.op1, sd1.op2))
		}
		if (is.na(sd2)) {
			sd2.op1 <- (sqrt(-(n2-1)*(sd1^2*n1*D^2-sd1^2*D^2-n1*Y2^2-n2*Y1^2-n1*Y1^2+2*n1*Y1*Y2+2*Y1^2-4*Y1*Y2+2*n2*Y1*Y2-n2*Y2^2+2*Y2^2)))/((n2-1)*D)
			sd2.op2 <- -(sqrt(-(n2-1)*(sd1^2*n1*D^2-sd1^2*D^2-n1*Y2^2-n2*Y1^2-n1*Y1^2+2*n1*Y1*Y2+2*Y1^2-4*Y1*Y2+2*n2*Y1*Y2-n2*Y2^2+2*Y2^2)))/((n2-1)*D)
			sd2 <- positive_real_values(c(sd2.op1, sd2.op2))
		}
		if (met.param) {
			if (is.na(n1)) {
				tryCatch({n1 <- polyroot(c(96*n2^3-16*n2^4-144*n2^2, (81*var*n2^2-72*var*n2^3+48*D^2*n2^2-72*D^2*n2+16*var*n2^4-288*n2-64*n2^3+288*n2^2-8*n2^3*D^2), (48*D^2*n2+48*var*n2^3+288*n2-16*D^2*n2^2-144-144*var*n2^2+81*var*n2-96*n2^2), (96+48*var*n2^2-64*n2-8*D^2*n2-72*var*n2), (16*var*n2-16)));
					}, error = function(e) {
						n1 <- NA;
					});
				n1 <- positive_real_values(n1)
        		n1 <- round(n1)
			}
			if (is.na(n2)) {
				tryCatch({  n2 <- polyroot(c(96*n1^3-16*n1^4-144*n1^2, (81*var*n1^2-72*var*n1^3+48*D^2*n1^2-72*D^2*n1+16*var*n1^4-288*n1-64*n1^3+288*n1^2-8*n1^3*D^2), (48*D^2*n1+48*var*n1^3+288*n1-16*D^2*n1^2-144-144*var*n1^2+81*var*n1-96*n1^2), (96+48*var*n1^2-64*n1-8*D^2*n1-72*var*n1), (16*var*n1-16)));
					}, error = function(e) {
						n2 <- NA;
					});
				n2 <- positive_real_values(n2)
       			n2 <- round(n2)
			}
		}
		else {
			if (is.na(n1)) {
				n1.op1 <- (1/4)*(-2*var*n2+4+D^2+sqrt(4*var^2*n2^2-4*D^2*n2*var+8*D^2+D^4))*n2/(var*n2-1)
				n1.op2 <- -(1/4)*(2*var*n2-4-D^2+sqrt(4*var^2*n2^2-4*D^2*n2*var+8*D^2+D^4))*n2/(var*n2-1)
				n1.op1 <- round(n1.op1, digits = 0)
				n1.op2 <- round(n1.op2, digits = 0)
				n1 <- positive_real_values(c(n1.op1,n1.op2))
                n1 <- round(n1)
			}
			if (is.na(n2)) {
				n2.op1 <- (1/4)*(-2*var*n1+D^2+4+sqrt(4*var^2*n1^2-4*var*n1*D^2+D^4+8*D^2))*n1/(-1+var*n1)
				n2.op2 <- -(1/4)*(2*var*n1-D^2-4+sqrt(4*var^2*n1^2-4*var*n1*D^2+D^4+8*D^2))*n1/(-1+var*n1)
				n2.op1 <- round(n2.op1, digits=0)
				n2.op2 <- round(n2.op2, digits=0)
				n2 <- positive_real_values(c(n2.op1, n2.op2))
                n2 <- round(n2)
			}
		}

		res <- list(n1=n1, n2=n2, mean1=Y1, mean2=Y2, sd1=sd1, sd2=sd2)
		return(res)
	}

	res <- switch(metric, "MD"=impute.from.MD(), "SMD"=impute.from.SMD())
	return(res)
}

fillin.cont.AminusB <- function(
    n.A=NA, mean.A=NA, sd.A=NA, se.A=NA, var.A=NA, low.A=NA, high.A=NA, pval.A=NA,
    n.B=NA, mean.B=NA, sd.B=NA, se.B=NA, var.B=NA, low.B=NA, high.B=NA, pval.B=NA,
    correlation = 0, alpha=0.05, metric=NA) {

	metric <- as.character(metric)

    succeeded <- TRUE
    comment <- ""
    res <- list(succeeded= succeeded)

    n.diff <- NA
    mean.diff <- NA
    sd.diff <- NA
    se.diff <- NA
    var.diff <- NA
    low.diff <- NA
    high.diff <- NA
    pval.diff <-NA

    z <- abs(qnorm(alpha/2))

    input.vector.A <- c(n.A, mean.A, sd.A, se.A, var.A, low.A, high.A, pval.A)
    input.vector.B <- c(n.B, mean.B, sd.B, se.B, var.B, low.B, high.B, pval.B)

    input.pattern <- list(A=!(is.na(input.vector.A)), B=!(is.na(input.vector.B)))

    fillin.A <- fillin.cont.1spell(n.A, mean.A, sd.A, se.A, var.A, low.A, high.A, pval.A, alpha=alpha)
    comment <-paste(comment, paste("A", fillin.A$comment, sep=":"), sep="|")

    fillin.B <- fillin.cont.1spell(n.B, mean.B, sd.B, se.B, var.B, low.B, high.B, pval.B, alpha=alpha)
    comment <-paste(comment, paste("B", fillin.B$comment, sep=":"), sep="|")

	fillins.succeeded <- identical( c(fillin.A$succeeded,fillin.B$succeeded), c(TRUE, TRUE))


	if (isnt.na(fillin.A$output["n"]) & is.na(fillin.B$output["n"])) {
		fillin.B$output["n"] <- fillin.A$output["n"];
	}
	else if (isnt.na(fillin.B$output["n"]) & is.na(fillin.A$output["n"])) {
		fillin.A$output["n"] <- fillin.B$output["n"];
	}

	nA.eq.nB <- identical(fillin.A$output["n"], fillin.B$output["n"])

    if (fillins.succeeded & nA.eq.nB) {
		n.diff <- fillin.A$output["n"]
		Y1 <- fillin.A$output["mean"]
		Y2 <- fillin.B$output["mean"]
		S1 <- fillin.A$output["sd"]
		S2 <- fillin.B$output["sd"]
		r <- correlation

		S.difference = sqrt(  (S1^2)+(S2^2)-(2*r*S1*S2)  )


		if (metric=="MD" || metric=="SMD") {
			mean.diff <- Y2-Y1
			sd.diff <- S.difference
			fillin.diff <- fillin.cont.1spell(n=n.diff, mean=mean.diff, sd=sd.diff, alpha=alpha)
			if (fillin.diff$succeeded) {
				se.diff   <- fillin.diff$output["se"]
				var.diff  <- fillin.diff$output["var"]
				low.diff  <- fillin.diff$output["low"]
				high.diff <- fillin.diff$output["high"]
				pval.diff <- fillin.diff$output["pval"]
			}
		}
    } else {
		if (!nA.eq.nB)
			comment <- paste(comment, "  n.A != n.B")
        succeeded <- FALSE
    }



    output.vector <- c(n.diff, mean.diff, sd.diff, se.diff, var.diff, low.diff, high.diff, pval.diff)
    output.names  <- c(   "n",    "mean",    "sd",    "se",    "var",    "low",    "high",    "pval")

    names(output.vector) <- output.names
    res<- list(succeeded=succeeded, input.pattern=input.pattern, output=output.vector,
                      pre=fillin.A$output, post=fillin.B$output,
                      comment=comment, correlation=correlation)

    return(res)

}

gimpute.diagnostic.data <- function(diag.data) {
	TP <- NULL; FN <- NULL; TN <- NULL; FP <-NULL;

	N    <-       diag.data[["total"]]
	prev <-       diag.data[["prev"]]
	sens <-       diag.data[["sens"]]
	sens.lb <-    diag.data[["sens.lb"]]
	sens.ub <-    diag.data[["sens.ub"]]
	spec    <-    diag.data[["spec"]]
	spec.lb <-    diag.data[["spec.lb"]]
	spec.ub <-    diag.data[["spec.ub"]]
	conf.level <- diag.data[["conf.level"]]

	case2a.condition <- isnt.null(sens) & isnt.null(prev) & isnt.null(N)
	case2b.condition <- isnt.null(spec) & isnt.null(prev) & isnt.null(N)

	sensitivity_estimate_and_interval <- isnt.null(sens) &
		(isnt.null(sens.lb) | isnt.null(sens.ub))
	sensitivity_interval <- isnt.null(sens.lb) & isnt.null(sens.ub)
	case5a.condition <- (sensitivity_estimate_and_interval | sensitivity_interval) &
		isnt.null(conf.level)
	case5b.condition <- case5a.condition & isnt.null(spec) & isnt.null(N)

	specificity_estimate_and_interval <- isnt.null(spec) &
		(isnt.null(spec.lb) | isnt.null(spec.ub))
	specificity_interval <- isnt.null(spec.lb) & isnt.null(spec.ub)
	case6a.condition <- (specificity_estimate_and_interval | specificity_interval) &
		isnt.null(conf.level)
	case6b.condition <- case6a.condition & isnt.null(sens) & isnt.null(N)

	case8a.inputs <- sensitivity_estimate_and_interval | sensitivity_interval
	case8b.inputs <- specificity_estimate_and_interval | specificity_interval
	case8a.condition <- case8a.inputs & isnt.null(conf.level)
	case8b.condition <- case8b.inputs & isnt.null(conf.level)

	case2 <- function(sens, spec, prev, N) {
		TP <- sens*prev*N
		FN <- (1-sens)*prev*N
		FP <- N*(spec-1)*(prev-1)
		TN <- N*spec*(1-prev)

		list(TP=TP,FP=FP,TN=TN,FN=FN)
	}
	case5 <- function(sens, sens.lb, sens.ub, spec, N, conf.level) {
		ci.data <- list(estimate=sens, lb=sens.lb, ub=sens.ub, conf.level=conf.level)
		est.var <- calc.est.var(ci.data)
		varLogitSENS <- est.var$var
		sens <- est.var$estimate

		TP = -1/(varLogitSENS*(sens-1))
		FP = -(-1+spec)*(varLogitSENS*sens^2*N-varLogitSENS*sens*N+1)/(varLogitSENS*sens*(sens-1))
		TN = spec*(varLogitSENS*sens^2*N-varLogitSENS*sens*N+1)/(varLogitSENS*sens*(sens-1))
		FN = 1/(varLogitSENS*sens)

		list(TP=TP,FP=FP,TN=TN,FN=FN)
	}


	case6 <- function(spec, spec.lb, spec.ub, sens, N, conf.level) {
		ci.data <- list(estimate=spec, lb=spec.lb, ub=spec.ub, conf.level=conf.level)
		est.var <- calc.est.var(ci.data)
		varLogitSPEC <- est.var$var
		spec <- est.var$estimate

		TP = sens*(-1*varLogitSPEC*spec*N+varLogitSPEC*spec^2*N+1)/(varLogitSPEC*spec*(-1+spec))
		FP = 1/(varLogitSPEC*spec)
		TN = -1/(varLogitSPEC*(-1+spec))
		FN = -(sens-1)*(-1*varLogitSPEC*spec*N+varLogitSPEC*spec^2*N+1)/(varLogitSPEC*spec*(-1+spec))

		list(TP=TP,FP=FP,TN=TN,FN=FN)
	}

	case8 <- function(sens, sens.lb, sens.ub, spec, spec.lb, spec.ub, conf.level) {
		ci.data <- list(estimate=sens, lb=sens.lb, ub=sens.ub, conf.level=conf.level)
		est.var <- calc.est.var(ci.data)
		varLogitSENS <- est.var$var
		sens <- est.var$estimate

		ci.data <- list(estimate=spec, lb=spec.lb, ub=spec.ub, conf.level=conf.level)
		est.var <- calc.est.var(ci.data)
		varLogitSPEC <- est.var$var
		spec <- est.var$estimate

		TP = -1/(varLogitSENS*(sens-1))
		FP = 1/(varLogitSPEC*spec)
		TN = -1/(varLogitSPEC*(-1+spec))
		FN = 1/(varLogitSENS*sens)

		list(TP=TP,FP=FP,TN=TN,FN=FN)
	}



	case2res <- case2(sens, spec, prev, N)
	case5res <- case5(sens, sens.lb, sens.ub, spec, N, conf.level)
    case6res <- case6(spec, spec.lb, spec.ub, sens, N, conf.level)
	case8res <- case8(sens, sens.lb, sens.ub, spec, spec.lb, spec.ub, conf.level)

	if (case2a.condition) {
		TP <- if(is.null(TP)) case2res$TP
		FN <- if(is.null(FN)) case2res$FN
	} else if (case5a.condition) {
		TP <- if(is.null(TP)) case5res$TP
		FN <- if(is.null(FN)) case5res$FN
	} else if (case6b.condition) {
		TP <- if(is.null(TP)) case6res$TP
		FN <- if(is.null(FN)) case6res$FN
	} else if (case8a.condition) {
		TP <- if(is.null(TP)) case8res$TP
		FN <- if(is.null(FN)) case8res$FN
	}

	if (case2b.condition) {
		TN <- if(is.null(TN)) case2res$TN
	    FP <- if(is.null(FP)) case2res$FP
	} else if (case5b.condition) {
		TN <- if(is.null(TN)) case5res$TN
		FP <- if(is.null(FP)) case5res$FP
	} else if (case6a.condition) {
		TN <- if(is.null(TN)) case6res$TN
		FP <- if(is.null(FP)) case6res$FP
	} else if (case8b.condition) {
		TN <- if(is.null(TN)) case8res$TN
		FP <- if(is.null(FP)) case8res$FP
	}

	if(is.null(TP)) {
    	TP <- NA
	}
	if(is.null(FN)) {
    	FN <- NA
	}
	if(is.null(TN)) {
    	TN <- NA
	}
	if(is.null(FP)) {
    	FP <- NA
	}

	TP.rnd.err <- abs(TP-round(TP,digits=0))
	FN.rnd.err <- abs(FN-round(FN,digits=0))
	TN.rnd.err <- abs(TN-round(TN,digits=0))
	FP.rnd.err <- abs(FP-round(FP,digits=0))

	TP <- round(TP,digits=0)
	FN <- round(FN,digits=0)
	TN <- round(TN,digits=0)
	FP <- round(FP,digits=0)

	list(TP=TP,
		 FN=FN,
		 TN=TN,
		 FP=FP,
		 TP.rnd.err=TP.rnd.err,
		 FN.rnd.err=FN.rnd.err,
		 TN.rnd.err=TN.rnd.err,
		 FP.rnd.err=FP.rnd.err)
}

calc.est.var <- function(ci.data) {
  est.var <- list()
  mult <- get.mult.from.conf.level(ci.data$conf.level)
  if (isnt.null(ci.data$estimate)) {
    if (isnt.null(ci.data$lb)) {
    est.var$estimate <- ci.data$estimate
    var <- ((logit(ci.data$estimate) - logit(ci.data$lb)) / mult)^2
    est.var$var <- var
    } else if (isnt.null(ci.data$ub)) {
    est.var$estimate <- ci.data$estimate
    var <- ((logit(ci.data$ub) - logit(ci.data$estimate)) / mult)^2
    est.var$var <- var
    }
  } else if (isnt.null(ci.data$lb) & isnt.null(ci.data$ub)) {
    radius <- (logit(ci.data$ub) - logit(ci.data$lb)) / 2
    estimate <- invlogit(logit(ci.data$lb) + radius)
    est.var$estimate <- estimate
    var <- (radius / mult)^2
    est.var$var <- var
  }
  est.var
}

rescale.effect.and.ci.conf.level <- function(data_arguments) {
	est <- data_arguments[["est"]]
	low <- data_arguments[["low"]]
	high <- data_arguments[["high"]]
	orig.conf.level <- data_arguments[["orig.conf.level"]]
	target.conf.level <- data_arguments[["target.conf.level"]]

	if (is.null(est))  est  <- NA
	if (is.null(low))  low  <- NA
	if (is.null(high)) high <- NA

	missing_count <- sum(is.na(c(est, low, high)))

	if (missing_count > 1 || is.na(orig.conf.level) || is.na(target.conf.level)) {
		return(list("FAIL"=NA))
	}

	if (is.na(est)) {
		est <- (high-low)/2.0
	}

	if (is.na(low)) {
		low <- est - (high-est)
	}

	if (is.na(high)) {
		high <- est + (est - low)
	}

	old.mult <- get.mult.from.conf.level(orig.conf.level)
	new.mult <- get.mult.from.conf.level(target.conf.level)

	se <- (high-low)/(2*old.mult)

	new.est  <- est
	new.low  <- new.est - new.mult*se
	new.high <- new.est + new.mult*se

	return(list(est=new.est, low=new.low, high=new.high))
}
