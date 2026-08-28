# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

#######################################
# RC MetaStudio                   #
# ----                                #
# diagnostic_methods.R                #
# Facade module; wraps methods        #
# that perform analysis on diagnostic #
# data in a coherent interface.       # 
#######################################

diagnostic.logit.metrics <- c("Sens", "Spec", "PPV", "NPV", "Acc")
diagnostic.log.metrics <- c("PLR", "NLR", "DOR")
bivariate.methods <- c("diagnostic.hsroc", "diagnostic.bivariate.ml")

adjust.raw.data <- function(diagnostic.data, params) {
    # adjust raw data by adding a constant to each entry   
    TP <- diagnostic.data@TP
    FN <- diagnostic.data@FN  
    TN <- diagnostic.data@TN 
    FP <- diagnostic.data@FP
    
    if ("to" %in% names(params)) {
        if (params$to == "all") {
            TP <- TP + params$adjust
            FN <- FN + params$adjust
            TN <- TN + params$adjust
            FP <- FP + params$adjust
        } else if (params$to == "only0") {
            product <- TP * FN * TN * FP
            # product equals 0 if at least one entry in a row is 0
            TP[product == 0] <- TP[product == 0] + params$adjust
            FN[product == 0] <- FN[product == 0] + params$adjust
            TN[product == 0] <- TN[product == 0] + params$adjust
            FP[product == 0] <- FP[product == 0] + params$adjust
        } else if (params$to == "if0all") {
            if (any(c(TP,FN,TN,FP) == 0)) {
                TP <- TP + params$adjust
                FN <- FN + params$adjust
                TN <- TN + params$adjust
                FP <- FP + params$adjust    
            }
        }
    }

    data.adj <- list("TP"=TP, "FN"=FN, "TN"=TN, "FP"=FP)
}

compute.diag.point.estimates <- function(diagnostic.data, params) {
    # Computes point estimates based on raw data and adds them to diagnostic.data
    if (length(diagnostic.data@TP) == 0) {
        if (length(diagnostic.data@y) > 0 && length(diagnostic.data@SE) > 0) {
            return(diagnostic.data)
        }
        stop("Diagnostic point estimates require either TP/FN/TN/FP counts or entered effect estimates and standard errors.")
    }

    data.adj <- adjust.raw.data(diagnostic.data, params)
    terms <- compute.diagnostic.terms(raw.data=data.adj, params)
    metric <- params$measure    
    TP <- data.adj$TP
    FN <- data.adj$FN  
    TN <- data.adj$TN 
    FP <- data.adj$FP
    
    y <- terms$numerator / terms$denominator
      
    diagnostic.data@y <- eval(call("diagnostic.transform.f", params$measure))$calc.scale(y, n)
 
	# logit scale SE
    diagnostic.data@SE <- switch(metric,
        Sens = sqrt((1 / TP) + (1 / FN)), 
        Spec = sqrt((1 / TN) + (1 / FP)),
        PPV = sqrt((1 / TP) + (1 / FP)),
        NPV = sqrt((1 / TN) + (1 / FN)),
        Acc = sqrt((1 / (TP + TN)) + (1 / (FP + FN))),
        PLR = sqrt((1 / TP) - (1 / (TP + FN)) + (1 / FP) - (1 / (TN + FP))),
        NLR = sqrt((1 / TP) - (1 / (TP + FN)) + (1 / FP) - (1 / (TN + FP))),
        DOR = sqrt((1 / TP) + (1 / FN) + (1 / FP) + (1 / TN)))
	# display scale SE


    diagnostic.data
}

compute.diagnostic.terms <- function(raw.data, params) { 
    # compute numerator and denominator of diagnostic point estimate.
    metric <- params$measure
    TP <- raw.data$TP
    FN <- raw.data$FN  
    TN <- raw.data$TN 
    FP <- raw.data$FP
    numerator <- switch(metric,
        # sensitivity
        Sens = TP, 
        # specificity
        Spec = TN,
        # pos. predictive value
        PPV =  TP,
        #neg. predictive value
        NPV =  TN,
        # accuracy
        Acc = TP + TN,
        # positive likelihood ratio
        PLR = TP * (TN + FP), 
        # negative likelihood ratio
        NLR = FN * (TN + FP),
        # diagnostic odds ratio
        DOR = TP * TN)
        
    denominator <- switch(metric,
        # sensitivity
        Sens = TP + FN, 
        # specificity
        Spec = TN + FP,
        # pos. predictive value
        PPV =  TP + FP,
        #neg. predictive value
        NPV =  TN + FN,
        # accuracy
        Acc = TP + TN + FP + FN,
        # positive likelihood ratio
        PLR = FP * (TP + FN), 
        # negative likelihood ratio
        NLR = TN * (TP + FN),
        # diagnostic odds ratio
        DOR = FP * FN)  

    terms <- list("numerator"=numerator, "denominator"=denominator)      
}

diagnostic.transform.f <- function(metric.str){
    display.scale <- function(x, ...){
        if (metric.str %in% diagnostic.log.metrics){
            exp(x)
        } else if (metric.str %in% diagnostic.logit.metrics) {
            invlogit(x)
        } else {
            # identity function
            x
        }
    }
    
    calc.scale <- function(x, ...){
        if (metric.str %in% diagnostic.log.metrics){
            log(x)
        } else if (metric.str %in% diagnostic.logit.metrics){
            logit(x)
        } else {
            # identity function
            x
        }
    }
    list(display.scale = display.scale, calc.scale = calc.scale)
}

get.res.for.one.diag.study <- function(diagnostic.data, params){
    # this method can be called when there is only one study to 
    # get the point estimate and lower/upper bounds.
    
    ######
    ## Do not check here if the object is NA; we want to recompute the 
    ## data here regardless, and the program will throwup on this check if 
    ## the y estimate doesn't exist on the object.
    #####
    diagnostic.data <- compute.diag.point.estimates(diagnostic.data, params)
    
    y <- diagnostic.data@y
    se <- diagnostic.data@SE

    # note: conf.level is given as, e.g., 95, rather than .95.
    mult <- get.mult.from.conf.level(params$conf.level)
    ub <- y + mult*se
    lb <- y - mult*se
    # we make lists to comply with the get.overall method
    res <- list("b"=c(y), "ci.lb"=lb, "ci.ub"=ub, "se"=se) 
    res
}

