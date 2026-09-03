# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

cum_meta_analysis_ref = 'Cumulative Meta-Analysis: Lau, Joseph, et al. "Cumulative meta-analysis of therapeutic trials for myocardial infarction." New England Journal of Medicine 327.4 (1992): 248-254.'
subgroup_ma_ref = "Subgroup Meta-Analysis: estimates are recomputed within covariate-defined study groups using the selected base meta-analysis method."
loo_ma_ref = "Leave-one-out Meta-Analysis: estimates are recomputed after omitting each study in turn to assess influence on the selected base meta-analysis method."

cum.ma.binary <- function(fname, binary.data, params){
    if (!("BinaryData" %in% class(binary.data))) stop("Binary data expected.")

    suppressed_params <- params
	suppressed_params$supress.output <- TRUE
    res <- eval(call(fname, binary.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))

    cum.results <- array(list(NULL), dim=c(length(binary.data@study.names)))

    for (i in 1:length(binary.data@study.names)){
        subset_effects <- binary.data@y[1:i]
        subset_standard_errors <- binary.data@SE[1:i]
        subset_study_names <- binary.data@study.names[1:i]
        subset_binary_data <- NULL
        if (length(binary.data@g1O1) > 0){
            subset_g1O1 <- binary.data@g1O1[1:i]
            subset_g1O2 <- binary.data@g1O2[1:i]
            subset_g2O1 <- binary.data@g2O1[1:i]
            subset_g2O2 <- binary.data@g2O2[1:i]
            subset_binary_data <- new('BinaryData', g1O1=subset_g1O1,
                               g1O2=subset_g1O2 , g2O1=subset_g2O1,
                               g2O2=subset_g2O2, y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
        } else {
            subset_binary_data <- new('BinaryData', y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
        }
        current_result <- eval(call(fname, subset_binary_data, suppressed_params))
        current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
        cum.results[[i]] <- current_overall
    }
    study.names <- binary.data@study.names[1]
    for (count in 2:length(binary.data@study.names)) {
        study.names <- c(study.names, paste("+ ",binary.data@study.names[count], sep=""))
    }
    metric.name <- pretty.metric.name(as.character(suppressed_params$measure))
	model.title <- switch(fname,
                          binary.fixed.inv.var=paste("Binary Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
                          binary.fixed.mh=paste("Binary Fixed-Effect Model - Mantel-Haenszel\n\nMetric: ", metric.name, sep=""),
                          binary.fixed.peto=paste("Binary Fixed-Effect Model - Peto\n\nMetric: ", metric.name, sep=""),
                          binary.random=paste("Binary Random-Effects Model\n\nMetric: ", metric.name, sep=""))
	value.info <- switch(fname,
                         binary.fixed.inv.var = cumul.rma.uni.value.info(),
                         binary.fixed.mh      = cumul.rma.mh.value.info(),
                         binary.fixed.peto    = cumul.rma.mh.value.info(),
                         binary.random        = cumul.rma.uni.value.info())
    cum.disp <- create.overall.display(res=cum.results, study.names, params, model.title, data.type="binary")
    forest.path <- paste(params$fp_outpath, sep="")
    params.cum <- params
    params.cum$fp_col1_str <- "Cumulative Studies"
    params.cum$fp_col2_str <- "Cumulative Estimate"
    plot.data.cum <- create.plot.data.cum(om.data=binary.data, params.cum, res=cum.results)
    if (rcmetar.metafor.default.supported(params.cum)) {
        plot.data <- rcmetar.build.sequential.metafor.bundle(binary.data, params.cum, cum.results, "cumulative", study.names, plot.data.cum)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    }
    params <- update.changed.plot.params(params, changed.params)
    forest.plot.params.path <- save.data(binary.data, res, params, plot.data)
    plot.params.paths <- c("Cumulative Forest Plot"=forest.plot.params.path)
    images <- c("Cumulative Forest Plot"=forest.path)
    plot.names <- c("cumulative forest plot"="cumulative_forest_plot")

	references <- c(res$References, cum_meta_analysis_ref)

    results <- list("images"=images,
			        "Cumulative Summary"=cum.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references),
					"res"=construct.sequential.res.output(cum.results, value.info, replacements=list(estimate='b')),
					"res.info"=list(summary.table=list(type="data.frame", description=""))
                   )

    results
}

construct.sequential.res.output <- function(seq.res, value.info, replacements=list()) {

	value.names <- names(value.info)
	results.table <- c()

	get.val<-function(x) {
		if (name %in% names(replacements))
			val <- x[[replacements[[name]]]]
		else
			val <- x[[name]]

		if (is.null(val))
			val <- NA
		val
	}

	for (name in value.names) {
		column <- unlist(sapply(seq.res,get.val))
		results.table <- cbind(results.table, column)
	}
	results.table <- as.data.frame(results.table)
	names(results.table) <- value.names

	list(summary.table=results.table)
}

construct.subgroup.res.output <- function(subgroups.res) {

	output = list()
	count = 0
	for (res in subgroups.res) {
		count <- count + 1
		output[[count]] <- res
	}
	output
}

construct.subgroup.value.info <- function(value.info, subgroup.list) {

	subgroup.value.info <- list()
	for (subgroup_name in subgroup.list) {
		subgroup.title<-paste("Subgroup",subgroup_name, sep=" ")
		subgroup.value.info[[subgroup.title]] = value.info
	}
	subgroup.value.info[["Overall"]] = value.info
	subgroup.value.info
}


bootstrap.binary <- function(fname, omdata, params, cond.means.data=FALSE) {
	bootstrap(fname, omdata, params, cond.means.data)
}
bootstrap.continuous <- function(fname, omdata, params, cond.means.data=FALSE) {
	bootstrap(fname, omdata, params, cond.means.data)
}

bootstrap <- function(fname, omdata, params, cond.means.data=FALSE) {


	omdata.rows <- seq(1:length(omdata@y))


	conf.level <- params$conf.level
	max.extra.attempts <- 5*params$num.bootstrap.replicates
	bootstrap.type <- as.character(params$bootstrap.type)
	bootstrap.plot.path <- as.character(params$bootstrap.plot.path)
	if (is.null(bootstrap.plot.path)) {
		bootstrap.plot.path <- "./r_tmp/bootstrap.png"
	}

	if (length(omdata@covariates) > 0) {
		cov.data <- extract.cov.data(omdata, dont.make.array=TRUE)
		factor.n.levels <- cov.data$display.data$factor.n.levels
		n.cont.covs <- cov.data$display.data$n.cont.covs
		cat.ref.var.and.levels <- cov.data$cat.ref.var.and.levels
		expected.coeff.count <- 1 + n.cont.covs + sum(factor.n.levels - 1)
	}


	vanilla.statistic <- function(data, indices) {
		suppressed_params <- params
		suppressed_params$create.plot <- FALSE
		suppressed_params$write.to.file <- FALSE

		subset_data <- get.subset(omdata, indices, make.unique.names=TRUE)


	   res <- eval(call(fname, subset_data, suppressed_params))
	   res.pure <- eval(call(paste(fname, ".overall", sep=""), res))
	   res.pure$b
	}


	meta.reg.statistic <- function(data, indices) {
		data.ok <- function(data.subset) {
			subset.cov.data <- extract.cov.data(data.subset, dont.make.array=TRUE)
			subset.factor.n.levels <- subset.cov.data$display.data$factor.n.levels
			subset.n.cont.covs <- subset.cov.data$display.data$n.cont.covs
			subset.cat.ref.var.and.levels <- subset.cov.data$cat.ref.var.and.levels

			if (!(all(factor.n.levels==subset.factor.n.levels) && all(n.cont.covs==subset.n.cont.covs)))
				return(FALSE)

			return(TRUE)
		}
		result.ok <- function(res) {
			length(res$b[,1]) == expected.coeff.count
		}

		subset_data <- get.subset(omdata, indices, make.unique.names=TRUE)
		error.during.meta.regression <- FALSE
		first.try <- TRUE
		result.wrong.shape <- FALSE
		while (first.try || !data.ok(subset_data) || error.during.meta.regression || result.wrong.shape) {
			if (extra.attempts >= max.extra.attempts)
				stop("Number of extra attempts exceeded 5x the number of replicates")


			if (!first.try || result.wrong.shape) {
				extra.attempts <<- extra.attempts + 1
				new.indices <- sample.int(length(omdata.rows), size=length(indices), replace=TRUE)
				subset_data <- get.subset(omdata, new.indices, make.unique.names=TRUE)
				error.during.meta.regression <- FALSE
				result.wrong.shape <- FALSE
			} else {
				first.try <- FALSE
			}

			if (data.ok(subset_data)) {

				res <- try(meta.regression(subset_data, params, stop.at.rma=TRUE), silent=FALSE)
				if (class(res)[1] == "try-error") {
					error.during.meta.regression <- TRUE
				}
				else {
					error.during.meta.regression <- FALSE
					result.wrong.shape <- !result.ok(res)
				}
			}
		}


		res$b
	}

	if (bootstrap.type == "boot.meta.reg.cond.means")
		a.matrix <- generate.a.matrix(omdata, cat.ref.var.and.levels, cond.means.data)
	meta.reg.cond.means.statistic <- function(data, indices) {
		unconditional.b <- meta.reg.statistic(data, indices)
		new_betas  <- a.matrix %*% matrix(unconditional.b, ncol=1)
		new_betas
	}

	statistic <- switch(bootstrap.type,
						boot.ma = vanilla.statistic,
						boot.meta.reg = meta.reg.statistic,
						boot.meta.reg.cond.means = meta.reg.cond.means.statistic)
	extra.attempts <- 0
	boot.res <- boot(omdata.rows, statistic=statistic, R=params$num.bootstrap.replicates)
	params$extra.attempts <- extra.attempts

	results <- switch(bootstrap.type,
			boot.ma = boot.ma.output.results(boot.res, params, bootstrap.plot.path),
			boot.meta.reg = boot.meta.reg.output.results(boot.res, params, bootstrap.plot.path, cov.data),
			boot.meta.reg.cond.means = boot.meta.reg.cond.means.output.results(omdata, boot.res, params, bootstrap.plot.path, cov.data, cond.means.data))

	textfile.data <- construct.boot.res.and.value.info.for.results(results, boot.res, bootstrap.type)
	results <- c(results, textfile.data)
	results[["References"]] <- rcmetar.unique.references(c(results[["References"]], rcmetar.method.references("bootstrap")))

	results

}

construct.boot.res.and.value.info.for.results <- function(results, boot.res, bootstrap.type) {
	summary <- switch(bootstrap.type,
					  boot.ma = results$Summary,
				      boot.meta.reg = results$Summary,
					  boot.meta.reg.cond.means = results[["Bootstrapped Meta-Regression Based Conditional Means"]])
	summary.name <- switch(bootstrap.type,
			          boot.ma = "Summary",
					  boot.meta.reg = "Summary",
					  boot.meta.reg.cond.means = "Bootstrapped Meta-Regression Based Conditional Means Summary")
	xlabels <- switch(bootstrap.type,
					  boot.ma = NA,
					  boot.meta.reg = results$gui.ignore.xlabels,
					  boot.meta.reg.cond.means = results$gui.ignore.xlabels)
	res <- list()
	res.info <- list()
	res[[summary.name]] <- summary
	res.info[[summary.name]] <- list(type="blob", description="")

	if (any(isnt.na(xlabels))) {
		res[['coefficient_labels']] = xlabels
		res.info[['coefficient_labels']] = list(type="vector", description="Coefficients in t given in the following order")
	}

	res$t <- boot.res$t
	res.info$t <- list(type="matrix", description="A matrix with #replicates rows, each of which is a bootstrap replicate")

	list(res=res,
		 res.info=res.info)
}


boot.ma.output.results <- function(boot.results, params, bootstrap.plot.path) {
	conf.interval <- boot.ci(boot.out = boot.results, type = "norm")
	mean_boot <- mean(boot.results$t)

	conf.interval.msg <- paste("The ", conf.interval$norm[1]*100, "% Confidence Interval: [", round(conf.interval$norm[2],digits=params$digits), ", ", round(conf.interval$norm[3],digits=params$digits), "]", sep="")
	mean.msg <- paste("The observed value of the effect size was ", round(boot.results$t0, digits=params$digits), ", while the mean over the replicates was ", round(mean_boot,digits=params$digits), ".", sep="")
	summary.msg <- paste(conf.interval.msg, "\n", mean.msg, sep="")
	png(filename=bootstrap.plot.path)
	plot.custom.boot(boot.results, title=as.character(params$histogram.title), xlabs=c(as.character(params$histogram.xlab)), ci.lb=conf.interval$norm[2], ci.ub=conf.interval$norm[3])
	graphics.off()

	images <- c("Histogram"=bootstrap.plot.path)
	plot.names <- c("histogram"="histogram")
	results <- list("images"=images,
			"Summary"=summary.msg)
	results
}

calc.meta.reg.coeffs.and.cis <- function(boot.results) {
	dim.t <- dim(boot.results$t)
	num.rows <- dim.t[1]
	num.coeffs <- dim.t[2]

	coeffs.and.cis <- data.frame(b=c(), ci.lb=c(), ci.ub=c())
	for (i in 1:num.coeffs) {
		mean_coeff <- mean(boot.results$t[,i])
		conf.interval <- boot.ci(boot.out = boot.results, type="norm", index=i)
		new.result.row <- data.frame(b=mean_coeff, ci.lb=conf.interval$norm[2], ci.ub=conf.interval$norm[3])
		coeffs.and.cis <- rbind(coeffs.and.cis, new.result.row)
	}
	coeffs.and.cis
}

boot.meta.reg.output.results <- function(boot.results, params, bootstrap.plot.path, cov.data) {
	coeffs.and.cis <- calc.meta.reg.coeffs.and.cis(boot.results)


	display.data <- cov.data$display.data
	reg.disp <- create.regression.display(coeffs.and.cis, params, display.data)



	cov.display.col <- display.data$cov.display.col
	levels.display.col <- display.data$levels.display.col
	factor.n.levels <- display.data$factor.n.levels

	non.empty.levels.labels    <- levels.display.col[levels.display.col!=""]
	wanted.cov.display.col.labels <- cov.display.col[1:(length(cov.display.col)-length(non.empty.levels.labels))]
	factor.index <- 0
	for (n.level in factor.n.levels) {
		non.empty.levels.labels[(factor.index+1)] <- ""
		factor.index <- factor.index + n.level
	}
	non.empty.levels.labels <- non.empty.levels.labels[non.empty.levels.labels!=""]

	xlabels <- c(wanted.cov.display.col.labels,non.empty.levels.labels)
	xlabels.clean <- xlabels
	xlabels <- paste(xlabels, "Coefficient")

	png(filename=bootstrap.plot.path, width = 480, height = 480*length(xlabels))
	plot.custom.boot(boot.results,
					 title=as.character(params$histogram.title),
					 xlabs=xlabels,
					 ci.lb=coeffs.and.cis$ci.lb,
					 ci.ub=coeffs.and.cis$ci.ub)
	graphics.off()

	images <- c("Histograms"=bootstrap.plot.path)
	plot.names <- c("histograms"="histograms")
	output.results <- list("images"=images,
						   "Summary"=reg.disp,
						   "gui.ignore.xlabels"=xlabels.clean)
	output.results
}

boot.meta.reg.cond.means.output.results <- function(omdata, boot.results, params, bootstrap.plot.path, cov.data, cond.means.data) {
	coeffs.and.cis <- calc.meta.reg.coeffs.and.cis(boot.results)
	cat.ref.var.and.levels <- cov.data$cat.ref.var.and.levels
	chosen.cov.name = as.character(cond.means.data$chosen.cov.name)

	boot.cond.means.disp <- boot.cond.means.display(omdata, coeffs.and.cis, params, cat.ref.var.and.levels, cond.means.data)

	xlabels <- cat.ref.var.and.levels[[chosen.cov.name]]
	xlabels.clean <- xlabels
	xlabels <- paste("Conditional Mean of", xlabels)

	png(filename=bootstrap.plot.path, width = 480, height = 480*length(xlabels))
	plot.custom.boot(boot.results,
			title=as.character(params$histogram.title),
			xlabs=xlabels,
			ci.lb=coeffs.and.cis$ci.lb,
			ci.ub=coeffs.and.cis$ci.ub)
	graphics.off()

	images <- c("Histograms"=bootstrap.plot.path)
	plot.names <- c("histograms"="histograms")
	output.results <- list("images"=images,
						   "Bootstrapped Meta-Regression Based Conditional Means"=boot.cond.means.disp,
						   "gui.ignore.xlabels"=xlabels.clean)
	output.results
}

plot.custom.boot <- function(boot.out, title="Bootstrap Histogram", ci.lb, ci.ub, xlabs=c("Effect Size")) {

	const <- function(w, eps=1e-8) {
		all(abs(w-mean(w, na.rm=TRUE)) < eps)
	}
	num.hists <- length(xlabs)
	par(mfcol=c(num.hists,1))
	for (index in 1:num.hists) {
		qdist <- "norm"
		t <- boot.out$t[,index]
		t0 <- boot.out$t0[index]
		t <- t[is.finite(t)]
		if (const(t, min(1e-8,mean(t, na.rm=TRUE)/1e6))) {
			return(invisible(boot.out))
		}
		nclass <- min(max(ceiling(length(t)/25),10),100)
		R <- boot.out$R

		hist(t,nclass=nclass,probability=TRUE,xlab=xlabs[index], main=title)
		abline(v=t0,lty=1)
				abline(v=ci.lb[index],lty=3)
		abline(v=ci.ub[index],lty=3)
	}
}

loo.ma.binary <- function(fname, binary.data, params){
    if (!("BinaryData" %in% class(binary.data))) stop("Binary data expected.")

    loo.results <- array(list(NULL), dim=c(length(binary.data@study.names)))
    suppressed_params <- params

	suppressed_params$supress.output <- TRUE
    res <- eval(call(fname, binary.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))
    N <- length(binary.data@study.names)
    for (i in 1:N){
        index.ls <- setdiff(1:N, i)

        subset_effects <- binary.data@y[index.ls]
        subset_standard_errors <- binary.data@SE[index.ls]
        subset_study_names <- binary.data@study.names[index.ls]
        subset_binary_data <- NULL

        if (length(binary.data@g1O1) > 0){
            subset_g1O1 <- binary.data@g1O1[index.ls]
            subset_g1O2 <- binary.data@g1O2[index.ls]
            subset_g2O1 <- binary.data@g2O1[index.ls]
            subset_g2O2 <- binary.data@g2O2[index.ls]
            subset_binary_data <- new('BinaryData', g1O1=subset_g1O1,
                               g1O2=subset_g1O2 , g2O1=subset_g2O1,
                               g2O2=subset_g2O2, y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
        } else{
            subset_binary_data <- new('BinaryData', y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
        }
        current_result <- eval(call(fname, subset_binary_data, suppressed_params))
        current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
        loo.results[[i]] <- current_overall
    }
    loo.results <- c(list(res.overall), loo.results)



    study.names <- c("Overall", paste("- ",binary.data@study.names, sep=""))
    metric.name <- pretty.metric.name(as.character(params$measure))
	model.title <- switch(fname,
			binary.fixed.inv.var = paste("Binary Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
			binary.fixed.mh = paste("Binary Fixed-Effect Model - Mantel-Haenszel\n\nMetric: ", metric.name, sep=""),
			binary.fixed.peto = paste("Binary Fixed-Effect Model - Peto\n\nMetric: ", metric.name, sep=""),
			binary.random = paste("Binary Random-Effects Model\n\nMetric: ", metric.name, sep=""))
	value.info <- switch(fname,
			binary.fixed.inv.var = loo.rma.uni.value.info(),
			binary.fixed.mh      = loo.rma.mh.value.info(),
			binary.fixed.peto    = loo.rma.mh.value.info(),
			binary.random        = loo.rma.uni.value.info())
	loo.disp <- create.overall.display(res=loo.results, study.names, params, model.title, data.type="binary")
    forest.path <- paste(params$fp_outpath, sep="")
    plot.data <- create.plot.data.loo(binary.data, params, res=loo.results)
    changed.params <- plot.data$changed.params
    if (rcmetar.metafor.default.supported(params)) {
        plot.data <- rcmetar.build.sequential.metafor.bundle(binary.data, params, loo.results, "leave-one-out", study.names, plot.data)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    } else {
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    }
    changed.params <- c(changed.params, params.changed.in.forest.plot)
    params <- update.changed.plot.params(params, changed.params)
    forest.plot.params.path <- save.data(binary.data, res=loo.results, params, plot.data)
    plot.params.paths <- c("Leave-one-out Forest Plot"=forest.plot.params.path)
    images <- c("Leave-one-out Forest Plot"=forest.path)
    plot.names <- c("loo forest plot"="loo_forest_plot")
	references <- c(res$References, loo_ma_ref)
    results <- list("images"=images,
			        "Leave-one-out Summary"=loo.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references),
					"res"=construct.sequential.res.output(loo.results,
						                                  value.info,
														  replacements=list(estimate='b',
									                                        Q='QE',
																			Qp='QEp')),
					"res.info"=list(summary.table=list(type="data.frame", description=""))
			)
    results
}

cum.ma.continuous <- function(fname, cont.data, params){
    if (!("ContinuousData" %in% class(cont.data))) stop("Continuous data expected.")

    suppressed_params <- params
	suppressed_params$supress.output <- TRUE
    res <- eval(call(fname, cont.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))

    params$fp_show_col3 <- FALSE
    params$fp_show_col4 <- FALSE
    params$fp_col1_str <- "Cumulative Studies"

    cum.results <- array(list(NULL), dim=c(length(cont.data@study.names)))

    for (i in 1:length(cont.data@study.names)){
        subset_effects <- cont.data@y[1:i]
        subset_standard_errors <- cont.data@SE[1:i]
        subset_study_names <- cont.data@study.names[1:i]
        subset_continuous_data <- NULL
        if (length(cont.data@N1) > 0){
            subset_N1 <- cont.data@N1[1:i]
            subset_mean1 <- cont.data@mean1[1:i]
            subset_sd1 <- cont.data@sd1[1:i]
            subset_N2 <- cont.data@N2[1:i]
            subset_mean2 <- cont.data@mean2[1:i]
            subset_sd2 <- cont.data@sd2[1:i]
            subset_continuous_data <- new('ContinuousData',
                               N1=subset_N1, mean1=subset_mean1 , sd1=subset_sd1,
                               N2=subset_N2, mean2=subset_mean2, sd2=subset_sd2,
                               y=subset_effects, SE=subset_standard_errors,
                               study.names=subset_study_names)
        }
        else{
            subset_continuous_data <- new('ContinuousData',
                                y=subset_effects, SE=subset_standard_errors,
                                study.names=subset_study_names)
        }
        current_result <- eval(call(fname, subset_continuous_data, suppressed_params))
        current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
        cum.results[[i]] <- current_overall
    }
    study.names <- c()
    study.names <- cont.data@study.names[1]
    for (count in 2:length(cont.data@study.names)) {
        study.names <- c(study.names, paste("+ ",cont.data@study.names[count], sep=""))
    }

    metric.name <- pretty.metric.name(as.character(params$measure))
	model.title <- switch(fname,
                          continuous.fixed  = paste("Continuous Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
						  continuous.random = paste("Continuous Random-Effects Model\n\nMetric: ", metric.name, sep=""))
    value.info <- switch(fname,
						 continuous.fixed  = cumul.rma.uni.value.info(),
	                     continuous.random = cumul.rma.uni.value.info())

	cum.disp <- create.overall.display(res=cum.results, study.names, params, model.title, data.type="continuous")
    forest.path <- paste(params$fp_outpath, sep="")
    params.cum <- params
    params.cum$fp_col1_str <- "Cumulative Studies"
    params.cum$fp_col2_str <- "Cumulative Estimate"
    plot.data.cum <- create.plot.data.cum(om.data=cont.data, params.cum, res=cum.results)
    if (rcmetar.metafor.default.supported(params.cum)) {
        plot.data <- rcmetar.build.sequential.metafor.bundle(cont.data, params.cum, cum.results, "cumulative", study.names, plot.data.cum)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    }
    params <- update.changed.plot.params(params, changed.params)
    forest.plot.params.path <- save.data(cont.data, res=cum.results, params, plot.data)
    plot.params.paths <- c("Cumulative Forest Plot"=forest.plot.params.path)
    images <- c("Cumulative Forest Plot"=forest.path)
    plot.names <- c("cumulative forest plot"="cumulative forest_plot")

	references <- c(res$References, cum_meta_analysis_ref)
    results <- list("images"=images,
			        "Cumulative Summary"=cum.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references),
					"res"=construct.sequential.res.output(cum.results, value.info, replacements=list(estimate='b')),
					"res.info"=list(summary.table=list(type="data.frame", description=""))
			)
    results
}


cum.ma.diagnostic <- function(fname, diagnostic.data, params){
	if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")

	suppressed_params <- params
	suppressed_params$create.plot <- FALSE
	suppressed_params$write.to.file <- FALSE
	res <- eval(call(fname, diagnostic.data, suppressed_params))
	res.overall <- eval(call(paste(fname, ".overall", sep=""), res))


	cum.results <- array(list(NULL), dim=c(length(diagnostic.data@study.names)))

	for (i in 1:length(diagnostic.data@study.names)){
		subset_effects <- diagnostic.data@y[1:i]
		subset_standard_errors <- diagnostic.data@SE[1:i]
		subset_study_names <- diagnostic.data@study.names[1:i]
		subset_binary_data <- NULL

		if (length(diagnostic.data@TP) > 0){
			subset_TP <- diagnostic.data@TP[1:i]
			subset_FN <- diagnostic.data@FN[1:i]
			subset_FP <- diagnostic.data@FP[1:i]
			subset_TN <- diagnostic.data@TN[1:i]
			subset_diagnostic_data <- new('DiagnosticData', TP=subset_TP,
					FN=subset_FN , FP=subset_FP,
					TN=subset_TN, y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
		} else {
			subset_diagnostic_data <- new('DiagnosticData', y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
		}
		current_result <- eval(call(fname, subset_diagnostic_data, suppressed_params))
		current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
		cum.results[[i]] <- current_overall
	}
	study.names <- diagnostic.data@study.names[1]
	for (count in 2:length(diagnostic.data@study.names)) {
		study.names <- c(study.names, paste("+ ", diagnostic.data@study.names[count], sep=""))
	}
	metric.name <- pretty.metric.name(as.character(suppressed_params$measure))
	model.title <- switch(fname,
                          diagnostic.fixed.inv.var = paste("Diagnostic Fixed-Effect Inverse Variance\n\nMetric: ", metric.name, sep=""),
                          diagnostic.fixed.mh      = paste("Diagnostic Fixed-Effect Mantel-Haenszel\n\nMetric: ", metric.name, sep=""),
                          diagnostic.fixed.peto    = paste("Diagnostic Fixed-Effect Peto\n\nMetric: ", metric.name, sep=""),
                          diagnostic.random        = paste("Diagnostic Random-Effects\n\nMetric: ", metric.name, sep=""))
	cum.disp <- create.overall.display(res=cum.results, study.names, params, model.title, data.type="diagnostic")
	forest.path <- paste(params$fp_outpath, sep="")
	params.cum <- params
	params.cum$fp_col1_str <- "Cumulative Studies"
	params.cum$fp_col2_str <- "Cumulative Estimate"
	plot.data.cum <- create.plot.data.cum(om.data=diagnostic.data, params.cum, res=cum.results)
	if (rcmetar.metafor.default.supported(params.cum)) {
		plot.data <- rcmetar.build.sequential.metafor.bundle(diagnostic.data, params.cum, cum.results, "cumulative", study.names, plot.data.cum)
		changed.params <- plot.data$changed.params
		params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
	}
	params <- update.changed.plot.params(params, changed.params)
	forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)
	plot.params.paths <- c("Cumulative Forest Plot"=forest.plot.params.path)
	images <- c("Cumulative Forest Plot"=forest.path)
	plot.names <- c("cumulative forest plot"="cumulative_forest_plot")

	references <- c(res$References, cum_meta_analysis_ref)

	results <- list("images"=images,
			        "Cumulative Summary"=cum.disp,
			        "plot_names"=plot.names,
					"plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references))
	results
}


multiple.cum.ma.diagnostic <- function(fnames, params.list, diagnostic.data) {



	results <- list()
	pretty.names <- diagnostic.fixed.inv.var.pretty.names()
	images <- c()
	plot.names <- c()
	plot.params.paths <- c()

	references <- c()

	for (count in 1:length(params.list)) {
		params <- params.list[[count]]
		fname <- fnames[count]
		diagnostic.data <- compute.diag.point.estimates(diagnostic.data, params)
		res <- cum.ma.diagnostic(fname, diagnostic.data, params)

		summary <- list("Summary"=res[["Cumulative Summary"]])
		names(summary) <- paste(eval(parse(text=paste("pretty.names$measure$", params$measure,sep=""))), " Summary", sep="")

		results <- c(results, summary)

		image.name <- paste(params$measure, "Forest Plot", sep=" ")
		analysis_images <- c(res$images[[1]])
		names(analysis_images) <- image.name
		images <- c(images, analysis_images)
		analysis_plot_paths <- res$plot_params_paths
		names(analysis_plot_paths) <- image.name
		plot.params.paths <- c(plot.params.paths, analysis_plot_paths)

		analysis_plot_names <- c("forest plot"="forest.plot")
		plot.names <- c(plot.names, analysis_plot_names)


		references <- c(references, res$References)

	}

	results <- c(results, list("images"=images,
					           "plot_names"=plot.names,
							   "plot_params_paths"=plot.params.paths,
							   "References"=rcmetar.unique.references(references)))
	results



}

loo.ma.continuous <- function(fname, cont.data, params){
    if (!("ContinuousData" %in% class(cont.data))) stop("Continuous data expected.")

    loo.results <- array(list(NULL), dim=c(length(cont.data@study.names)))
    suppressed_params <- params
	suppressed_params$supress.output <- TRUE
    res <- eval(call(fname, cont.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))
    N <- length(cont.data@study.names)
    for (i in 1:N){
        index.ls <- setdiff(1:N, i)

        subset_effects <- cont.data@y[index.ls]
        subset_standard_errors <- cont.data@SE[index.ls]
        subset_study_names <- cont.data@study.names[index.ls]
        subset_continuous_data <- NULL

        if (length(cont.data@N1) > 0){
            subset_N1 <- cont.data@N1[index.ls]
            subset_mean1 <- cont.data@mean1[index.ls]
            subset_sd1 <- cont.data@sd1[index.ls]
            subset_N2 <- cont.data@N2[index.ls]
            subset_mean2 <- cont.data@mean2[index.ls]
            subset_sd2 <- cont.data@sd2[index.ls]
            subset_continuous_data <- new('ContinuousData',
                               N1=subset_N1, mean1=subset_mean1 , sd1=subset_sd1,
                               N2=subset_N2, mean2=subset_mean2, sd2=subset_sd2,
                               y=subset_effects, SE=subset_standard_errors,
                               study.names=subset_study_names)
        }
        else{
            subset_continuous_data <- new('ContinuousData',
                                y=subset_effects, SE=subset_standard_errors,
                                study.names=subset_study_names)
        }
        current_result <- eval(call(fname, subset_continuous_data, suppressed_params))
        current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
        loo.results[[i]] <- current_overall
    }
    loo.results <- c(list(res.overall), loo.results)
    study.names <- c("Overall", paste("- ", cont.data@study.names, sep=""))
    params$data.type <- "continuous"
    metric.name <- pretty.metric.name(as.character(params$measure))
	model.title <- switch(fname,
			continuous.fixed=paste("Continuous Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
			continuous.random=paste("Continuous Random-Effects Model\n\nMetric: ", metric.name, sep=""))
	value.info <- switch(fname,
			continuous.fixed  = loo.rma.uni.value.info(),
			continuous.random = loo.rma.uni.value.info())
	loo.disp <- create.overall.display(res=loo.results, study.names, params, model.title, data.type="continuous")
    forest.path <- paste(params$fp_outpath, sep="")
    plot.data <- create.plot.data.loo(cont.data, params, res=loo.results)
    changed.params <- plot.data$changed.params
    if (rcmetar.metafor.default.supported(params)) {
        plot.data <- rcmetar.build.sequential.metafor.bundle(cont.data, params, loo.results, "leave-one-out", study.names, plot.data)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    } else {
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    }
    changed.params <- c(changed.params, params.changed.in.forest.plot)
    params <- update.changed.plot.params(params, changed.params)
    forest.plot.params.path <- save.data(cont.data, res=loo.results, params, plot.data)
    plot.params.paths <- c("Leave-one-out Forest Plot"=forest.plot.params.path)
    images <- c("Leave-one-out Forest Plot"=forest.path)
    plot.names <- c("loo forest plot"="loo_forest_plot")
	references <- c(res$References, loo_ma_ref)
    results <- list("images"=images,
			        "Leave-one-out Summary"=loo.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references),
					"res"=construct.sequential.res.output(loo.results,
							value.info,
							replacements=list(estimate='b',
									Q='QE',
									Qp='QEp')),
					"res.info"=list(summary.table=list(type="data.frame", description=""))
			)
    results
}

subgroup.ma.binary <- function(fname, binary.data, params){
    if (!("BinaryData" %in% class(binary.data))) stop("Binary data expected.")
    cov.name <- as.character(params$cov_name)
    selected.cov <- get.cov(binary.data, cov.name)
    cov.vals <- selected.cov@cov.vals
    suppressed_params <- params
	suppressed_params$supress.output <- TRUE
    subgroup.list <- unique(cov.vals)
    grouped.data <- array(list(NULL),c(length(subgroup.list)+1))
    subgroup.results <- array(list(NULL), c(length(subgroup.list)+1))
    col3.nums <- NULL
    col3.denoms <- NULL
    col4.nums <- NULL
    col4.denoms <- NULL
    count <- 1
    for (i in subgroup.list){
      subset_binary_data <- get.subgroup.data.binary(binary.data, i, cov.vals)
      grouped.data[[count]] <- subset_binary_data
      col3.nums <- c(col3.nums, subset_binary_data@g1O1, sum(subset_binary_data@g1O1))
      col3.denoms <- c(col3.denoms, subset_binary_data@g1O1 + subset_binary_data@g1O2, sum(subset_binary_data@g1O1 + subset_binary_data@g1O2))
      col4.nums <- c(col4.nums, subset_binary_data@g2O1, sum(subset_binary_data@g2O1))
      col4.denoms <- c(col4.denoms, subset_binary_data@g2O1 + subset_binary_data@g2O2, sum(subset_binary_data@g2O1 + subset_binary_data@g2O2))
      current_result <- eval(call(fname, subset_binary_data, suppressed_params))
      current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
      subgroup.results[[count]] <- current_overall
      count <- count + 1
    }
    res <- eval(call(fname, binary.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))
    grouped.data[[count]] <- binary.data
    subgroup.results[[count]] <- res.overall
    subgroup.names <- paste("Subgroup ", subgroup.list, sep="")
    subgroup.names <- c(subgroup.names, "Overall")
    metric.name <- pretty.metric.name(as.character(params$measure))
	model.title <- switch(fname,
		binary.fixed.inv.var = paste("Binary Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
		binary.fixed.mh = paste("Binary Fixed-Effect Model - Mantel-Haenszel\n\nMetric: ", metric.name, sep=""),
		binary.fixed.peto = paste("Binary Fixed-Effect Model - Peto\n\nMetric: ", metric.name, sep=""),
		binary.random = paste("Binary Random-Effects Model\n\nMetric: ", metric.name, sep=""))
	value.info <- switch(fname,
		binary.fixed.inv.var = binary.fixed.inv.var.value.info(),
		binary.fixed.mh	     = binary.fixed.mh.value.info(),
		binary.fixed.peto	 = binary.fixed.peto.value.info(),
		binary.random	     = binary.random.value.info())
    subgroup.disp <- create.subgroup.display(subgroup.results, subgroup.names, params, model.title, data.type="binary")
    forest.path <- paste(params$fp_outpath, sep="")
    subgroup.data <- list("subgroup.list"=subgroup.list, "grouped.data"=grouped.data, "results"=subgroup.results,
                          "col3.nums"=col3.nums, "col3.denoms"=col3.denoms, "col4.nums"=col4.nums, "col4.denoms"=col4.denoms)
    plot.data <- create.subgroup.plot.data.binary(subgroup.data, params)
    changed.params <- plot.data$changed.params
    if (rcmetar.metafor.default.supported(params)) {
        plot.data <- rcmetar.build.subgroup.metafor.bundle(binary.data, params, subgroup.data, plot.data)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    } else {
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    }
    changed.params <- c(changed.params, params.changed.in.forest.plot)
    params <- update.changed.plot.params(params, changed.params)
    forest.plot.params.path <- save.data(binary.data, res, params, plot.data)
    plot.params.paths <- c("Subgroup Forest Plot"=forest.plot.params.path)
    images <- c("Subgroup Forest Plot"=forest.path)
    plot.names <- c("subgroups forest plot"="subgroups_forest_plot")
	references <- c(res$References, subgroup_ma_ref)
    results <- list("images"=images,
			        "Subgroup Summary"=subgroup.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references),
					"res"      = construct.subgroup.res.output(subgroup.results),
					"res.info" = construct.subgroup.value.info(value.info, subgroup.list))
    results
}

get.subgroup.data.binary <- function(binary.data, cov.val, cov.vals) {
  if (!("BinaryData" %in% class(binary.data))) stop("Binary data expected.")
  subset_effects <- binary.data@y[cov.vals == cov.val]
  subset_standard_errors <- binary.data@SE[cov.vals == cov.val]
  subset_study_names <- binary.data@study.names[cov.vals == cov.val]
  subset_years <- binary.data@years[cov.vals == cov.val]
  if (length(binary.data@g1O1) > 0){
    subset_g1O1 <- binary.data@g1O1[cov.vals == cov.val]
    subset_g1O2 <- binary.data@g1O2[cov.vals == cov.val]
    subset_g2O1 <- binary.data@g2O1[cov.vals == cov.val]
    subset_g2O2 <- binary.data@g2O2[cov.vals == cov.val]
    subgroup.data <- new('BinaryData', g1O1=subset_g1O1,
                          g1O2=subset_g1O2, g2O1=subset_g2O1,
                          g2O2=subset_g2O2, y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names,
                          years=subset_years, g1.name=binary.data@g1.name, g2.name=binary.data@g2.name)
  } else {
    subgroup.data <- new('BinaryData', y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names,
                         years=subset_years, g1.name=binary.data@g1.name, g2.name=binary.data@g2.name)
  }
  subgroup.data
}


subgroup.ma.continuous <- function(fname, cont.data, params){
    if (!("ContinuousData" %in% class(cont.data))) stop("Continuous data expected.")
    suppressed_params <- params
    cov.name <- as.character(params$cov_name)
    selected.cov <- get.cov(cont.data, cov.name)
    cov.vals <- selected.cov@cov.vals
	suppressed_params$supress.output <- TRUE
    subgroup.list <- unique(cov.vals)
    grouped.data <- array(list(NULL),c(length(subgroup.list)+1))
    subgroup.results <- array(list(NULL), c(length(subgroup.list)+1))
    col3.nums <- NULL
    col3.denoms <- NULL
    col4.nums <- NULL
    col4.denoms <- NULL
    count <- 1
    for (i in subgroup.list){
      subset_continuous_data <- get.subgroup.data.cont(cont.data, i, cov.vals)
      grouped.data[[count]] <- subset_continuous_data
      current_result <- eval(call(fname, subset_continuous_data, params))
      current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
      subgroup.results[[count]] <- current_overall
      count <- count + 1
    }
    res <- eval(call(fname, cont.data, params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))
    grouped.data[[count]] <- cont.data
    subgroup.results[[count]] <- res.overall
    subgroup.names <- paste("Subgroup ", subgroup.list, sep="")
    subgroup.names <- c(subgroup.names, "Overall")
    metric.name <- pretty.metric.name(as.character(params$measure))
    model.title <- switch(fname,
						  continuous.fixed = paste("Continuous Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
						  continuous.random = paste("Continuous Random-Effects Model\n\nMetric: ", metric.name, sep=""))
    value.info <- switch(fname,
						 continuous.fixed  = continuous.fixed.value.info(),
						 continuous.random = continuous.random.value.info())
    subgroup.disp <- create.overall.display(subgroup.results, subgroup.names, params, model.title, data.type="continuous")
    forest.path <- paste(params$fp_outpath, sep="")
    subgroup.data <- list("subgroup.list"=subgroup.list, "grouped.data"=grouped.data, "results"=subgroup.results,
                          "col3.nums"=col3.nums, "col3.denoms"=col3.denoms, "col4.nums"=col4.nums, "col4.denoms"=col4.denoms)
    plot.data <- create.subgroup.plot.data.cont(subgroup.data, params)
    changed.params <- plot.data$changed.params
    if (rcmetar.metafor.default.supported(params)) {
        plot.data <- rcmetar.build.subgroup.metafor.bundle(cont.data, params, subgroup.data, plot.data)
        changed.params <- plot.data$changed.params
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    } else {
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
    }
    changed.params <- c(changed.params, params.changed.in.forest.plot)
    params <- update.changed.plot.params(params, changed.params)
    forest.plot.params.path <- save.data(cont.data, res, params, plot.data)
    plot.params.paths <- c("Subgroups Forest Plot"=forest.plot.params.path)
    images <- c("Subgroups Forest Plot"=forest.path)
    plot.names <- c("subgroups forest plot"="subgroups_forest_plot")

	references <- c(res$References, subgroup_ma_ref)

    results <- list("images"=images,
			        "Subgroup Summary"=subgroup.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths,
					"References"=rcmetar.unique.references(references),
					"res"      = construct.subgroup.res.output(subgroup.results),
					"res.info" = construct.subgroup.value.info(value.info, subgroup.list))
    results
}

get.subgroup.data.cont <- function(cont.data, cov.val, cov.vals) {
  if (!("ContinuousData" %in% class(cont.data))) stop("Continuous data expected.")
      subset_effects <- cont.data@y[cov.vals == cov.val]
      subset_standard_errors <- cont.data@SE[cov.vals == cov.val]
      subset_study_names <- cont.data@study.names[cov.vals == cov.val]
      subset_years <- cont.data@years[cov.vals == cov.val]
  if (length(cont.data@N1) > 0){
      subset_N1 <- cont.data@N1[cov.vals == cov.val]
      subset_mean1 <- cont.data@mean1[cov.vals == cov.val]
      subset_sd1 <- cont.data@sd1[cov.vals == cov.val]
      subset_N2 <- cont.data@N2[cov.vals == cov.val]
      subset_mean2 <- cont.data@mean2[cov.vals == cov.val]
      subset_sd2 <- cont.data@sd2[cov.vals == cov.val]
      subgroup.data <- new('ContinuousData',
                          N1=subset_N1, mean1=subset_mean1 , sd1=subset_sd1,
                          N2=subset_N2, mean2=subset_mean2, sd2=subset_sd2,
                          y=subset_effects, SE=subset_standard_errors,
                          study.names=subset_study_names, years=subset_years,
                          g1.name=cont.data@g1.name, g2.name=cont.data@g2.name)
    } else {
    subgroup.data <- new('ContinuousData',
                          y=subset_effects, SE=subset_standard_errors,
                          study.names=subset_study_names, years=subset_years,
                          g1.name=cont.data@g1.name, g2.name=cont.data@g2.name)
    }
    subgroup.data
}

get.cov <- function(om.data, cov.name) {
    covariate <- NULL
    count <- 1
    while ((count <= length(om.data@covariates)) & (is.null(covariate))) {
        if (om.data@covariates[[count]]@cov.name == cov.name) {
            covariate <- om.data@covariates[[count]]
        }
        count <- count + 1
    }
    covariate
}

update.plot.data.multiple <- function(binary.data, params, results) {

    scale.str <- "standard"
    if (metric.is.log.scale(as.character(params$measure))){
        scale.str <- "log"
    }
    transform.name <- "binary.transform.f"
    data.type <- "binary"
    plot.options <- extract.plot.options(params)
    if (!is.null(params$fp_display.lb)) {
        plot.options$display.lb <- eval(call(transform.name, params$measure))$calc.scale(params$fp_display.lb)
    }
    if (!is.null(params$fp_display.ub)) {
        plot.options$display.ub <- eval(call(transform.name, params$measure))$calc.scale(params$fp_display.ub)
    }
    if (!is.null(params$fp_show.summary.line)) {
        plot.options$show.summary.line <- params$fp_show_summary_line
    } else {
        plot.options$show.summary.line <- TRUE
    }
    plot.data <- list(label = c(rcmetar.forest.study.header.label(params$fp_col1_str), binary.data@study.names, "Overall"),
                    types = c(3, rep(0, length(binary.data@study.names)), 2),
                    scale = scale.str,
                    data.type = data.type,
                    overall =FALSE,
                    options = plot.options)
    mult <- get.mult.from.conf.level(params$conf.level)
    y.overall <- res$b[1]
    lb.overall <- res$ci.lb[1]
    ub.overall <- res$ci.ub[1]
     y <- binary.data@y
    lb <- y - mult*binary.data@SE
    ub <- y + mult*binary.data@SE

    y <- c(y, y.overall)
    lb <- c(lb, lb.overall)
    ub <- c(ub, ub.overall)

    y.disp <- eval(call(transform.name, params$measure))$display.scale(y)
    lb.disp <- eval(call(transform.name, params$measure))$display.scale(lb)
    ub.disp <- eval(call(transform.name, params$measure))$display.scale(ub)

    if (params$fp_show_col2=='TRUE') {
        effect.size.col <- format.effect.size.col(y.disp, lb.disp, ub.disp, params)
        plot.data$additional.col.data$es <- effect.size.col
    }
    if (scale.str == "log") {
        effects <- list(ES = y,
                    LL = lb,
                    UL = ub)
    } else {
        effects <- list(ES = y.disp,
                    LL = lb.disp,
                    UL = ub.disp)
    }
    plot.data$effects <- effects
    if (!is.null(selected.cov)){
        cov.val.str <- paste("binary.data@covariates$", selected.cov, sep="")
        cov.values <- eval(parse(text=cov.val.str))
        plot.data$covariate <- list(varname = selected.cov,
                                   values = cov.values)
    }
    plot.data$fp_xlabel <- paste(params$fp_xlabel, sep = "")
    plot.data$fp_xticks <- params$fp_xticks
    plot.data
}

multiple.loo.diagnostic <- function(fnames, params.list, diagnostic.data) {


    results <- list()
    pretty.names <- diagnostic.fixed.inv.var.pretty.names()
	references <- c()

    images <- c()
    plot.names <- c()
    plot.params.paths <- c()



    if (length(params.list) > 0) {
        for (count in 1:length(params.list)) {
            subset_diagnostic_data <- compute.diag.point.estimates(diagnostic.data, params.list[[count]])
            analysis_result <- loo.ma.diagnostic(fnames[[count]], subset_diagnostic_data, params.list[[count]])
            analysis_images <- analysis_result$images
            names(analysis_images) <- paste(eval(parse(text=paste("pretty.names$measure$",params.list[[count]]$measure,sep=""))), " Forest Plot", sep="")
            images <- c(images, analysis_images)
            analysis_plot_paths <- analysis_result$plot_params_paths
            names(analysis_plot_paths) <- paste(eval(parse(text=paste("pretty.names$measure$", params.list[[count]]$measure,sep=""))), " Forest Plot", sep="")
            plot.params.paths <- c(plot.params.paths, analysis_plot_paths)
            plot.names <- c(plot.names, analysis_result$plot.names)
            analysis_summary <- list("Summary"=analysis_result$Summary)
            names(analysis_summary) <- paste(eval(parse(text=paste("pretty.names$measure$",params.list[[count]]$measure,sep=""))), " Summary", sep="")

			references <- c(references, analysis_result$References)

			results <- c(results, analysis_summary)
        }
    }
    results <- c(results, list("images"=images,
					           "plot_names"=plot.names,
                               "plot_params_paths"=plot.params.paths,
							   "References"=rcmetar.unique.references(references)))
    results
}

loo.ma.diagnostic <- function(fname, diagnostic.data, params){
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
    loo.results <- array(list(NULL), dim=c(length(diagnostic.data@study.names)))
    suppressed_params <- params
    suppressed_params$create.plot <- FALSE
    suppressed_params$write.to.file <- FALSE
    res <- eval(call(fname, diagnostic.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))
    N <- length(diagnostic.data@study.names)
    for (i in 1:N){
        index.ls <- setdiff(1:N, i)

        subset_effects <- diagnostic.data@y[index.ls]
        subset_standard_errors <- diagnostic.data@SE[index.ls]
        subset_study_names <- diagnostic.data@study.names[index.ls]
        subset_diagnostic_data <- NULL

        if (length(diagnostic.data@TP) > 0){
            subset_TP <- diagnostic.data@TP[index.ls]
            subset_FN <- diagnostic.data@FN[index.ls]
            subset_TN <- diagnostic.data@TN[index.ls]
            subset_FP <- diagnostic.data@FP[index.ls]
            subset_diagnostic_data <- new('DiagnosticData', TP=subset_TP,
                               FN=subset_FN , TN=subset_TN,
                               FP=subset_FP, y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
        } else{
            subset_diagnostic_data <- new('DiagnosticData', y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names)
        }
        current_result <- eval(call(fname, subset_diagnostic_data, suppressed_params))
        current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
        loo.results[[i]] <- current_overall
    }
    loo.results <- c(list(res.overall), loo.results)
    study.names <- c("Overall", paste("- ", diagnostic.data@study.names, sep=""))
    metric.name <- pretty.metric.name(as.character(params$measure))
	model.title <- switch(fname,
			diagnostic.fixed = paste("Diagnostic Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
			diagnostic.random = paste("Diagnostic Random-Effects Model\n\nMetric: ", metric.name, sep=""))
    loo.disp <- create.overall.display(res=loo.results, study.names, params, model.title, data.type="diagnostic")

    if (!identical(params$create.plot, FALSE)) {
        plot.data <- create.plot.data.loo(diagnostic.data, params, res=loo.results)
        forest.path <- paste(params$fp_outpath, sep="")
        changed.params <- plot.data$changed.params
        if (rcmetar.metafor.default.supported(params)) {
            plot.data <- rcmetar.build.sequential.metafor.bundle(diagnostic.data, params, loo.results, "leave-one-out", study.names, plot.data)
            changed.params <- plot.data$changed.params
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
        } else {
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
        }
        changed.params <- c(changed.params, params.changed.in.forest.plot)
        params <- update.changed.plot.params(params, changed.params)
        forest.plot.params.path <- save.data(diagnostic.data, res=loo.results, params, plot.data)
        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Leave-one-out Forest plot"=forest.path)
        plot.names <- c("loo forest plot"="loo_forest_plot")
        results <- list("images"=images, "Summary"=loo.disp,
                        "plot_names"=plot.names,
                        "plot_params_paths"=plot.params.paths)
    } else {
        results <- list(res=loo.results, res.overall=res.overall, Summary=loo.disp)
    }

	references <- c(res$References, loo_ma_ref)
	results[["References"]] <- rcmetar.unique.references(references)
    results
}


multiple.subgroup.diagnostic <- function(fnames, params.list, diagnostic.data) {


    results <- list()
    pretty.names <- diagnostic.fixed.inv.var.pretty.names()
    cov.name <- as.character(params.list[[1]]$cov_name)
    selected.cov <- get.cov(diagnostic.data, cov.name)
    images <- c()
    plot.names <- c()
    plot.params.paths <- c()
	references <- c()



    if (length(params.list) > 0) {
        for (count in 1:length(params.list)) {
            subset_diagnostic_data <- compute.diag.point.estimates(diagnostic.data, params.list[[count]])
            analysis_result <- subgroup.ma.diagnostic(fnames[[count]], subset_diagnostic_data, params.list[[count]], selected.cov)
            if (is.null(params.list[[count]]$create.plot)) {
                analysis_images <- analysis_result$images
                names(analysis_images) <- paste(eval(parse(text=paste("pretty.names$measure$",params.list[[count]]$measure,sep=""))), " Forest Plot", sep="")
                images <- c(images, analysis_images)
                analysis_plot_paths <- analysis_result$plot_params_paths
                names(analysis_plot_paths) <- paste(eval(parse(text=paste("pretty.names$measure$", params.list[[count]]$measure,sep=""))), " Forest Plot", sep="")
                plot.params.paths <- c(plot.params.paths, analysis_plot_paths)
                plot.names <- c(plot.names, analysis_result$plot_names)
            }
            analysis_summary <- list("Summary"=analysis_result$Summary)
            names(analysis_summary) <- paste(eval(parse(text=paste("pretty.names$measure$",params.list[[count]]$measure,sep=""))), " Summary", sep="")

			references <- c(references, analysis_result$References)

			results <- c(results, analysis_summary)
        }
    }
    results <- c(results, list("images"=images,
					           "plot_names"=plot.names,
                               "plot_params_paths"=plot.params.paths,
							   "References"=rcmetar.unique.references(references)))
    results
}

subgroup.ma.diagnostic <- function(fname, diagnostic.data, params, selected.cov){
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
    cov.vals <- selected.cov@cov.vals
    suppressed_params <- params
    suppressed_params$create.plot <- FALSE
    suppressed_params$write.to.file <- FALSE
    subgroup.list <- unique(cov.vals)
    grouped.data <- array(list(NULL),c(length(subgroup.list) + 1))
    subgroup.results <- array(list(NULL), c(length(subgroup.list) + 1))
    col3.nums <- NULL
    col3.denoms <- NULL
    col4.nums <- NULL
    col4.denoms <- NULL
    count <- 1
    for (i in subgroup.list){
      subset_diagnostic_data <- get.subgroup.data.diagnostic(diagnostic.data, i, cov.vals)
      grouped.data[[count]] <- subset_diagnostic_data
      raw.data <- list("TP"=subset_diagnostic_data@TP, "FN"=subset_diagnostic_data@FN, "TN"=subset_diagnostic_data@TN, "FP"=subset_diagnostic_data@FP)
      terms <- compute.diagnostic.terms(raw.data, suppressed_params)
      col3.nums <- c(col3.nums, terms$numerator, sum(terms$numerator))
      col3.denoms <- c(col3.denoms, terms$denominator, sum(terms$denominator))
      current_result <- eval(call(fname, subset_diagnostic_data, suppressed_params))
      current_overall <- eval(call(paste(fname, ".overall", sep=""), current_result))
      subgroup.results[[count]] <- current_overall
      count <- count + 1
    }
    res <- eval(call(fname, diagnostic.data, suppressed_params))
    res.overall <- eval(call(paste(fname, ".overall", sep=""), res))
    grouped.data[[count]] <- diagnostic.data
    subgroup.results[[count]] <- res.overall
    subgroup.names <- paste("Subgroup ", subgroup.list, sep="")
    subgroup.names <- c(subgroup.names, "Overall")

    metric.name <- pretty.metric.name(suppressed_params$measure)
    model.title <- switch(fname,
                          diagnostic.fixed = paste("Diagnostic Fixed-Effect Model - Inverse Variance\n\nMetric: ", metric.name, sep=""),
                          diagnostic.random = paste("Diagnostic Random-Effects Model\n\nMetric: ", metric.name, sep=""))
    subgroup.disp <- create.subgroup.display(subgroup.results, subgroup.names, params, model.title, data.type="diagnostic")
    forest.path <- paste(params$fp_outpath, sep="")
    subgroup.data <- list("subgroup.list"=subgroup.list, "grouped.data"=grouped.data, "results"=subgroup.results,
                          "col3.nums"=col3.nums, "col3.denoms"=col3.denoms, "col4.nums"=col4.nums, "col4.denoms"=col4.denoms)
    if (is.null(params$create.plot)) {
        plot.data <- create.subgroup.plot.data.diagnostic(subgroup.data, params)
        changed.params <- plot.data$changed.params
        if (rcmetar.metafor.default.supported(params)) {
            plot.data <- rcmetar.build.subgroup.metafor.bundle(diagnostic.data, params, subgroup.data, plot.data)
            changed.params <- plot.data$changed.params
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
        } else {
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
        }
        changed.params <- c(changed.params, params.changed.in.forest.plot)
        params <- update.changed.plot.params(params, changed.params)
        forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)
        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Subgroups Forest Plot"=forest.path)
        plot.names <- c("subgroups forest plot"="subgroups_forest_plot")
        results <- list("images"=images, "Summary"=subgroup.disp,
                    "plot_names"=plot.names,
                    "plot_params_paths"=plot.params.paths)
    } else {
        results <- list(subgroup.data=subgroup.data, Summary=subgroup.disp, "cov.list"=subgroup.list)
    }

	references <- c(res$References, subgroup_ma_ref)
	results[["References"]] <- rcmetar.unique.references(references)

    results
}

get.subgroup.data.diagnostic <- function(diagnostic.data, cov.val, cov.vals) {
  if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
  subset_effects <- diagnostic.data@y[cov.vals == cov.val]
  subset_standard_errors <- diagnostic.data@SE[cov.vals == cov.val]
  subset_study_names <- diagnostic.data@study.names[cov.vals == cov.val]
  subset_years <- diagnostic.data@years[cov.vals == cov.val]
  if (length(diagnostic.data@TP) > 0){
    subset_TP <- diagnostic.data@TP[cov.vals==cov.val]
    subset_FN <- diagnostic.data@FN[cov.vals==cov.val]
    subset_TN <- diagnostic.data@TN[cov.vals==cov.val]
    subset_FP <- diagnostic.data@FP[cov.vals==cov.val]
    subgroup.data <- new('DiagnosticData', TP=subset_TP,
                          FN=subset_FN , TN=subset_TN,
                          FP=subset_FP, y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names,
                          years=subset_years)
  } else {
    subgroup.data <- new('DiagnosticData', y=subset_effects, SE=subset_standard_errors, study.names=subset_study_names,
                         years=subset_years)
  }
  subgroup.data
}
