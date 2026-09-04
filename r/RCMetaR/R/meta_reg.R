# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

regression.wrapper <- function(data, mods.formula, method, level, digits, btt=NULL) {
	rma.args <- list(yi=data$yi, vi=data$vi, mods=mods.formula, data=data,
	                 method=method, level=level, digits=digits)
	if (!is.null(btt)) rma.args$btt <- btt
	do.call(metafor::rma.uni, rma.args)
}

make.mods.formula <- function(mods, response=NULL) {
    terms <- c(mods[["numeric"]], mods[["categorical"]], names(mods[["interactions"]]))
    stats::reformulate(terms, response=response)
}

make.design.matrix <- function(strat.cov, mods, cond.means.data, data) {

	nlevels <- length(levels(data[[strat.cov]]))
	rownames <- levels(data[[strat.cov]])
	colnames <- c("Intercept")
	dsn.matrix <- matrix(rep(1,nlevels))

	for (mod in mods[["numeric"]]) {
		value <- cond.means.data[[mod]]
		dsn.matrix <- cbind(dsn.matrix,rep(value,nlevels))
		colnames<-c(colnames, mod)
	}

	for (mod in mods[["categorical"]]) {
	l.mod <- levels(data[[mod]])
		mod.matrix <- c()

		if (mod==strat.cov) {
			for (x in l.mod) {
				x.coded <- coded.cat.mod.level(x, l.mod)
				mod.matrix <- rbind(mod.matrix,x.coded)
			}
		} else {
			value <- cond.means.data[[mod]]
			lvl.coded <- coded.cat.mod.level(value, l.mod)
			for (x in 1:nlevels) {
				mod.matrix <- rbind(mod.matrix, lvl.coded)
			}
		}

		dsn.matrix <- cbind(dsn.matrix, mod.matrix)
		colnames<-c(colnames, paste(mod, l.mod[2:length(l.mod)],sep=""))
	}


	interaction.mod.matrix <- c()
	for (interaction in names(mods[['interactions']])) {
		interaction.vars <- mods[['interactions']][[interaction]]

		cat.cat <- (interaction.vars[1] %in% mods[['categorical']]) && (interaction.vars[2] %in% mods[['categorical']])
		cat.cont <- (interaction.vars[1] %in% mods[['categorical']]) && (interaction.vars[2] %in% mods[['numeric']])
		cont.cat <- (interaction.vars[1] %in% mods[['numeric']]) && (interaction.vars[2] %in% mods[['categorical']])
		cat.cont <- cat.cont || cont.cat

		if (cat.cat) {

			cat1.levels <- levels(data[[interaction.vars[1]]])
			cat2.levels <- levels(data[[interaction.vars[2]]])

			if (strat.cov %in% interaction.vars) {
				strat.cov.is.first <- strat.cov ==  interaction.vars[1]
				if (strat.cov.is.first) {
					value2 <- cond.means.data[[interaction.vars[2]]]
					mod.matrix <- c()
					for (value1 in cat1.levels) {
						row.vector <- get.row.vector.cat.cat(
								cat1.levels, cat2.levels,
								value1, value2)
						mod.matrix <- rbind(mod.matrix,row.vector)
					}
				}
				else {
					value1 = cond.means.data[[interaction.vars[1]]]
					mod.matrix <- c()
					for (value2 in cat2.levels) {
						row.vector <- get.row.vector.cat.cat(
								cat1.levels, cat2.levels,
								value1, value2)
						mod.matrix <- rbind(mod.matrix,row.vector)
					}
				}
			} else {
				value1 = cond.means.data[[interaction.vars[1]]]
				value2 = cond.means.data[[interaction.vars[2]]]

				row.vector <- get.row.vector.cat.cat(
						cat1.levels, cat2.levels,
						value1, value2)

				mod.matrix <- c()
				for (i in 1:nlevels) {
					mod.matrix <- rbind(mod.matrix,row.vector)
				}
			}

			intvar1 <- interaction.vars[1]
			intvar2 <- interaction.vars[2]
			col.names.for.interaction <- c()
			for (y in cat2.levels[2:length(cat2.levels)]) {
				for (x in cat1.levels[2:length(cat1.levels)]) {
					col.names.for.interaction <- c(col.names.for.interaction, paste(intvar1, x, ":",intvar2,y,sep=""))
				}
			}
			colnames<-c(colnames, col.names.for.interaction)
		} else if (cat.cont) {
			if (strat.cov %in% interaction.vars) {
				if (strat.cov==interaction.vars[1]) {
					strat.levels <- levels(data[[interaction.vars[1]]])
					cont.val <- cond.means.data[[interaction.vars[2]]]
				} else {
					strat.levels <- levels(data[[interaction.vars[2]]])
					cont.val <- cond.means.data[[interaction.vars[1]]]
				}

				mod.matrix <- c()
				for (x in strat.levels) {
					row.vector <- get.row.vector.cat.cont(strat.levels, x, cont.val)
					mod.matrix <- rbind(mod.matrix,row.vector)
				}

		    } else {
                value1 <- cond.means.data[[interaction.vars[1]]]
                value2 <- cond.means.data[[interaction.vars[2]]]
				if (class(value1) == "numeric") {
					cont.val <- value1
					cat.val <- value2
					cat.levels <- levels(data[[interaction.vars[2]]])
				} else {
					cont.val <- value2
					cat.val <- value1
					cat.levels <- levels(data[[interaction.vars[1]]])
				}

				row.vector <- get.row.vector.cat.cont(cat.levels, cat.val, cont.val)
				mod.matrix <- c()
				for (i in 1:nlevels) {
					mod.matrix <- rbind(mod.matrix,row.vector)
				}
			}

			intVar1 <- interaction.vars[1]
			intVar2 <- interaction.vars[2]
			if (intVar1 %in% mods[["numeric"]]) {
				cont.var <- intVar1
				cat.var <- intVar2
			} else {
				cont.var <- intVar2
				cat.var <- intVar1
			}
			cat.levels <- levels(data[[cat.var]])
            colnames <- c(colnames, paste(cont.var,":",cat.levels[2:length(cat.levels)],sep=""))
		} else {
	        value1 <- cond.means.data[[interaction.vars[1]]]
	        value2 <- cond.means.data[[interaction.vars[2]]]
			mod.matrix <- rep(value1*value2, nlevels)

			colnames <- c(colnames, paste(interaction.vars[1],":",interaction.vars[2], sep=""))
		}
		interaction.mod.matrix <- cbind(interaction.mod.matrix,mod.matrix)

	}
	dsn.matrix <- cbind(dsn.matrix, interaction.mod.matrix)
	dimnames(dsn.matrix) <- list(rownames, colnames)
	return(dsn.matrix)
}