###################################################
#     multiple diagnostic methods                 #
###################################################
multiple.diagnostic <- function(fnames, params.list, diagnostic.data) {

    # wrapper for applying multiple diagnostic functions and metrics    

    ####
    # fnames -- names of diagnostic meta-analytic functions to call
    # params.list -- parameter lists to be passed along to the functions in
    #              fnames
    # diagnostic.data -- the (diagnostic data) that is to be analyzed 
    ###
    metrics <- c()
    results <- list()
    pretty.names <- diagnostic.fixed.inv.var.pretty.names()
    sens.spec.outpath <- c()
    for (count in 1:length(params.list)) {
        metrics <- c(metrics, params.list[[count]]$measure)
        if (params.list[[count]]$measure=="Sens") {
            sens.index <- count
        }
        if (params.list[[count]]$measure=="Spec") {
            spec.index <- count
        }
        if (params.list[[count]]$measure=="PLR") {
            plr.index <- count
        }
        if (params.list[[count]]$measure=="NLR") {
            nlr.index <- count
        }
    }
    
    images <- c()
    image.order <- c()
    plot.names <- c()
    plot.params.paths <- c()
    plot.capabilities <- list()
    plot.pdfs.paths <- c() # sometimes we want to just output pdfs at run-time
    remove.indices <- c()
	references <- c()

    if (("Sens" %in% metrics) & ("Spec" %in% metrics)) {
        ####
        # we are running an analysis for sens *and* spec;
        # has a bivariate method been selected??
        fname <- fnames[sens.index]
        if (fname %in% bivariate.methods){
            params.sens <- params.list[[sens.index]] # we could pick either here
            biv.results <- eval(call(fname, diagnostic.data, params.sens))
            results <- c(results, biv.results$Summary)
            images <- c(images, biv.results$images)
            plot.capabilities <- c(plot.capabilities, biv.results$plot_capabilities)
            image.order <- append.image.order(image.order, biv.results)
            remove.indices <- c(sens.index, spec.index)
			references <- c(references, biv.results$References)
        } else {
            # Non-bivariate sensitivity and specificity are rendered by the
            # ordinary per-metric loop below. Keep the shared SROC artifact.
            params.sens <- params.list[[sens.index]]
            # create SROC plot
            sroc.path <- rcmetar.scratch.path("roc.png")
            sroc.plot.data <- create.sroc.plot.data(diagnostic.data, params=params.sens)
            sroc.plot(sroc.plot.data, sroc.path)
            # we use the system time as our unique-enough string to store
            # the params object
            sroc.plot.params.path <- save.plot.data(sroc.plot.data)
            plot.params.paths.tmp <- c("SROC"=sroc.plot.params.path)
            plot.params.paths <- c(plot.params.paths, plot.params.paths.tmp)
            images <- c(images, c("SROC"=sroc.path))
            plot.capabilities[["SROC"]] <- .rcmetar.plot.descriptor.for.kind("sroc", has.params=TRUE)
            image.order <- c(image.order, "SROC")
            plot.names <- c(plot.names, c("sroc"="sroc"))
        }
    }

    # Bivariate sensitivity/specificity is the only paired analysis result.
    fnames <- fnames[setdiff(1:length(fnames), remove.indices)]
    params.list <- params.list[setdiff(1:length(params.list), remove.indices)]
	
	

    if (length(params.list) > 0) {
        for (count in 1:length(params.list)) {
            # create ma summaries and single (not side-by-side) forest plots.
            #pretty.names <- eval(call(paste(fnames[count],".pretty.names",sep="")))
            diagnostic.data.tmp <- compute.diag.point.estimates(diagnostic.data, params.list[[count]])
            results.tmp <- eval(call(fnames[count], diagnostic.data.tmp, params.list[[count]]))
            images.tmp <- results.tmp$images
            names(images.tmp) <- paste(eval(parse(text=paste("pretty.names$measure$",params.list[[count]]$measure,sep=""))), " Forest Plot", sep="")
            images <- c(images, images.tmp)
            plot.capabilities[[names(images.tmp)[[1]]]] <- .rcmetar.plot.descriptor.for.kind(
                "forest",
                has.params=length(results.tmp$plot_params_paths) > 0
            )
            image.order <- c(image.order, names(images.tmp))
            plot.params.paths.tmp <- results.tmp$plot_params_paths
            names(plot.params.paths.tmp) <- paste(eval(parse(text=paste("pretty.names$measure$", params.list[[count]]$measure,sep=""))), " Forest Plot", sep="")
            plot.params.paths <- c(plot.params.paths, plot.params.paths.tmp)
            plot.names <- c(plot.names, results.tmp$plot_names)
            summary.tmp <- list("Summary"=results.tmp$Summary)
            names(summary.tmp) <- paste(eval(parse(text=paste("pretty.names$measure$",params.list[[count]]$measure,sep=""))), " Summary", sep="")
      
		    references <- c(references, results.tmp$References)
			results <- c(results, summary.tmp)
        }
    }

    graphics.off()
    results <- c(results, list("images"=images,
					           "image_order"=image.order,
                               "plot_names"=plot.names,
                               "plot_params_paths"=plot.params.paths,
                               "plot_capabilities"=plot.capabilities,
							   "References"=rcmetar.unique.references(references)))
    results
}

append.image.order <- function(image.order, results){
    if ("image_order" %in% names(results)){
        image.order <- c(image.order, results[["image_order"]])
    } else{
        # just keep the current order
        image.order <- c(image.order, names(results$images))
    }
    image.order
}

###################################################
#            diagnostic fixed effects             #
###################################################
diagnostic.fixed.inv.var <- function(diagnostic.data, params){
    # assert that the argument is the correct type
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
    results <- NULL
    inference.method <- rcmetar.validate.inference.method(params, length(diagnostic.data@y))
    if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
        res <- get.res.for.one.diag.study(diagnostic.data, params)
        # Package res for use by overall method.
        summary.disp <- list("MAResults" = res) 
        results <- list("Summary"=summary.disp)
    } else {
         # call out to the metafor package
        res<-rma.uni(yi=diagnostic.data@y, sei=diagnostic.data@SE, 
                     slab=diagnostic.data@study.names,
                     method="FE", test=inference.method, level=params$conf.level,
                     digits=params$digits)
		# GD EXPERIMENTAL#########################
		res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
		res$study.names <- diagnostic.data@study.names
		res$study.years <- diagnostic.data@years
		#########################################
        # Create list to display summary of results
        model.title <- paste("Diagnostic Fixed-Effect Model - Inverse Variance (k = ", res$k, ")", sep="")
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        pretty.names <- diagnostic.fixed.inv.var.pretty.names()
        pretty.metric <- eval(parse(text=paste("pretty.names$measure$", params$measure,sep="")))
        for (count in 1:length(summary.disp$table.titles)) {
          summary.disp$table.titles[count] <- paste(" ", pretty.metric, " -", summary.disp$table.titles[count], sep="")
        }
        # Write results to csv file
        if ((is.null(params$write.to.file)) || params$write.to.file == TRUE) {
            results.path <- paste("./r_tmp/diag_fixed_inv_var_", params$measure, "_results.csv", sep="")
            # Keep the default path here unless callers pass an override in params.
            write.results.to.file(diagnostic.data, params, res, outpath=results.path) 
        }
        if ((is.null(params$create.plot)) || params$create.plot == TRUE) {
            # A forest plot will be created unless
            # params.create.plot is set to FALSE.
            forest.path <- paste(params$fp_outpath, sep="")
            plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
            changed.params <- plot.data$changed.params
            # list of changed params values
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            # dump the forest plot params to disk; return path to
            # this .Rdata for later use
            forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)

            plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
            images <- c("Forest Plot"=forest.path)
            plot.names <- c("forest plot"="forest_plot")

			
            results <- list("images"=images,
					        "Summary"=summary.disp,
                            "plot_names"=plot.names, 
                            "plot_params_paths"=plot.params.paths)
        } else {
            results <- list("Summary"=summary.disp)
        } 
    }
	
	references <- rcmetar.unique.references(c(
        rcmetar.method.references("rma.uni.fixed"),
        rcmetar.inference.method.references(params)))
	results[["References"]] <- references
	
    results
}

diagnostic.fixed.inv.var.parameters <- function(){
    # parameters
    apply_adjustment_to = c("only0", "all")

    params <- list("inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply_adjustment_to)

    # default values
    defaults <- list("inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")

    var_order = c("inference.method", "conf.level", "digits", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

diagnostic.fixed.inv.var.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Diagnostic Fixed-Effect Inverse Variance", 
                         "description" = "Performs fixed-effect meta-analysis with inverse variance weighting.",
                         "inference.method"=rcmetar.inference.method.metadata(),
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"), 
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero."),
                         "measure"=list("Sens"="Sensitivity", "Spec"="Specificity", "DOR"="Odds Ratio", "PLR"="Positive Likelihood Ratio",
                                        "NLR"="Negative Likelihood Ratio")           
                          )
}

diagnostic.fixed.inv.var.is.feasible <- function(diagnostic.data, metric){
    metric %in% c("Sens", "Spec", "PLR", "NLR", "DOR")
}

diagnostic.fixed.inv.var.overall <- function(results) {
    # this parses out the overall from the computed result
    res <- results$Summary$MAResults
}

################################################
#  diagnostic fixed effects -- mantel haenszel #
################################################
diagnostic.fixed.mh <- function(diagnostic.data, params){
    # assert that the argument is the correct type
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")  
    results <- NULL
    if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
        res <- get.res.for.one.diag.study(diagnostic.data, params)
         # Package res for use by overall method.
        summary.disp <- list("MAResults" = res) 
        results <- list("Summary"=summary.disp)
    } 
    else {
        res <- switch(params$measure,

            "DOR" = rma.mh(ai=diagnostic.data@TP, bi=diagnostic.data@FN, 
                                ci=diagnostic.data@FP, di=diagnostic.data@TN, slab=diagnostic.data@study.names,
                                level=params$conf.level, digits=params$digits, measure="OR",
                                add=c(params$adjust, 0), to=c(as.character(params$to), "none")),
                                
            "PLR" = rma.mh(ai=diagnostic.data@TP, bi=diagnostic.data@FN, 
                                ci=diagnostic.data@FP, di=diagnostic.data@TN, slab=diagnostic.data@study.names,
                                level=params$conf.level, digits=params$digits, measure="RR",
                                add=c(params$adjust, 0), to=c(as.character(params$to), "none")),
        
                      # For "NLR", switch ai with bi, and ci with di
                      # Required by rma.mh when measure is "RR".
            "NLR" = rma.mh(ai=diagnostic.data@FN, bi=diagnostic.data@TP, 
                                ci=diagnostic.data@TN, di=diagnostic.data@FP, slab=diagnostic.data@study.names,
                                level=params$conf.level, digits=params$digits, measure="RR",
                                add=c(params$adjust, 0), to=c(as.character(params$to), "none")))
         
		# GD EXPERIMENTAL#########################
		res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
		res$study.names <- diagnostic.data@study.names
		res$study.years <- diagnostic.data@years
		#########################################		
        #                        
        # Create list to display summary of results
        #
        model.title <- "Diagnostic Fixed-Effect Model - Mantel-Haenszel"
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        pretty.names <- diagnostic.fixed.mh.pretty.names()
        pretty.metric <- eval(parse(text=paste("pretty.names$measure$", params$measure,sep="")))
        for (count in 1:length(summary.disp$table.titles)) {
          summary.disp$table.titles[count] <- paste(" ", pretty.metric, " -", summary.disp$table.titles[count], sep="")
        }
        # Write results to csv file
        if ((is.null(params$write.to.file)) || params$write.to.file == TRUE) {
            results.path <- paste("./r_tmp/diag_fixed_mh_", params$measure, "_results.csv", sep="")
            # Keep the default path here unless callers pass an override in params.
            write.results.to.file(diagnostic.data, params, res, outpath=results.path) 
        }
        #
        # generate forest plot
        #
        if ((is.null(params$create.plot)) || (params$create.plot == TRUE)) {
            if (is.null(diagnostic.data@y) || is.null(diagnostic.data@SE)) {
                diagnostic.data <- compute.diag.point.estimates(diagnostic.data, params)
                # compute point estimates for plot.data in case they are missing
            }
            forest.path <- paste(params$fp_outpath, sep="")
            plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
            changed.params <- plot.data$changed.params
            # list of changed params values
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            # dump the forest plot params to disk; return path to
            # this .Rdata for later use
            forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)
            
            plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
            images <- c("Forest Plot"=forest.path)
            plot.names <- c("forest plot"="forest_plot")
            results <- list("images"=images,
					        "Summary"=summary.disp,
                            "plot_names"=plot.names, 
                            "plot_params_paths"=plot.params.paths)
        }
        else {
            results <- list("Summary"=summary.disp)
        }    
    }
	
	references <- rcmetar.method.references("rma.mh")
	results[["References"]] <- references
	
    results
}
                                
