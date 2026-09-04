permuted.ma <- function(
	data, method, intercept=TRUE, level=95, digits=RCMETAR_DEFAULT_DISPLAY_DIGITS, knha=FALSE, weighted=TRUE,
	exact=FALSE, iter=1000, retpermdist=FALSE) {

	ma.res <- rma.uni(yi, vi,
		intercept=intercept,
		data=data,
		slab=data$slab,
		method=method,
		knha=knha,
		level=level,
		digits=digits,
		weighted=weighted)

	perm.res <- permutest(ma.res, exact=exact, iter=iter,
              retpermdist=FALSE, digits=digits)
	summary <- paste(capture.output(perm.res), collapse="\n")

	results <- list(
		"Summary"=summary,
		"res"=perm.res,
		"res.info"=permutest.value.info(retpermdist, meta.reg.mode=FALSE)
		)
}

permuted.meta.reg <- function (
	data, method, mods, intercept=TRUE, level=95, digits=RCMETAR_DEFAULT_DISPLAY_DIGITS, knha=FALSE, btt=NULL,
	exact=FALSE, iter=1000, retpermdist=FALSE,
	include.meta.reg.summary=TRUE
	) {

	mods.formula <- make.mods.formula(mods)

	reg.res <- regression.wrapper(data, mods.formula, method, level, digits, btt)

	perm.res <- permutest(reg.res, exact=exact, iter=iter,
              retpermdist=retpermdist, digits=digits)
	summary <- paste(capture.output(perm.res), collapse="\n")

	results <- list(
		"Permuted Meta-Regression Summary"=summary,
		"res"=perm.res,
		"res.info"=permutest.value.info(retpermdist)
		)

	if (include.meta.reg.summary) {
		meta.reg.result <- g.meta.regression(
			data=data,
			mods=mods,
			method=method,
			level=level,
			digits=digits,
			measure=NULL,
			btt=btt,
			make.coeff.forest.plot=FALSE,
			exclude.intercept=FALSE,
			disable.plots=TRUE
		)

		results <- c(list('Standard Meta Regression Summary'=meta.reg.result$Summary), results)
	}

	results
}

permutest.value.info <- function(retpermdist, meta.reg.mode=TRUE) {
	info = list(
			pval = list(type="vector", description='p-value(s) based on the permutation test.'),
			QMp = list(type="vector", description='p-value for the omnibus test of coefficients based on the permutation test.')
	)

	if (retpermdist && meta.reg.mode) {
		additional.info = list(
				zval.perm = list(type="data.frame", description='values of the test statistics of the coefficients under the various permutations'),
				QM.perm = list(type="vector", description='values of the test statistic for the omnibus test of coefficients under the various permutations')
		)
		info = c(info, additional.info)
	}
	return(info)
}