get.row.vector.cat.cat <- function(cat1.levels, cat2.levels, value1, value2) {
	row.vector <- c()
	for (y in cat2.levels[2:length(cat2.levels)]) {
		for (x in cat1.levels[2:length(cat1.levels)]) {
			row.vector <- c(row.vector, ifelse(y==value2 && x==value1, 1,0))
		}
	}

	return(row.vector)
}

get.row.vector.cat.cont <- function(cat.levels, cat.val, cont.val) {

	row <- c()
	for (x in cat.levels[2:length(cat.levels)]) {
		row <- c(row, ifelse(x==cat.val, 1, 0))
	}
	row <- cont.val * row
	return(row)
}


coded.cat.mod.level <- function(lvl, l.mod) {

	index <- match(lvl, l.mod)
	n.levels <- length(l.mod)

	code.matrix <- rbind(rep(0,n.levels-1),diag(n.levels-1))
	code.matrix[index,]
}


reg.output.helper <- function(theData, rma.results, model.formula, digits) {
	coeffs <- tryCatch({
		coef(summary(rma.results))
	}, error=function(e) {
		NULL
	})
	omnibus <- tryCatch({
		anova(rma.results)
	}, error=function(e) {
		NULL
	})
	output <- list()
	if (!is.null(coeffs)) {
		output[["Coefficient table"]] <- paste(capture.output(round(coeffs, digits)), collapse="\n")
	}
	if (!is.null(omnibus)) {
		output[["Omnibus test"]] <- paste(capture.output(omnibus), collapse="\n")
	}
	output[["Model data"]] <- sprintf(
		"Studies: %d\nFormula: %s",
		nrow(theData),
		paste(deparse(model.formula), collapse=" ")
	)
	if (length(output) == 0) {
		output[["Model output"]] <- paste(capture.output(rma.results), collapse="\n")
	}
	output
}