diagnostic.fixed.mh.parameters <- function(){
    # parameters
    apply_adjustment_to = c("only0", "all")
    
    params <- list("conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply_adjustment_to)
    
    # default values
    defaults <- list("conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")
    
    var_order = c("conf.level", "digits", "adjust", "to")
    
    # constraints
    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

diagnostic.fixed.mh.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Diagnostic Fixed-Effect Mantel-Haenszel", 
                         "description" = "Performs fixed-effect meta-analysis using the Mantel-Haenszel method.",
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"), 
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero."),
                          "measure"=list("Sens"="Sensitivity", "Spec"="Specificity", "DOR"="Odds Ratio", "PLR"="Positive Likelihood Ratio",
                                        "NLR"="Negative Likelihood Ratio")
                          )
}

diagnostic.fixed.mh.is.feasible <- function(diagnostic.data, metric){
    metric %in% c("DOR", "PLR", "NLR")
}

diagnostic.fixed.mh.overall <- function(results) {
    # this parses out the overall from the computed result
    res <- results$Summary$MAResults
}

##################################################
#       diagnostic fixed effects -- Peto             #
##################################################
diagnostic.fixed.peto <- function(diagnostic.data, params){
  # assert that the argument is the correct type
  if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.") 
  
  if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
    res <- get.res.for.one.diag.study(diagnostic.data, params)
    # Package res for use by overall method.
    summary.disp <- list("MAResults" = res) 
    results <- list("Summary"=summary.disp)
  }
  else{  
    res <- rma.peto(ai=diagnostic.data@TP, bi=diagnostic.data@FN, 
                    ci=diagnostic.data@FP, di=diagnostic.data@TN,
					slab=diagnostic.data@study.names,
                    level=params$conf.level,
					digits=params$digits,
                    add=c(params$adjust, 0),
					to=c(as.character(params$to), "none"))
	# GD EXPERIMENTAL#########################
	res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
	res$study.names <- diagnostic.data@study.names
	res$study.years <- diagnostic.data@years
	#########################################			
			
    # Corrected values for y and SE
    diagnostic.data@y <- res$yi
    diagnostic.data@SE <- sqrt(res$vi)
    
    #                        
    # Create list to display summary of results
    #
    model.title <- "Diagnostic Fixed-Effect Model - Peto"
    summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
    pretty.names <- diagnostic.fixed.peto.pretty.names()
    pretty.metric <- eval(parse(text=paste("pretty.names$measure$", params$measure,sep="")))
    for (count in 1:length(summary.disp$table.titles)) {
      summary.disp$table.titles[count] <- paste(" ", pretty.metric, " -", summary.disp$table.titles[count], sep="")
    }
    results <- list("Summary"=summary.disp)
    
    if (is.null(params$create.plot) || params$create.plot == TRUE ||
        is.null(params$write.to.file) || params$write.to.file == TRUE) {
      if (is.null(diagnostic.data@y) || is.null(diagnostic.data@SE)) {
        # compute point estimates for plot.data in case they are missing
        diagnostic.data <- compute.bin.point.estimates(diagnostic.data, params)
      }
      if (is.null(params$write.to.file) || params$write.to.file == TRUE) {
        # Write results and study data to csv files  
        res$study.weights <- (1 / res$vi) / sum(1 / res$vi)
        results.path <- paste("./r_tmp/diagnostic_fixed_peto_results.csv")
        # Keep the default path here unless callers pass an override in params.
        # Study-data CSV export can be re-enabled beside the results file.
        write.results.to.file(diagnostic.data, params, res, outpath=results.path)
      }
      if (is.null(params$create.plot) || params$create.plot == TRUE) {
        # Create forest plot and list to display summary of results
        metric.name <- pretty.metric.name(as.character(params$measure))
        model.title <- "Diagnostic Fixed-Effect Model - Peto\n\nMetric: Odds Ratio"
        # Create results display tables
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        #
        # generate forest plot 
        #
        forest.path <- paste(params$fp_outpath, sep="")
        plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
        changed.params <- plot.data$changed.params
        # list of changed params values
        params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
        changed.params <- c(changed.params, params.changed.in.forest.plot)
        params <- update.changed.plot.params(params, changed.params)
        # dump the forest plot params to disk; return path to
        # this .Rdata for later use
        forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)
        #
        # Now we package the results in a dictionary (technically, a named 
        # vector). In particular, there are two fields that must be returned; 
        # a dictionary of images (mapping titles to image paths) and a list of texts
        # (mapping titles to pretty-printed text). In this case we have only one 
        # of each. 
        # 
        plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
        images <- c("Forest Plot"=forest.path)
        plot.names <- c("forest plot"="forest_plot")
        results <- list("images"=images,
				        "Summary"=summary.disp,
                        "plot_names"=plot.names,
						"plot_params_paths"=plot.params.paths)
      }
    }
  }
  
  references <- rcmetar.method.references("rma.peto")
  results[["References"]] <- references
  
  results
}

diagnostic.fixed.peto.parameters <- function(){
  # parameters
  apply_adjustment_to = c("only0", "all")
  
  params <- list( "conf.level"="float", "digits"="int",
                  "adjust"="float", "to"=apply_adjustment_to)
  
  # default values
  defaults <- list("conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS, "adjust"=.5, "to"="only0")
  
  var_order = c("conf.level", "digits", "adjust", "to")
  
  parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}

diagnostic.fixed.peto.pretty.names <- function() {
  pretty.names <- list("pretty.name"="Diagnostic Fixed-Effect Peto", 
                       "description" = "Performs fixed-effect meta-analysis using the Peto method.",
                       "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"), 
                       "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                       "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                       "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero.")
                         )
}

diagnostic.fixed.peto.is.feasible <- function(diagnostic.data, metric){
  # only feasible if we have raw (2x2) data for all studies
  # and the metric is `DOR'
  metric == "DOR" &&
    length(diagnostic.data@TP)==length(diagnostic.data@FN) &&
    length(diagnostic.data@FN)==length(diagnostic.data@FP) &&
    length(diagnostic.data@FP)==length(diagnostic.data@TN) &&
    length(diagnostic.data@TP) > 0
}

diagnostic.fixed.peto.overall <- function(results) {
  # this parses out the overall from the computed result
  res <- results$Summary$MAResults
}

##################################
#  diagnostic random effects     #
##################################
diagnostic.random <- function(diagnostic.data, params){
    # assert that the argument is the correct type
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")
    
    results <- NULL
    inference.method <- rcmetar.validate.inference.method(params, length(diagnostic.data@y))
    if (length(diagnostic.data@TP) == 1 || length(diagnostic.data@y) == 1){
        res <- get.res.for.one.diag.study(diagnostic.data, params)
        # Package res for use by overall method.
        summary.disp <- list("MAResults" = res) 
        results <- list("Summary"=summary.disp)
    } else {
        # call out to the metafor package
        res<-rma.uni(yi=diagnostic.data@y, sei=diagnostic.data@SE, 
                 slab=diagnostic.data@study.names,
                 method=params$rm.method, test=inference.method, level=params$conf.level,
                 digits=params$digits)

		# GD EXPERIMENTAL#########################
		weights <- 1 / (res$vi + res$tau2)
        res$study.weights <- weights / sum(weights)
		res$study.names <- diagnostic.data@study.names
		res$study.years <- diagnostic.data@years
		#########################################
		 
        # Create list to display summary of results
        model.title <- paste("Diagnostic Random-Effects Model (k = ", res$k, ")", sep="")
        summary.disp <- create.summary.disp(diagnostic.data, params, res, model.title)
        pretty.names <- diagnostic.random.pretty.names()
        pretty.metric <- eval(parse(text=paste("pretty.names$measure$", params$measure,sep="")))
        for (count in 1:length(summary.disp$table.titles)) {
            summary.disp$table.titles[count] <- paste(pretty.metric, " -", summary.disp$table.titles[count], sep="")
        }
        # Write results and study data to csv files
        if ((is.null(params$write.to.file)) || params$write.to.file == TRUE) {
            results.path <- paste("./r_tmp/diag_random_", params$measure, "_results.csv", sep="")
            # Keep the default path here unless callers pass an override in params.
            write.results.to.file(diagnostic.data, params, res, outpath=results.path)
        }
        #
        # generate forest plot 
        #
        if ((is.null(params$create.plot)) || (params$create.plot == TRUE)) {
            forest.path <- paste(params$fp_outpath, sep="")
            plot.data <- create.plot.data.diagnostic(diagnostic.data, params, res)
            changed.params <- plot.data$changed.params
            # list of changed params values
            params.changed.in.forest.plot <- rcmetar.draw.forest.plot(plot.data, forest.path)
            changed.params <- c(changed.params, params.changed.in.forest.plot)
            params <- update.changed.plot.params(params, changed.params)
            # update params values
            # we use the system time as our unique-enough string to store
            # the params object
            forest.plot.params.path <- save.data(diagnostic.data, res, params, plot.data)
            
            plot.params.paths <- c("Forest Plot"=forest.plot.params.path)
            images <- c("Forest Plot"=forest.path)
            plot.names <- c("forest plot"="forest_plot")
			
			
            results <- list("images"=images,
					        "Summary"=summary.disp,
                            "plot_names"=plot.names, 
                            "plot_params_paths"=plot.params.paths)
        }
        else {
            results <- list("Summary"=summary.disp)
        } 
    }
	
	references <- rcmetar.unique.references(c(
        rcmetar.method.references("rma.uni.random"),
        rcmetar.inference.method.references(params)))
	results[["References"]] <- references
	
    results
}

diagnostic.random.parameters <- function(){
    apply.adjustment.to = c("only0", "all")
    rm.method.ls <- rcmetar.random.effects.methods()
    params <- list("rm.method"=rm.method.ls, "inference.method"=rcmetar.inference.methods(), "conf.level"="float", "digits"="int",
                            "adjust"="float", "to"=apply.adjustment.to)
    
    # default values
    defaults <- list("rm.method"="DL", "inference.method"="z", "conf.level"=95, "digits"=RCMETAR_DEFAULT_DISPLAY_DIGITS,
                            "adjust"=.5, "to"="only0")
    
    var.order <- c("rm.method", "inference.method", "conf.level", "digits", "adjust", "to")
    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var.order)
}

diagnostic.random.pretty.names <- function() {
	# Keep display names explicit even though rm_method_ls defines the codes.
	rm_method_names <- rcmetar.random.effects.method.names()
	
    pretty.names <- list("pretty.name"="Diagnostic Random-Effects", 
                         "description" = "Performs random-effects meta-analysis.",
                         "rm.method"=list("pretty.name"="Random-Effects method", "description"="Method for estimating between-studies heterogeneity", "rm.method.names"=rm_method_names),                      
                         "inference.method"=rcmetar.inference.method.metadata(),
                         "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"), 
                         "digits"=list("pretty.name"="Decimal places", "description"="Decimal places for displayed estimates and intervals; p-values use at least 3"),
                         "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Correction factor target", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero."),
                         "measure"=list("Sens"="Sensitivity", "Spec"="Specificity", "DOR"="Odds Ratio", "PLR"="Positive Likelihood Ratio",
                                        "NLR"="Negative Likelihood Ratio")
                         )
}

diagnostic.random.is.feasible <- function(diagnostic.data, metric){
    metric %in% c("Sens", "Spec", "PLR", "NLR", "DOR")      
}
diagnostic.random.overall <- function(results) {
    # this parses out the overall from the computed result
    res <- results$Summary$MAResults
}

hsroc.retry.out.dir <- function(chain.out.dir) {
    retry.out.dir <- paste(chain.out.dir, "_retry_1", sep="")
    if (!dir.create(retry.out.dir, showWarnings=FALSE)) {
        stop(paste("Could not create HSROC retry output directory:", retry.out.dir))
    }
    retry.out.dir
}

hsroc.required.chain.files <- function() {
    c("theta.txt", "alpha.txt", "PI.txt", "Sens1.txt", "Spec1.txt",
      "Sens1_new.txt", "Spec1_new.txt",
      "sigma.theta.txt", "sigma.alpha.txt", "capital_THETA.txt",
      "LAMBDA.txt", "beta.txt", "S_overall.txt", "C_overall.txt")
}

hsroc.read.chain.samples <- function(sample.path) {
    sample.size <- file.info(sample.path)$size
    if (!is.na(sample.size) && sample.size > 0 && sample.size %% 8 == 0) {
        samples <- try(readBin(sample.path, what="numeric", n=sample.size / 8), silent=TRUE)
        if (!inherits(samples, "try-error") && length(samples) > 0) {
            return(samples)
        }
    }

    samples <- try(as.matrix(read.table(sample.path)), silent=TRUE)
    if (inherits(samples, "try-error") || length(samples) == 0) {
        return(samples)
    }
    suppressWarnings(as.numeric(samples))
}

hsroc.chain.validation.error <- function(chain.out.dir) {
    required.files <- file.path(chain.out.dir, hsroc.required.chain.files())
    missing.files <- required.files[!file.exists(required.files)]
    if (length(missing.files) > 0) {
        return(paste("missing sampler output file(s):", paste(basename(missing.files), collapse=", ")))
    }

    for (sample.path in required.files) {
        samples <- hsroc.read.chain.samples(sample.path)
        if (inherits(samples, "try-error") || length(samples) == 0) {
            return(paste("could not read sampler output file:", basename(sample.path)))
        }
        if (any(is.na(samples)) || any(!is.finite(samples))) {
            return(paste("non-finite sampler draw(s) in:", basename(sample.path)))
        }
    }

    NULL
}

hsroc.nonconverged.try.error <- function(reason) {
    structure(
        paste("HSROC sampling did not converge cleanly:", reason),
        class="try-error"
    )
}

run.hsroc.with.recovery <- function(diag.data.frame, params, chain.out.dir) {
    run.once <- function(path) {
        try(HSROC(data=diag.data.frame, iter.num=params$num.iters,
                prior_LAMBDA=c(params$lambda.lower, params$lambda.upper),
                prior_THETA=c(params$theta.lower, params$theta.upper),
                path=path), silent=TRUE)
    }

    res <- run.once(chain.out.dir)
    res.validation.error <- NULL
    if (!inherits(res, "try-error")) {
        res.validation.error <- hsroc.chain.validation.error(chain.out.dir)
    }
    if (!inherits(res, "try-error") && is.null(res.validation.error)) {
        return(list("result"=res, "path"=chain.out.dir))
    }

    retry.out.dir <- hsroc.retry.out.dir(chain.out.dir)
    setwd(retry.out.dir)
    retry.res <- run.once(retry.out.dir)

    if (inherits(retry.res, "try-error")) {
        return(list("result"=retry.res, "path"=retry.out.dir))
    }
    retry.validation.error <- hsroc.chain.validation.error(retry.out.dir)
    if (!is.null(retry.validation.error)) {
        return(list("result"=hsroc.nonconverged.try.error(retry.validation.error), "path"=retry.out.dir))
    }
    list("result"=retry.res, "path"=retry.out.dir)
}