g.meta.regression <- function(
  data,
  mods,
  method,
  level,
  digits,
  measure,
  btt=NULL,
  make.coeff.forest.plot=FALSE,
  exclude.intercept=FALSE,
  disable.plots = FALSE)
{

	mods.formula <- make.mods.formula(mods)

	res <- regression.wrapper(data, mods.formula, method, level, digits,btt)

	residuals <- rstandard(res, digits=digits)
	residuals$slab <- data$slab
	res.and.residuals <- res
	res.and.residuals$residuals <- residuals
	res.and.residuals.info <- c(rma.uni.value.info(),
			                    list(residuals=list(type="blob", description="Standardized residuals for fitted models")))

	Summary <- paste(capture.output(res), collapse="\n")
	regression.model.formula.str <- sprintf("Regression model formula: %s", paste(deparse(stats::reformulate(attr(terms(mods.formula), "term.labels"), response="yi")), collapse=" "))
	Summary <- paste(Summary, regression.model.formula.str, sep="\n\n")
	est.coeffs <- round(res$b[,1], digits=digits)
	tmp <- est.coeffs[2:length(est.coeffs)]
	tmp <- paste(tmp, names(tmp), sep="*")
	tmp <- paste(tmp, collapse=" + ")
	reg.equation <- paste(est.coeffs[1],tmp, sep=" + ")
	reg.equation.str <- sprintf("Regression model equation: %s", reg.equation)
	Summary <- paste(Summary, reg.equation.str, sep="\n")

	model.formula <- stats::reformulate(attr(terms(mods.formula), "term.labels"), response="yi")
	more.output <- reg.output.helper(theData=data, rma.results=res, model.formula=model.formula, digits=digits)
	pre.summary <- ""
	for (name in names(more.output)) {
		dashes <- paste(rep("-", nchar(name)+2), collapse="")
		item.str <- sprintf("%s:\n%s\n%s", name, dashes, more.output[[name]])
		pre.summary <- paste(pre.summary, item.str, sep="\n\n")
	}
	Summary <- paste(pre.summary, Summary, sep="\n\n")

	results <- list(#"images"=images,
			"Summary"=Summary,
			"res"=res.and.residuals, #res,
			"res.info"=res.and.residuals.info)


	images <- c()
	plot.names <- c()
	plot.params.paths <- c()
	if (is.single.numeric.covariate(mods) && !disable.plots) {
		betas <- res$b
		fitted.line <- list(intercept=betas[1], slope=betas[2])
		plot.path <- rcmetar.scratch.path("reg.png")
	    cov.name <- mods[['numeric']][[1]]
		cov.vals <- data[[cov.name]]
		plot.data <- g.create.plot.data.reg(data, cov.name, cov.vals, measure, level, fitted.line, res=res, digits=digits)


		plot.data$xlabel <- cov.name

		scale.str <- g.get.scale(measure)
		if ((scale.str=="standard") || (scale.str=="arcsine")) {
			scale.str <- ""
		}
		plot.data$ylabel <- paste(scale.str, " ", pretty.metric.name(as.character(measure)), sep="")
		meta.regression.plot(plot.data, plot.path)

		plot.params <- list(
			"rm.method"=method,
			"conf.level"=level,
			"digits"=digits,
			"measure"=measure
		)
		plot.data.path <- save.data(data, res, plot.params, plot.data)

		images <- c("Regression Plot"=plot.path)
		plot.names <- c("reg.plot"="reg.plot")
		plot.params.paths <- c("Regression Plot"=plot.data.path)

		results[['images']] <- images
		results[['plot_names']] <- plot.names
		results[['plot_params_paths']] <- plot.params.paths
	}

	coeff.forest.plot.path <- paste("r_tmp/", "bforestplot_", as.character(as.numeric(Sys.time())), sep = "")

	if (make.coeff.forest.plot && !disable.plots) {
		forest.plot.of.regression.coefficients(as.vector(res$b), res$ci.lb, res$ci.ub, labels=rownames(res$b), exclude.intercept=exclude.intercept, filepath=coeff.forest.plot.path)
		images <- c(images, "Forest Plot of Coefficients"=paste(coeff.forest.plot.path,".png",sep=""))
		plot.names <- c(plot.names, "coeff.forest.plot"="coeff.forest.plot")
		plot.params.paths <- c("Forest Plot of Coefficients"=coeff.forest.plot.path)
	}

	if (length(images)>0)
		results[['images']] <- images
	if (length(plot.names)>0)
		results[['plot_names']] <- plot.names
	if (length(plot.params.paths)>0)
		results[['plot_params_paths']] <- plot.params.paths

	results
}

is.single.numeric.covariate <- function(mods) {
	count.numeric <- length(mods[['numeric']])
	count.categorical <- length(mods[['categorical']])
	count.interactions <- length(mods[['interactions']])

	if (count.numeric==1 && count.categorical + count.interactions == 0) {
		return(TRUE)
	} else {
		return(FALSE)
	}
}

g.create.plot.data.reg <- function(reg.data, cov.name, cov.vals, measure, level, fitted.line, res=NULL, digits=RCMETAR_DEFAULT_DISPLAY_DIGITS) {
	if (!inherits(res, "rma")) {
		stop("Meta-regression bubble plots require a metafor rma result.", call.=FALSE)
	}
	params <- list(
		measure=measure,
		conf.level=level,
		digits=digits,
		fp_style="default"
	)
	rcmetar.create.metafor.bubble.bundle(
		reg.data=reg.data,
		params=params,
		res=res,
		cov.name=cov.name,
		cov.values=cov.vals,
		fitted.line=fitted.line
	)
}

g.get.scale <- function (measure)
{
	if (metric.is.log.scale(measure)) {
		scale <- "log"
	}
	else if (metric.is.logit.scale(measure)) {
		scale <- "logit"
	}
	else if (metric.is.arcsine.scale(measure)) {
		scale <- "arcsine"
	}
	else {
		scale <- "standard"
	}
	scale
}

g.meta.regression.cond.means <- function(data, mods, method, level, digits, strat.cov, cond.means.data, btt=NULL) {

	mods.formula <- make.mods.formula(mods)

	res <- regression.wrapper(data, mods.formula, method, level, digits,btt)

	A <- make.design.matrix(strat.cov, mods, cond.means.data, data)
	new_betas <- A %*% res$b
	new_cov   <- A %*% res$vb %*% t(A)
	new_vars <- diag(new_cov)
	mult <- get.mult.from.conf.level(level)
	new_lowers <- new_betas - mult*sqrt(new_vars)
	new_uppers <- new_betas + mult*sqrt(new_vars)
	new_se     <- sqrt(new_vars)

	cond.means.df <- data.frame(cond.mean=new_betas, se=new_se, var=new_vars, ci.lb=new_lowers, ci.ub=new_uppers)

	cond.means.df.rounded <- round(cond.means.df, digits=digits)
	cond.means.df.str <- paste(capture.output(cond.means.df.rounded), collapse="\n")
	cond.means.data.names <- sort(names(cond.means.data))
	cond.means.data.vals  <- sapply(cond.means.data.names, function(x) cond.means.data[[x]])
	lines = paste(cond.means.data.names, cond.means.data.vals, sep=": ")
	other.vals.str <- paste(lines, sep="\n")
	cond.means.summary <- paste("The conditional means are calculated over the levels of: ", strat.cov,
			"\nThe other covariates had selected values of:\n",
			other.vals.str,"\n",cond.means.df.str,sep="")


	results<-list(
			      "Summary"=paste(capture.output(res), collapse="\n"),
				  "res"=res,
				  "res.info"=rma.uni.value.info(),
				  "Conditional Means Summary"=cond.means.summary,
				  "res.cond.means"=cond.means.df
				)
}

g.bootstrap.meta.regression <- function(data, mods, method, level, digits,
		n.replicates, histogram.title="", bootstrap.plot.path="./r_tmp/bootstrap.png",
		btt=NULL) {

	mods.formula <- make.mods.formula(mods)


	max.failures <- 5*n.replicates
	cat.mods.level.counts <- list()
	for (mod in mods[["categorical"]]) {
		n.levels <- length(levels(data[[mod]]))
		cat.mods.level.counts[[mod]] <- n.levels
	}

	meta.reg.statistic <- function(data, indices) {
		ok = FALSE
		while (!ok) {
			if (failures > max.failures) {
			    stop("Number of failed attempts exceeded 5x the number of replicates")
			}
			if (!subset.ok(data,indices)) {
				failures <<- failures+1
				indices <- sample.int(nrow(data), size=length(indices), replace=TRUE)
				next
			}

			analysis_result <- tryCatch({
						regression.wrapper(data[indices,], mods.formula, method, level, digits,btt)
					  }, error = function(e) {
						failures <<- failures + 1
						indices <- sample.int(nrow(data), size=length(indices), replace=TRUE)
						NULL
					  })
			if (is.null(analysis_result)) {
				next
			}
			ok <- TRUE
		}
		analysis_result$b[,1]
	}

	subset.ok <- function(data, indices) {
		data.subset = data[indices,]

		for (mod in mods[["categorical"]]) {
			n.levels <- length(unique(data[[mod]]))
			if (n.levels != cat.mods.level.counts[[mod]]) {
				return(FALSE)
			}
		}
		return(TRUE)
	}

	failures <- 0
	res.boot <- boot(data, statistic=meta.reg.statistic, R=n.replicates)

	coeff.names <- names(res.boot$t0)
	b=res.boot$t0
	ci.lb <- c()
	ci.ub <- c()
	for (i in 1:length(res.boot$t0)) {
		level <- validate.conf.level(level)
		ci <- boot.ci(boot.out=res.boot, type="norm", index=i, conf=level/100)
		ci.lb <- c(ci.lb, ci[["normal"]][2])
		ci.ub <- c(ci.ub, ci[["normal"]][3])
	}
	boot.summary.df <- data.frame(estimate=b, "Lower bound"=ci.lb, "Upper bound"=ci.ub, check.names=FALSE)
	rownames(boot.summary.df) <- coeff.names
    boot.summary.df.rounded <- round(boot.summary.df, digits=digits)
	boot.summary.df.rounded.str <- paste(capture.output(boot.summary.df.rounded), collapse="\n")
	summary.txt <- sprintf("# Bootstrap replicates: %d\n# of failures: %d\n\n%s", n.replicates,failures, boot.summary.df.rounded.str)


	xlabels <- coeff.names
	png(filename=bootstrap.plot.path, width = 480, height = 480*length(xlabels))
	plot.custom.boot(res.boot,
			title=as.character(histogram.title),
			xlabs=xlabels,
			ci.lb=boot.summary.df[["Lower bound"]],
			ci.ub=boot.summary.df[["Upper bound"]])
	graphics.off()
	images <- c("Histograms"=bootstrap.plot.path)

	results<-list(
		    "images"=images,
			"Bootstrapped Meta Regression Summary"=summary.txt,
			"References"=rcmetar.method.references("bootstrap")
	)
}