hsroc.retained.iterations <- function(params) {
    round((params$num.iters * params$num.chains - params$burn.in * params$num.chains) / params$thin, 0)
}

hsroc.rasterize.pdf <- function(pdf.path) {
    if (!file.exists(pdf.path)) {
        return(NULL)
    }

    png.path <- sub("[.]pdf$", ".png", pdf.path)
    if (file.exists(png.path)) {
        return(png.path)
    }

    if (!requireNamespace("pdftools", quietly=TRUE)) {
        stop(paste("HSROC produced a PDF plot, but the pdftools R package is not installed to convert it for display:", pdf.path))
    }

    converted <- pdftools::pdf_convert(
        pdf=pdf.path,
        format="png",
        pages=1,
        filenames=png.path,
        dpi=144,
        verbose=FALSE
    )
    if (length(converted) > 0 && file.exists(converted[[1]])) {
        return(converted[[1]])
    }
    if (!file.exists(png.path)) {
        stop(paste("Could not convert HSROC PDF plot for display:", pdf.path))
    }
    png.path
}

hsroc.display.image.path <- function(image.path) {
    if (is.null(image.path) || length(image.path) == 0 || is.na(image.path)) {
        return(NULL)
    }
    image.path <- as.character(image.path[[1]])
    extension <- ""
    if (grepl("[.]", basename(image.path))) {
        extension <- tolower(sub("^.*[.]", "", image.path))
    }

    if (extension %in% c("png", "jpg", "jpeg", "bmp", "gif", "tif", "tiff") && file.exists(image.path)) {
        return(image.path)
    }
    if (extension == "pdf") {
        return(hsroc.rasterize.pdf(image.path))
    }
    NULL
}

hsroc.path.in.out.dir <- function(out.dir, maybe.relative.path) {
    path <- as.character(maybe.relative.path[[1]])
    if (grepl("^([A-Za-z]:)?(/|\\\\)", path)) {
        return(path)
    }
    file.path(out.dir, path)
}

hsroc.stock.pdf.plots <- function(out.dir, params) {
    retained.iterations <- hsroc.retained.iterations(params)
    list(
        "Summary ROC"=file.path(out.dir, "Summary ROC curve.pdf"),
        "Density plots"=file.path(out.dir, paste("Density plots for N =", retained.iterations, ".pdf")),
        "Trace plots"=file.path(out.dir, paste("Trace plots for N =", retained.iterations, ".pdf"))
    )
}

hsroc.display.images <- function(hsroc.sum, out.dir, params) {
    images <- list()

    if (!is.null(hsroc.sum$image.list) && length(hsroc.sum$image.list) > 0) {
        for (img.name in names(hsroc.sum$image.list)) {
            image.path <- hsroc.path.in.out.dir(out.dir, hsroc.sum$image.list[[img.name]])
            display.path <- hsroc.display.image.path(image.path)
            if (!is.null(display.path)) {
                images[[img.name]] <- display.path
            }
        }
        if (length(images) > 0) {
            return(images)
        }
    }

    stock.pdfs <- hsroc.stock.pdf.plots(out.dir, params)
    for (img.name in names(stock.pdfs)) {
        display.path <- hsroc.display.image.path(stock.pdfs[[img.name]])
        if (!is.null(display.path)) {
            images[[img.name]] <- display.path
        }
    }
    images
}

hsroc.summary.path.argument <- function(out.dir) {
    if ("summary.path" %in% names(formals(HSROCSummary))) {
        return(list("summary.path"=out.dir))
    }
    list("path"=out.dir)
}

hsroc.retained.chain.samples <- function(chain.out.dirs, file.name, params) {
    retained.samples <- numeric()
    for (chain.out.dir in chain.out.dirs) {
        samples <- hsroc.read.chain.samples(file.path(chain.out.dir, file.name))
        if (inherits(samples, "try-error") || length(samples) == 0) {
            stop(paste("Could not read HSROC sampler output file:", file.name))
        }
        if (params$burn.in >= length(samples)) {
            stop("HSROC burn-in removed all retained sampler draws.")
        }
        samples <- samples[(params$burn.in + 1):length(samples)]
        samples <- samples[seq(1, length(samples), by=params$thin)]
        retained.samples <- c(retained.samples, samples)
    }
    retained.samples
}

hsroc.hpd.interval <- function(samples) {
    if (requireNamespace("coda", quietly=TRUE)) {
        return(as.numeric(coda::HPDinterval(coda::as.mcmc(samples))[1, ]))
    }
    as.numeric(stats::quantile(samples, probs=c(0.025, 0.975), names=FALSE))
}

hsroc.repair.summary <- function(hsroc.sum, chain.out.dirs, params) {
    summary.name <- "Between-study parameters"
    if (!summary.name %in% names(hsroc.sum)) {
        return(hsroc.sum)
    }

    between.study <- hsroc.sum[[summary.name]]
    if (is.null(dim(between.study)) || is.null(rownames(between.study))) {
        return(hsroc.sum)
    }

    row.index <- which(rownames(between.study) %in% c("Specificity (new)", "C1_new"))
    if (length(row.index) != 1) {
        return(hsroc.sum)
    }

    column.names <- colnames(between.study)
    estimate.column <- grep("estimate", column.names, ignore.case=TRUE)
    lower.column <- grep("HPD[._ ]?(low|lower)", column.names, ignore.case=TRUE)
    upper.column <- grep("HPD[._ ]?(high|upper)", column.names, ignore.case=TRUE)
    if (length(estimate.column) != 1 || length(lower.column) != 1 || length(upper.column) != 1) {
        return(hsroc.sum)
    }

    estimate <- as.numeric(between.study[row.index, estimate.column])
    lower <- as.numeric(between.study[row.index, lower.column])
    upper <- as.numeric(between.study[row.index, upper.column])
    if (is.finite(estimate) && is.finite(lower) && is.finite(upper) &&
        lower <= estimate && estimate <= upper) {
        return(hsroc.sum)
    }

    c1.new.samples <- hsroc.retained.chain.samples(chain.out.dirs, "Spec1_new.txt", params)
    if (any(is.na(c1.new.samples)) || any(!is.finite(c1.new.samples))) {
        return(hsroc.sum)
    }

    hpd <- hsroc.hpd.interval(c1.new.samples)
    between.study[row.index, estimate.column] <- stats::median(c1.new.samples)
    between.study[row.index, lower.column] <- hpd[1]
    between.study[row.index, upper.column] <- hpd[2]
    hsroc.sum[[summary.name]] <- between.study
    hsroc.sum
}

hsroc.validate.summary.intervals <- function(hsroc.sum) {
    summary.names <- intersect(c("Between-study parameters", "Within-study parameters", "Reference standard"), names(hsroc.sum))
    for (summary.name in summary.names) {
        summary.section <- hsroc.sum[[summary.name]]
        if (is.null(dim(summary.section)) || length(dim(summary.section)) != 2) {
            next
        }

        column.names <- colnames(summary.section)
        estimate.column <- grep("estimate", column.names, ignore.case=TRUE)
        lower.column <- grep("HPD[._ ]?(low|lower)", column.names, ignore.case=TRUE)
        upper.column <- grep("HPD[._ ]?(high|upper)", column.names, ignore.case=TRUE)
        if (length(estimate.column) != 1 || length(lower.column) != 1 || length(upper.column) != 1) {
            next
        }

        estimates <- as.numeric(summary.section[, estimate.column])
        lower <- as.numeric(summary.section[, lower.column])
        upper <- as.numeric(summary.section[, upper.column])
        bad.interval <- is.finite(estimates) & is.finite(lower) & is.finite(upper) &
            (upper < lower | estimates < lower | estimates > upper)
        if (any(bad.interval)) {
            bad.names <- rownames(summary.section)[bad.interval]
            if (is.null(bad.names)) {
                bad.names <- which(bad.interval)
            }
            stop(paste("HSROC summary returned inconsistent interval bounds for",
                       summary.name, paste(bad.names, collapse=", "),
                       "- sampling did not converge cleanly. Try more iterations, a longer burn-in, or wider priors."))
        }
    }

    invisible(TRUE)
}

hsroc.summary.columns <- function(summary.section) {
    column.names <- colnames(summary.section)
    list(
        estimate=grep("estimate", column.names, ignore.case=TRUE),
        lower=grep("HPD[._ ]?(low|lower)", column.names, ignore.case=TRUE),
        upper=grep("HPD[._ ]?(high|upper)", column.names, ignore.case=TRUE)
    )
}