g.bootstrap.meta.regression.cond.means <- function(
    data, mods, method, level, digits, strat.cov, cond.means.data,
    n.replicates, histogram.title="", bootstrap.plot.path="./r_tmp/bootstrap.png",
	btt=NULL) {

	mods.formula <- make.mods.formula(mods)

	A <- make.design.matrix(strat.cov, mods, cond.means.data, data)

	max.failures <- 5*n.replicates
	cat.mods.level.counts <- list()
	for (mod in mods[["categorical"]]) {
		n.levels <- length(levels(data[[mod]]))
		cat.mods.level.counts[[mod]] <- n.levels
	}

	cond.means.reg.statistic <- function(data, indices) {
		ok = FALSE
		while (!ok) {
			if (failures > max.failures) {
				stop("Number of failed attempts exceeded 5x the number of replicates")
			}
			if (!subset.ok(data,indices)) {
				failures <<- failures+1
				indices <- sample.int(nrow(data), size=length(indices), replace=TRUE)
				next
			}

			analysis_result <- tryCatch({
						regression.wrapper(data[indices,], mods.formula, method, level, digits,btt)
					}, error = function(e) {
						failures <<- failures + 1
						indices <- sample.int(nrow(data), size=length(indices), replace=TRUE)
						NULL
					})
			if (is.null(analysis_result)) {
				next
			}
			ok <- TRUE
		}

		bootstrap_betas <- A %*% analysis_result$b
		bootstrap_betas[,1]

	}

	subset.ok <- function(data, indices) {
		data.subset = data[indices,]

		for (mod in mods[["categorical"]]) {
			n.levels <- length(unique(data.subset[[mod]]))
			if (n.levels != cat.mods.level.counts[[mod]]) {
				return(FALSE)
			}
		}
		return(TRUE)
	}

	failures <- 0
	res.boot <- boot(data, statistic=cond.means.reg.statistic, R=n.replicates)

	coeff.names <- levels(data[[strat.cov]])
	b=res.boot$t0
	ci.lb <- c()
	ci.ub <- c()
	for (i in 1:length(res.boot$t0)) {
		level <- validate.conf.level(level)
		ci <- boot.ci(boot.out=res.boot, type="norm", index=i, conf=level/100)
		ci.lb <- c(ci.lb, ci[["normal"]][2])
		ci.ub <- c(ci.ub, ci[["normal"]][3])
	}
	boot.summary.df <- data.frame(cond.mean=b, "Lower bound"=ci.lb, "Upper bound"=ci.ub, check.names=FALSE)
	rownames(boot.summary.df) <- coeff.names

	boot.summary.df.rounded <- round(boot.summary.df, digits=digits)
	boot.summary.df.rounded.str <- paste(capture.output(boot.summary.df.rounded), collapse="\n")
	bootstrap.summary <- sprintf("Bootstrap:\n  # Bootstrap replicates: %d\n  # of failures: %d", n.replicates,failures)
	cond.means.data.names <- sort(names(cond.means.data))
	cond.means.data.vals  <- sapply(cond.means.data.names, function(x) cond.means.data[[x]])
	lines = paste(cond.means.data.names, cond.means.data.vals, sep=": ")
	other.vals.str <- paste(lines, sep="\n")
	cond.means.summary <- paste("The conditional means are calculated over the levels of: ", strat.cov,
			"\nThe other covariates had selected values of:\n",
			other.vals.str,sep="")
	summary.txt <- sprintf("%s\n%s\nResults:\n%s", bootstrap.summary, cond.means.summary,boot.summary.df.rounded.str)

	xlabels <- coeff.names
	png(filename=bootstrap.plot.path, width = 480, height = 480*length(xlabels))
	plot.custom.boot(res.boot,
			title=as.character(histogram.title),
			xlabs=xlabels,
			ci.lb=boot.summary.df[["Lower bound"]],
			ci.ub=boot.summary.df[["Upper bound"]])
	graphics.off()
	images <- c("Histograms"=bootstrap.plot.path)

	results<-list(
			"images"=images,
			"Bootstrapped Conditional Means Meta Regression Summary"=summary.txt,
			"res"=boot.summary.df,
			"References"=rcmetar.method.references("bootstrap")
	)
}


meta.regression <- function(reg.data, params, cond.means.data=NULL, stop.at.rma=FALSE) {
	if (is(reg.data, "DiagnosticData")) {
		return(diagnostic.reitsma.meta.regression(reg.data, params, stop.at.rma=stop.at.rma))
	}
	cov.data <- extract.cov.data(reg.data)
	cov.array <- cov.data$cov.array
	cat.ref.var.and.levels <- cov.data$cat.ref.var.and.levels

	method <- as.character(params$rm.method)
	inference.method <- rcmetar.validate.inference.method(
		params,
		length(reg.data@y),
		ncol(cov.array) + 1)


	res<-rma.uni(yi=reg.data@y, sei=reg.data@SE, slab=reg.data@study.names,
					level=params$conf.level, digits=params$digits,
					method=method, test=inference.method, mods=cov.array)
	pure.res<-res
	if (stop.at.rma) {
		return(res)
	}

       display.data <- cov.data$display.data
       reg.disp <- create.regression.display(res, params, display.data)

       if (display.data$n.cont.covs==1 & length(display.data$factor.n.levels)==0) {
            betas <- res$b
            fitted.line <- list(intercept=betas[1], slope=betas[2])
            plot.path <- rcmetar.scratch.path("reg.png")
            if (!is.null(params$bp_outpath) && length(params$bp_outpath) > 0 &&
                    !is.na(params$bp_outpath[1]) && nzchar(as.character(params$bp_outpath[1]))) {
                plot.path <- as.character(params$bp_outpath[1])
            }
            plot.data <- create.plot.data.reg(reg.data, params, fitted.line, res=res)

            plot.data$xlabel <- reg.data@covariates[[1]]@cov.name
            scale.str <- get.scale(params)
            if ((scale.str=="standard") || (scale.str=="arcsine")) {
                scale.str <- ""
            }
            plot.data$ylabel <- paste(scale.str, " ", pretty.metric.name(as.character(params$measure)), sep="")
            meta.regression.plot(plot.data, plot.path)

            plot.data.path <- save.data(reg.data, res, params, plot.data)

            images <- c("Regression Plot"=plot.path)
            plot.names <- c("reg.plot"="reg.plot")
            plot.params.paths <- c("Regression Plot"=plot.data.path)
			pure.res$weights <- weights(res)
            results <- list("input_data"=reg.data,
                            "input_params"=params,
                            "images"=images,
					        "Summary"=reg.disp,
							"plot_names"=plot.names,
							"plot_params_paths"=plot.params.paths,
							"res"=pure.res,
							"res.info"=rma.uni.value.info(),
							"Weights"=weights(res))
  } else if (isnt.null(cond.means.data)) {
			mr.cond.means.disp <- cond_means_display(res, params, display.data, reg.data=reg.data, cat.ref.var.and.levels=cat.ref.var.and.levels, cond.means.data=cond.means.data)
			res.output <- c(pure.res,
							list(Conditional_Means_Section=paste("############################",cond.means.info(cond.means.data), sep="\n"),
								 Conditional_Means=mr.cond.means.disp))
			res.output.info <- c(rma.uni.value.info(),
								 list(Conditional_Means_Section = list(type="vector", description=""),
						              Conditional_Means=list(type="blob", description="")))
			results <- list("Summary"=reg.disp,
							"Conditional Means"=mr.cond.means.disp,
							"res"= res.output,
							"res.info"= res.output.info
							  )


		} else if (display.data$n.cont.covs==0 & length(display.data$factor.n.levels)==1) {
			adj.reg.disp <- adjusted_means_display(res, params, display.data)
			res.output <- c(pure.res,
							list(Adjusted_Means_Section="#############################",
								 Adjusted_Means=adj.reg.disp))
			res.output.info <- c(rma.uni.value.info(),
								 list(Adjusted_Means_Section=list(type="vector", description=""),
									  Adjusted_Means=list(type="blob", description="")))
			results <- list("Summary"=capture.output.and.collapse(reg.disp),
                            "Adjusted Mean"=capture.output.and.collapse(adj.reg.disp),
							"res"=res.output,
							"res.info"=res.output.info)
		} else {
			results <- list("Summary"=reg.disp,
							"res"=pure.res,
							"res.info"=rma.uni.value.info())
		}

	references <- rcmetar.unique.references(c(
		rcmetar.method.references("meta.regression"),
		rcmetar.inference.method.references(params)))
	results[["References"]] <- references
    results
}