hsroc.canonical.summary.column.name <- function(column.name) {
    compact <- tolower(gsub("[._]+", " ", trimws(as.character(column.name))))
    compact <- gsub("[[:space:]]+", " ", compact)
    if (compact %in% c("hpd low", "hpd lower", "ci lb", "lower bound")) {
        return("Lower bound")
    }
    if (compact %in% c("hpd high", "hpd upper", "ci ub", "upper bound")) {
        return("Upper bound")
    }
    if (compact == "median estimate") {
        return("Median estimate")
    }
    as.character(column.name)
}

hsroc.normalize.summary.headers <- function(summary.section) {
    if (is.list(summary.section) && is.null(dim(summary.section))) {
        return(lapply(summary.section, hsroc.normalize.summary.headers))
    }

    if (!is.null(dim(summary.section)) && length(dim(summary.section)) >= 2) {
        column.names <- colnames(summary.section)
        if (!is.null(column.names)) {
            colnames(summary.section) <- vapply(
                column.names,
                hsroc.canonical.summary.column.name,
                character(1),
                USE.NAMES=FALSE
            )
        }
    }

    summary.section
}

hsroc.summary.row <- function(summary.section, candidates) {
    row.names <- rownames(summary.section)
    if (is.null(row.names)) {
        return(NULL)
    }
    row.index <- which(row.names %in% candidates)
    if (length(row.index) != 1) {
        return(NULL)
    }
    row.index
}

hsroc.summary.values <- function(summary.section, candidates) {
    columns <- hsroc.summary.columns(summary.section)
    if (length(columns$estimate) != 1 || length(columns$lower) != 1 || length(columns$upper) != 1) {
        return(NULL)
    }
    row.index <- hsroc.summary.row(summary.section, candidates)
    if (is.null(row.index)) {
        return(NULL)
    }
    stats::setNames(
        as.numeric(c(
            summary.section[row.index, columns$estimate],
            summary.section[row.index, columns$lower],
            summary.section[row.index, columns$upper]
        )),
        c("estimate", "lower", "upper")
    )
}

hsroc.safe.ratio <- function(numerator, denominator) {
    if (is.na(numerator) || is.na(denominator) || denominator == 0) {
        return(NA_real_)
    }
    numerator / denominator
}

hsroc.diagnostic.odds.ratio <- function(sensitivity, specificity) {
    hsroc.safe.ratio(sensitivity * specificity, (1 - sensitivity) * (1 - specificity))
}

hsroc.posterior.summary <- function(samples) {
    samples <- samples[is.finite(samples)]
    if (length(samples) == 0) {
        return(NULL)
    }
    hpd <- hsroc.hpd.interval(samples)
    stats::setNames(c(stats::median(samples), hpd[1], hpd[2]), c("estimate", "lower", "upper"))
}

hsroc.derived.accuracy.rows.from.samples <- function(chain.out.dirs, params) {
    sensitivity.samples <- hsroc.retained.chain.samples(chain.out.dirs, "Sens1_new.txt", params)
    specificity.samples <- hsroc.retained.chain.samples(chain.out.dirs, "Spec1_new.txt", params)
    sample.count <- min(length(sensitivity.samples), length(specificity.samples))
    if (sample.count == 0) {
        return(NULL)
    }
    sensitivity.samples <- sensitivity.samples[seq_len(sample.count)]
    specificity.samples <- specificity.samples[seq_len(sample.count)]

    plr.samples <- sensitivity.samples / (1 - specificity.samples)
    nlr.samples <- (1 - sensitivity.samples) / specificity.samples
    dor.samples <- (sensitivity.samples * specificity.samples) /
        ((1 - sensitivity.samples) * (1 - specificity.samples))
    list(
        plr=hsroc.posterior.summary(plr.samples),
        nlr=hsroc.posterior.summary(nlr.samples),
        dor=hsroc.posterior.summary(dor.samples)
    )
}

hsroc.derived.accuracy.rows.from.intervals <- function(sensitivity, specificity) {
    plr <- c(
        estimate=hsroc.safe.ratio(sensitivity[["estimate"]], 1 - specificity[["estimate"]]),
        lower=hsroc.safe.ratio(sensitivity[["lower"]], 1 - specificity[["lower"]]),
        upper=hsroc.safe.ratio(sensitivity[["upper"]], 1 - specificity[["upper"]])
    )
    nlr <- c(
        estimate=hsroc.safe.ratio(1 - sensitivity[["estimate"]], specificity[["estimate"]]),
        lower=hsroc.safe.ratio(1 - sensitivity[["upper"]], specificity[["upper"]]),
        upper=hsroc.safe.ratio(1 - sensitivity[["lower"]], specificity[["lower"]])
    )
    dor <- c(
        estimate=hsroc.diagnostic.odds.ratio(sensitivity[["estimate"]], specificity[["estimate"]]),
        lower=hsroc.diagnostic.odds.ratio(sensitivity[["lower"]], specificity[["lower"]]),
        upper=hsroc.diagnostic.odds.ratio(sensitivity[["upper"]], specificity[["upper"]])
    )
    list(plr=plr, nlr=nlr, dor=dor)
}

hsroc.derived.accuracy.rows <- function(sensitivity, specificity, chain.out.dirs, params) {
    sampled.rows <- try(hsroc.derived.accuracy.rows.from.samples(chain.out.dirs, params), silent=TRUE)
    if (!inherits(sampled.rows, "try-error") && !is.null(sampled.rows) &&
        !is.null(sampled.rows$plr) && !is.null(sampled.rows$nlr) && !is.null(sampled.rows$dor)) {
        return(sampled.rows)
    }
    hsroc.derived.accuracy.rows.from.intervals(sensitivity, specificity)
}

hsroc.format.summary.number <- function(x, digits) {
    if (is.na(x) || !is.finite(x)) {
        return("NA")
    }
    sprintf(paste("%.", digits, "f", sep=""), x)
}

hsroc.capture.print.output <- function(x, ..., width=10000) {
    old.options <- options(width=width)
    on.exit(options(old.options), add=TRUE)
    paste(capture.output(print(x, ...)), collapse="\n")
}

hsroc.summary.table.text <- function(rows, digits) {
    formatted <- data.frame(
        Metric=names(rows),
        Estimate=vapply(rows, function(row) hsroc.format.summary.number(row[["estimate"]], digits), character(1)),
        `Lower bound`=vapply(rows, function(row) hsroc.format.summary.number(row[["lower"]], digits), character(1)),
        `Upper bound`=vapply(rows, function(row) hsroc.format.summary.number(row[["upper"]], digits), character(1)),
        check.names=FALSE
    )
    hsroc.capture.print.output(formatted, row.names=FALSE, right=FALSE)
}

hsroc.model.parameter.label <- function(parameter.name) {
    labels <- list(
        "THETA"=c("Accuracy parameter", "Higher values increase diagnostic accuracy."),
        "LAMBDA"=c("Threshold parameter", "Higher values reflect a stricter positivity threshold."),
        "beta"=c("Shape parameter", "Controls HSROC curve asymmetry or covariate effects."),
        "sigma.alpha"=c("Between-study accuracy SD", "Between-study variation in diagnostic accuracy."),
        "sigma.theta"=c("Between-study threshold SD", "Between-study variation in positivity threshold.")
    )
    if (parameter.name %in% names(labels)) {
        return(labels[[parameter.name]])
    }
    c(as.character(parameter.name), "HSROC model parameter.")
}

hsroc.model.parameter.table.text <- function(rows, descriptions, digits) {
    formatted <- data.frame(
        Parameter=names(rows),
        Description=descriptions,
        Estimate=vapply(rows, function(row) hsroc.format.summary.number(row[["estimate"]], digits), character(1)),
        `Lower bound`=vapply(rows, function(row) hsroc.format.summary.number(row[["lower"]], digits), character(1)),
        `Upper bound`=vapply(rows, function(row) hsroc.format.summary.number(row[["upper"]], digits), character(1)),
        check.names=FALSE
    )
    hsroc.capture.print.output(formatted, row.names=FALSE, right=FALSE)
}

hsroc.model.parameter.summary <- function(between.study, clinical.rows, digits) {
    if (is.null(dim(between.study)) || is.null(rownames(between.study))) {
        return(NULL)
    }
    model.rows <- setdiff(seq_len(nrow(between.study)), clinical.rows)
    if (length(model.rows) == 0) {
        return(NULL)
    }

    model.parameters <- between.study[model.rows, , drop=FALSE]
    columns <- hsroc.summary.columns(model.parameters)
    if (length(columns$estimate) == 1 && length(columns$lower) == 1 && length(columns$upper) == 1) {
        rows <- lapply(seq_len(nrow(model.parameters)), function(row.index) {
            stats::setNames(
                as.numeric(c(
                    model.parameters[row.index, columns$estimate],
                    model.parameters[row.index, columns$lower],
                    model.parameters[row.index, columns$upper]
                )),
                c("estimate", "lower", "upper")
            )
        })
        parameter.labels <- lapply(rownames(model.parameters), hsroc.model.parameter.label)
        names(rows) <- vapply(parameter.labels, function(label) label[[1]], character(1))
        descriptions <- vapply(parameter.labels, function(label) label[[2]], character(1))
        return(hsroc.model.parameter.table.text(rows, descriptions, digits))
    }

    hsroc.capture.print.output(model.parameters)
}

hsroc.add.study.names.to.within.study.summary <- function(hsroc.sum, diagnostic.data=NULL) {
    if (is.null(diagnostic.data) || !"Within-study parameters" %in% names(hsroc.sum)) {
        return(hsroc.sum)
    }
    study.names <- diagnostic.data@study.names
    if (length(study.names) == 0) {
        return(hsroc.sum)
    }

    within.study <- hsroc.sum[["Within-study parameters"]]
    dimensions <- dim(within.study)
    if (is.null(dimensions) || length(dimensions) < 1 || dimensions[[1]] != length(study.names)) {
        return(hsroc.sum)
    }

    within.dimnames <- dimnames(within.study)
    if (is.null(within.dimnames)) {
        within.dimnames <- vector("list", length(dimensions))
    }
    within.dimnames[[1]] <- study.names
    dimnames(within.study) <- within.dimnames
    hsroc.sum[["Within-study parameters"]] <- within.study
    hsroc.sum
}

hsroc.display.summary <- function(hsroc.sum, params, chain.out.dirs, diagnostic.data=NULL) {
    hsroc.sum <- hsroc.add.study.names.to.within.study.summary(hsroc.sum, diagnostic.data)
    raw.summary.names <- intersect(c("Between-study parameters", "Within-study parameters", "Reference standard"), names(hsroc.sum))
    fallback.summary <- hsroc.normalize.summary.headers(hsroc.sum[raw.summary.names])
    if (!"Between-study parameters" %in% names(hsroc.sum)) {
        return(fallback.summary)
    }

    between.study <- hsroc.sum[["Between-study parameters"]]
    if (is.null(dim(between.study)) || length(dim(between.study)) != 2) {
        return(fallback.summary)
    }

    digits <- params$digits
    if (is.null(digits) || is.na(digits)) {
        digits <- RCMETAR_DEFAULT_DISPLAY_DIGITS
    }

    summary.sensitivity.rows <- c("S Overall", "Sensitivity Overall", "Sensitivity (overall)")
    summary.specificity.rows <- c("C Overall", "Specificity Overall", "Specificity (overall)")
    predicted.sensitivity.rows <- c("S1_new", "Sensitivity (new)")
    predicted.specificity.rows <- c("C1_new", "Specificity (new)")
    summary.sensitivity <- hsroc.summary.values(between.study, summary.sensitivity.rows)
    summary.specificity <- hsroc.summary.values(between.study, summary.specificity.rows)
    predicted.sensitivity <- hsroc.summary.values(between.study, predicted.sensitivity.rows)
    predicted.specificity <- hsroc.summary.values(between.study, predicted.specificity.rows)

    accuracy.sensitivity <- summary.sensitivity
    accuracy.specificity <- summary.specificity
    if (is.null(accuracy.sensitivity) || is.null(accuracy.specificity)) {
        accuracy.sensitivity <- predicted.sensitivity
        accuracy.specificity <- predicted.specificity
    }
    if (is.null(accuracy.sensitivity) || is.null(accuracy.specificity)) {
        return(fallback.summary)
    }

    derived <- hsroc.derived.accuracy.rows(accuracy.sensitivity, accuracy.specificity, chain.out.dirs, params)
    summary.rows <- list(
        "Summary Sensitivity"=summary.sensitivity,
        "Summary Specificity"=summary.specificity,
        "Predicted Sensitivity (new study)"=predicted.sensitivity,
        "Predicted Specificity (new study)"=predicted.specificity,
        "Positive Likelihood Ratio"=derived$plr,
        "Negative Likelihood Ratio"=derived$nlr,
        "Diagnostic Odds Ratio"=derived$dor,
        "Summary ROC point (Sensitivity)"=accuracy.sensitivity,
        "Summary ROC point (Specificity)"=accuracy.specificity
    )
    summary.rows <- summary.rows[!vapply(summary.rows, is.null, logical(1))]

    summary <- list("Clinical Accuracy Summary"=hsroc.summary.table.text(summary.rows, digits))
    clinical.row.indexes <- c(
        hsroc.summary.row(between.study, summary.sensitivity.rows),
        hsroc.summary.row(between.study, summary.specificity.rows),
        hsroc.summary.row(between.study, predicted.sensitivity.rows),
        hsroc.summary.row(between.study, predicted.specificity.rows)
    )
    model.summary <- hsroc.model.parameter.summary(between.study, clinical.row.indexes, digits)
    if (!is.null(model.summary)) {
        summary[["HSROC Model Parameters"]] <- model.summary
    }
    for (summary.name in setdiff(names(fallback.summary), "Between-study parameters")) {
        summary[[summary.name]] <- fallback.summary[[summary.name]]
    }
    summary
}

##################################
#       diagnostic hsroc         #
##################################
diagnostic.hsroc <- function(diagnostic.data, params){
    prev.working.dir <- getwd()
    on.exit(setwd(prev.working.dir), add=TRUE)

    # Run the sampler from the analysis scratch subdirectory expected by HSROC.
    setwd("r_tmp")

    ####
    # first we create a unique directory
    unique.name <- as.character(as.numeric(Sys.time()))
    out.dir <- paste(getwd(), unique.name, sep="/")
    dir.create(out.dir)

    #### 
    # convert the diagnostic data to a format consumable
    # by the HSROC lib, this means a data frame
    # with the following columns:
    #    ++ +- -+  --
    diag.data.frame <- 
        data.frame(TP=diagnostic.data@TP, FP=diagnostic.data@FP, FN=diagnostic.data@FN, TN=diagnostic.data@TN)

    ### set up and run the three chains
    chain.out.dirs <- c()
    for (chain.i in 1:params$num.chains){
        chain.out.dir <- paste(out.dir, "/chain_", chain.i, sep="")
        dir.create(chain.out.dir)
        setwd(chain.out.dir)

        chain.res <- run.hsroc.with.recovery(diag.data.frame, params, chain.out.dir)
        res <- chain.res$result

        # Put in try block in case HSROC fails
        if (inherits(res, "try-error")) {
            stop("Sorry -- HSROC sampling did not converge cleanly. Try more iterations, a longer burn-in, or wider priors.")
        }
        chain.out.dirs <- c(chain.out.dirs, chain.res$path)
    }

    chain.validation.errors <- vapply(chain.out.dirs, function(path) {
        validation.error <- hsroc.chain.validation.error(path)
        if (is.null(validation.error)) {
            return(NA_character_)
        }
        validation.error
    }, character(1))
    if (any(!is.na(chain.validation.errors))) {
        stop("Sorry -- HSROC sampling did not converge cleanly. Try more iterations, a longer burn-in, or wider priors.")
    }

    summary.args <- c(list(data=diag.data.frame, burn_in=params$burn.in, Thin=params$thin, print_plot=T,
                           chain=chain.out.dirs),
                      hsroc.summary.path.argument(out.dir))
    hsroc.sum <- do.call(HSROCSummary, summary.args)
    hsroc.sum <- hsroc.repair.summary(hsroc.sum, chain.out.dirs, params)
    hsroc.validate.summary.intervals(hsroc.sum)

    #### 
    # pull out the summary
    required.summary.names <- c("Between-study parameters", "Within-study parameters")
    missing.summary.names <- required.summary.names[!required.summary.names %in% names(hsroc.sum)]
    if (length(missing.summary.names) > 0) {
        stop(paste("HSROC summary did not contain expected section(s):", paste(missing.summary.names, collapse=", ")))
    }
    summary <- hsroc.display.summary(hsroc.sum, params, chain.out.dirs, diagnostic.data)

    ####
    # and the images
    images <- hsroc.display.images(hsroc.sum, out.dir, params)
    plot.capabilities <- setNames(
        lapply(names(images), function(name) .rcmetar.plot.descriptor.for.kind("other", has.params=FALSE)),
        names(images)
    )

    # we don't want the SROC plot to be mixed in with 
    # the density plots...
    roc.plot.name <- "Summary ROC"
    if (roc.plot.name %in% names(plot.capabilities)) {
        plot.capabilities[[roc.plot.name]] <- .rcmetar.plot.descriptor.for.kind("sroc", has.params=FALSE)
    }
    image.names <- names(images)
    image.order <- c()
    if (roc.plot.name %in% image.names) {
        image.order <- c(image.order, roc.plot.name)
    }
    image.order <- c(image.order, image.names[image.names!=roc.plot.name])
	references <- rcmetar.method.references("hsroc")
    results <- list("images"=images,
                    "image_order"=image.order,
                    "plot_capabilities"=plot.capabilities,
					"Summary"=summary,
					"References"=rcmetar.unique.references(references))

}