meta.regression.parameters <- function() {
    rm.methods <- rcmetar.random.effects.methods()
    list(
        parameters=list("rm.method"=rm.methods, "inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int"),
        defaults=list("rm.method"="REML", "inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS),
        var_order=c("rm.method", "inference.method", "conf.level", "digits")
    )
}

meta.regression.pretty.names <- function() {
    list(
        "pretty.name"="Meta-Regression",
        "description"="Models study-level covariates as predictors of effect estimates.",
        "rm.method"=list(
            "pretty.name"="Random-Effects method",
            "description"="Method for estimating residual between-studies heterogeneity",
            "rm.method.names"=rcmetar.random.effects.method.names()),
        "inference.method"=rcmetar.inference.method.metadata(),
        "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"),
        "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3")
    )
}

cond.means.info <- function(cond.means.data) {
	blurb <- paste("\nConditional means for '",as.character(cond.means.data$chosen.cov.name), "',\nstratified over its levels given the following values for the other covariates:\n", sep="")
	for (name in names(cond.means.data)) {
		if (name != 'chosen.cov.name') {
			blurb <- paste(blurb, name, " = ", cond.means.data[[name]], "\n", sep="")
		}
	}
	return(blurb)
}


extract.cov.data <- function(reg.data, dont.make.array = FALSE) {
  n.cont.covs <- 0
  factor.n.levels <- NULL
  factor.cov.display.col <- NULL
  levels.display.col <- NULL
  studies.display.col <- NULL

  cont.cov.names <- c()
  cont.cov.ranges <- list()
  cont.cov.array <- NULL
  factor.cov.array <- NULL
  factor.cov.names <- c()
  factor.ref.levels <- c()
  cat.cov.ref.var.and.levels <- list()
  for (n.covs in 1:length(reg.data@covariates)) {
    cov <- reg.data@covariates[[n.covs]]
    cov.name <- cov@cov.name
    cov.vals <- cov@cov.vals
    cov.type <- cov@cov.type
	ref.var <- cov@ref.var
    if (cov.type=="continuous") {
      cov.col <- array(cov.vals, dim=c(length(reg.data@y), 1),
                    dimnames=list(NULL, cov.name))
      cont.cov.array <- cbind(cont.cov.array, cov.col)
      cont.cov.names <- c(cont.cov.names, cov.name)
      n.cont.covs <- n.cont.covs + 1
    }
    if (cov.type=="factor") {
      levels <- sort(unique(cov.vals))
      levels.minus.NA <- setdiff(levels, "")
      levels.minus.ref.var <- setdiff(levels.minus.NA, ref.var)


      cov.cols <- array(dim=c(length(reg.data@y), length(levels.minus.ref.var)))
      studies.col <- c(sum(cov.vals==ref.var))
      for (col.index in 1:length(levels.minus.ref.var)) {
           level <- levels.minus.ref.var[col.index]
		   if (!dont.make.array) {
               cov.cols[cov.vals!="" & cov.vals!=level, col.index] <- 0
               cov.cols[cov.vals!="" & cov.vals==level, col.index] <- 1
	       }
           studies.col <- c(studies.col, sum(cov.vals==level))
      }
      factor.cov.array <- cbind(factor.cov.array, cov.cols)
      factor.cov.names <- c(factor.cov.names, cov.name)
      factor.ref.levels <- c(factor.ref.levels, ref.var)
      factor.n.levels <- c(factor.n.levels, length(levels.minus.NA))
      factor.cov.display.col <- c(factor.cov.display.col, cov.name, rep("",length(levels.minus.ref.var)))
      factor.studies.display.col <- c()
      levels.display.col <- c(levels.display.col, ref.var, levels.minus.ref.var)
      studies.display.col <- c(studies.display.col, studies.col)
	  ref.var.and.levels.in.order <- c(ref.var, levels.minus.ref.var)
	  cat.cov.ref.var.and.levels[[cov.name]] <- ref.var.and.levels.in.order
      }
  }
  cov.array <- cbind(cont.cov.array, factor.cov.array)
  analysis.rows <- is.finite(reg.data@y) & is.finite(reg.data@SE) & complete.cases(cov.array)
  for (cov.name in cont.cov.names) {
    analyzed.values <- as.numeric(cont.cov.array[analysis.rows, cov.name])
    analyzed.values <- analyzed.values[is.finite(analyzed.values)]
    cont.cov.ranges[[cov.name]] <- if (length(analyzed.values) > 0) {
      range(analyzed.values)
    } else {
      c(NA_real_, NA_real_)
    }
  }
  cov.display.col <- c("Intercept", cont.cov.names, factor.cov.display.col)
  levels.display.col <- c(rep("",length(cont.cov.names) + 1), levels.display.col)
  studies.display.col <- c(rep("",length(cont.cov.names) + 1), studies.display.col)
  display.data <- list(cov.display.col=cov.display.col, levels.display.col=levels.display.col,
                       studies.display.col=studies.display.col, factor.n.levels=factor.n.levels,
                       factor.cov.names=factor.cov.names, factor.ref.levels=factor.ref.levels,
                       cont.cov.names=cont.cov.names, cont.cov.ranges=cont.cov.ranges,
                       n.cont.covs=n.cont.covs)

  cov.data <- list(cov.array=cov.array, display.data=display.data, cat.ref.var.and.levels=cat.cov.ref.var.and.levels)

}

binary.fixed.meta.regression <- function(reg.data, params){
    cov.data <- array(dim=c(length(reg.data@y), length(cov.names)), dimnames=list(NULL, cov.names))
    for (cov.name in cov.names) {
       cov.vals <- reg.data@covariates[[cov.name]]
       cov.data[,cov.name] <- cov.vals
    }
    inference.method <- rcmetar.validate.inference.method(params, length(reg.data@y), ncol(cov.data) + 1)
    res<-rma.uni(yi=reg.data@y, sei=reg.data@SE, slab=reg.data@study.names,
                                level=params$conf.level, digits=params$digits, method="FE", test=inference.method,
                                mods=cov.data)
    reg.disp <- create.regression.disp(res, params, cov.names)
    if (length(cov.names)==1) {
        betas <- res$b
        fitted.line <- list(intercept=betas[1], slope=betas[2])
        plot.path <- rcmetar.scratch.path("reg.png")
        plot.data <- create.plot.data.reg(reg.data, params, fitted.line, selected.cov=cov.name, res=res)
        meta.regression.plot(plot.data, outpath=plot.path)
        images <- c("Regression Plot"=plot.path)
        plot.names <- c("forest plot"="reg.plot")
        results <- list("images"=images, "Summary"=capture.output.and.collapse(reg.disp), "plot_names"=plot.names)
    } else {
        results <- list("Summary"=capture.output.and.collapse(reg.disp))
    }

}

random.meta.regression <- function(reg.data, params, cov.name){
    cov.vals <- reg.data@covariates[[cov.name]]
    inference.method <- rcmetar.validate.inference.method(params, length(reg.data@y), 2)
    res<-rma.uni(yi=reg.data@y, sei=reg.data@SE, slab=reg.data@study.names,
                                level=params$conf.level, digits=params$digits,
                                method=params$rm.method, test=inference.method,
                                mods=cov.vals)
    reg.disp <- create.regression.disp(res, params)
    reg.disp
    betas <- res$b
    fitted.line <- list(intercept=betas[1], slope=betas[2])
    if (is.null(params$rp_outpath)) {
        plot.path <- rcmetar.scratch.path("reg.png")
    }
    else {
        plot.path <- params$rp_outpath
    }
    plot.data <- create.plot.data.reg(reg.data, params, fitted.line, selected.cov=cov.name, res=res)
    meta.regression.plot(plot.data, outpath=plot.path)
    images <- c("Regression Plot"=plot.path)
    plot.names <- c("forest plot"="reg.plot")
    results <- list("images"=images, "Summary"=capture.output.and.collapse(reg.disp), "plot_names"=plot.names)
    results
}

binary.random.meta.regression.parameters <- function(){
    rm_method_ls <- rcmetar.random.effects.methods()
    params <- list("rm.method"=rm_method_ls, "inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int")

    defaults <- list("rm.method"="DL", "inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS)

    var_order <- c("rm.method", "inference.method", "conf.level", "digits")
    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

categorical.meta.regression <- function(reg.data, params, cov.names) {
  cov.data <- array()
  var.names <- NULL
  for (cov.name in cov.names) {
       groups <- reg.data@covariates[[cov.name]]
       group.list <- unique(groups)
       design_matrix_block <- array(dim=c(length(reg.data@y), length(group.list)-1), dimnames=list(NULL, group.list[-1]))
       for (group in group.list[-1]) {
           design_matrix_block[,group] <- as.numeric(groups == group)
       }
       if (length(cov.data) > 1) {
           cov.data <- cbind(cov.data, design_matrix_block)
       } else {
           cov.data <- design_matrix_block
       }
  }
  inference.method <- rcmetar.validate.inference.method(params, length(reg.data@y), ncol(cov.data) + 1)
  res <-rma.uni(yi=reg.data@y, sei=reg.data@SE, slab=reg.data@study.names,
                                level=params$conf.level, digits=params$digits, method="FE", test=inference.method,
                                mods=cov.data)
  reg.disp <- create.regression.disp(res, params, cov.names=dimnames(cov.data)[[2]])
  results <- list("Summary"=reg.disp)
}