diagnostic.hsroc.parameters <- function(){
    params <- list("num.iters"="float", "burn.in"="float", "thin"="float", 
                        "theta.lower"="float", "theta.upper"="float",
                        "lambda.lower"="float", "lambda.upper"="float",
                        "num.chains"="float")
    
    # default values
    defaults <- list("num.iters"=5000, "burn.in"=1000, "thin"=2, 
                        "theta.lower"=-2, "theta.upper"=2,
                        "lambda.lower"=-2, "lambda.upper"=2,
                        "num.chains"=3)
    
    var.order <- c("num.iters", "burn.in", "thin", "num.chains", 
                    "theta.lower", "theta.upper",
                    "lambda.lower", "lambda.upper")
    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var.order)
}

diagnostic.hsroc.pretty.names <- function() {
    pretty.names <- list("pretty.name"="HSROC", 
                         "description" = "Hierarchical regression analysis of diagnostic data\n (Rutter and Gatsonis, Statistics in Medicine, 2001).",
                         "num.iters"=list("pretty.name"="Number of Iterations", "description"="Number of iterations to run."),
                         "burn.in"=list("pretty.name"="Burn in", "description"="Number of draws to use for convergence."),
                         "thin"=list("pretty.name"="Thin", "description"="Thinning."),
                         "num.chains"=list("pretty.name"="Number of Chains", "description"="Number of MCMC chains."),
                         "lambda.lower"=list("pretty.name"="prior on lambda (lower)", "description"="Lower value in (uniform) range over expected lambda values."),
                         "lambda.upper"=list("pretty.name"="prior on lambda (upper)", "description"="Upper value in (uniform) range over expected lambda values."),
                         "theta.lower"=list("pretty.name"="prior on theta (lower)", "description"="Lower value in (uniform) range over expected theta values."),
                         "theta.upper"=list("pretty.name"="prior on theta (upper)", "description"="Upper value in (uniform) range over expected theta values.")
                    )
}


diagnostic.hsroc.is.feasible <- function(diagnostic.data, metric){
    # only estimable when we have >= 5 studies
    length(diagnostic.data@TP) > 4
}

diagnostic.hsroc.ml.is.feasible <- diagnostic.hsroc.is.feasible


##################################
#   diagnostic biviariate        #
##################################
diagnostic.bivariate.ml <- function(diagnostic.data, params){
	mult <- get.mult.from.conf.level(params$conf.level)
    adjusted.counts <- adjust.raw.data(diagnostic.data, params)

    biv.results <- bivariate.dx.test(adjusted.counts$TP, adjusted.counts$FP, adjusted.counts$FN, adjusted.counts$TN)

    
    #### 
    # Extract the bivariate summary values from the model output matrix.
    logit_sens = biv.results[1,1]
    logit_spec = biv.results[1,2]
    se_logit_sens = biv.results[1,3]
    se_logit_spec = biv.results[1,4]
    correlation = biv.results[1,7]

    digits = RCMETAR_DEFAULT_DISPLAY_DIGITS
    digits.str <- paste("%.", digits, "f", sep="")
    sensitivity <- sprintf(digits.str, invlogit(logit_sens))
	# Un-hard-coding CI.. issue # 214
    sens.low <- sprintf(digits.str, invlogit(logit_sens - mult*se_logit_sens))
    sens.high <- sprintf(digits.str, invlogit(logit_sens + mult*se_logit_sens))

    specificity <- sprintf(digits.str, invlogit(logit_spec))
    spec.low <- sprintf(digits.str, invlogit(logit_spec - mult*se_logit_spec))
    spec.high <- sprintf(digits.str, invlogit(logit_spec + mult*se_logit_spec))

    r <- sprintf(digits.str, biv.results$correlation)

    report.array <- array(c("", "Sensitivity","Specificity", "Correlation",
                            "Estimate", sensitivity, specificity, r,
                            "Lower bound", sens.low, spec.low, "",
                            "Upper bound", sens.high,spec.high, ""),
                            dim=c(4,4))

    class(report.array) <- "summary.data"
    summary.text <- capture.output.and.collapse(report.array)


    # generate the plot
    path.to.roc.plot.base <- "./r_tmp/bivariate" # default analysis scratch path
    plot.bivariate(biv.results, adjusted.counts$TP, adjusted.counts$FP, 
                                 adjusted.counts$FN, adjusted.counts$TN,
                                 filepath=path.to.roc.plot.base)

    images <- c("ROC Plot"=paste(path.to.roc.plot.base, ".png", sep=""))
    plot.capabilities <- list(
        "ROC Plot"=.rcmetar.plot.descriptor.for.kind("roc", has.params=FALSE)
    )

	references <- rcmetar.method.references("diagnostic.bivariate")
    results <- list("images"=images,
                    "plot_capabilities"=plot.capabilities,
			        "Summary"=list("Bivariate Summary"=summary.text),
					"References"=rcmetar.unique.references(references))
}


diagnostic.bivariate.ml.parameters <- function(){
    apply_adjustment_to = c("only0", "all")

    params <- list("conf.level"="float", "adjust"="float", "to"=apply_adjustment_to)

    # default values
    defaults <- list("conf.level"=95, "adjust"=.5, "to"="only0")

    var_order = c("conf.level", "adjust", "to")

    parameters <- list("parameters"=params, "defaults"=defaults, "var_order"=var_order)
}


diagnostic.bivariate.ml.pretty.names <- function() {
    pretty.names <- list("pretty.name"="Bivariate (Maximum Likelihood)", 
                         "description" = "Bivariate analysis of sensitivity and specificity \n using maximum likelihood estimate.",
						 "conf.level"=list("pretty.name"="Confidence level", "description"="Level at which to compute confidence intervals"), 
						 "adjust"=list("pretty.name"="Correction factor", "description"="Constant c that is added to the entries of a two-by-two table."),
                         "to"=list("pretty.name"="Add correction factor to", "description"="When Add correction factor is set to \"only 0\", the correction factor
                                   is added to all cells of each two-by-two table that contains at least one zero. When set to \"all\", the correction factor
                                   is added to all two-by-two tables if at least one table contains a zero.")
                        )  
                    
}

diagnostic.bivariate.ml.is.feasible <- function(diagnostic.data, metric){
    # only estimable when we have >= 5 studies
    length(diagnostic.data@TP) > 4
}



##################################
#            SROC Plot           #
##################################
create.sroc.plot.data <- function(diagnostic.data, params){
    # create plot data for an ROC plot.
  
    # assert that the argument is the correct type
    if (!("DiagnosticData" %in% class(diagnostic.data))) stop("Diagnostic data expected.")

    # add constant to zero cells
    data.adj <- adjust.raw.data(diagnostic.data,params)
    # compute true positive ratio = sensitivity 
    TPR <- data.adj$TP / (data.adj$TP + data.adj$FN)
    # compute false positive ratio = 1 - specificity
    FPR <- data.adj$FP / (data.adj$TN + data.adj$FP)
    S <- logit(TPR) + logit(FPR)
    D <- logit(TPR) - logit(FPR)
    s.range <- list("max"=max(S), "min"=min(S))
    inv.var <- data.adj$TP + data.adj$FN + data.adj$FP + data.adj$TN
    res <- lm(D~S)
    fitted.line <- list(intercept=res$coefficients[1], slope=res$coefficients[2])
    std.err <- summary(res)$sigma
    # residual standard error
    mult <- get.mult.from.conf.level(params$conf.level)
    # multiplier for std.err to get conf. int. bounds
    plot.options <- list()
    plot.options$roc.xlabel <- params$roc_xlabel
    plot.options$roc.ylabel <- params$roc_ylabel
    plot.options$roc.title <- params$roc_title
    # Preserve ROC plot options for callers that expose them in the UI.
    plot.data <- list("fitted.line" = fitted.line, "TPR"=TPR, "FPR"=FPR, "std.err"=std.err, "mult"=mult, "inv.var" = inv.var, "s.range" = s.range, "plot.options"=plot.options)
}
