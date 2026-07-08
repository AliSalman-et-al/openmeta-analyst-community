# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later

#' RCMetaR data classes and study data containers
#'
#' RCMetaR represents imported study data with S4 classes. These classes carry
#' study names, notes, entered covariates, raw study-level measurements, and
#' optional precomputed effect-size data used by the analysis wrappers.
#'
#' @section Classes:
#' \describe{
#'   \item{\code{OMData}}{Base study container with study names, notes, covariate names, covariate values, and raw data.}
#'   \item{\code{BinaryData}}{Two-arm or one-arm binary outcome data with event counts, sample sizes, and optional effect-size columns.}
#'   \item{\code{ContinuousData}}{Continuous outcome data with group means, standard deviations, sample sizes, and optional effect-size columns.}
#'   \item{\code{DiagnosticData}}{Diagnostic test accuracy data with true-positive, false-positive, false-negative, and true-negative counts.}
#'   \item{\code{AnalysisSpecification}}{A named analysis request: data type, metric, method, and parameter list.}
#'   \item{\code{CovariateValues}}{A single covariate's name, values, type, and reference level metadata.}
#' }
#'
#' @section Data access:
#' Use \code{get.subset()} to preserve class-specific slots while selecting a
#' subset of study rows. Use \code{get.cov()} and \code{study.column()} when
#' building grouped analyses and display tables.
#'
#' @aliases OMData OMData-class BinaryData BinaryData-class ContinuousData ContinuousData-class DiagnosticData DiagnosticData-class AnalysisSpecification AnalysisSpecification-class CovariateValues CovariateValues-class get.cov study.column
#' @name RCMetaR-data-classes
NULL

#' Binary outcome analysis functions
#'
#' Functions for binary meta-analysis endpoints. RCMetaR supports inverse
#' variance, Mantel-Haenszel, Peto, and random-effects workflows over odds
#' ratios, risk ratios, risk differences, arcsine metrics, and one-arm
#' proportions.
#'
#' @section Analysis entry points:
#' \describe{
#'   \item{\code{binary.fixed.inv.var()}}{Runs a fixed-effect inverse-variance binary meta-analysis.}
#'   \item{\code{binary.fixed.mh()}}{Runs a fixed-effect Mantel-Haenszel binary meta-analysis.}
#'   \item{\code{binary.fixed.peto()}}{Runs a fixed-effect Peto odds-ratio meta-analysis.}
#'   \item{\code{binary.random()}}{Runs a random-effects binary meta-analysis.}
#'   \item{\code{binary.fixed.meta.regression()}}{Runs fixed-effect binary meta-regression through the shared regression pipeline.}
#' }
#'
#' @section Study-level calculations:
#' \code{compute.for.one.bin.study()}, \code{compute.bin.point.estimates()},
#' \code{get.res.for.one.binary.study()}, \code{create.binary.data.array()},
#' and \code{write.bin.study.data.to.file()} prepare per-study estimates,
#' variances, display tables, and exported data files.
#'
#' @section Method metadata:
#' Functions ending in \code{.parameters}, \code{.pretty.names},
#' \code{.value.info}, \code{.overall}, or \code{.is.feasible} describe the
#' method contract consumed by the rc-metastudio UI and Python adapter.
#'
#' @section Transform helpers:
#' \code{binary.transform.f()} returns the transformation function used for a
#' binary metric. \code{arcsine.sqrt()}, \code{invarcsine.sqrt()},
#' \code{freeman_tukey()}, \code{invfreeman_tukey()}, \code{logit()}, and
#' \code{invlogit()} are shared transformation utilities.
#'
#' @section References:
#' See \code{rcmetar.method.references("rma.uni.fixed")},
#' \code{rcmetar.method.references("rma.uni.random")},
#' \code{rcmetar.method.references("rma.mh")}, and
#' \code{rcmetar.method.references("rma.peto")} for the statistical method
#' citations used in result payloads.
#'
#' @aliases binary.fixed.inv.var binary.fixed.inv.var.is.feasible.for.funnel binary.fixed.inv.var.overall binary.fixed.inv.var.parameters binary.fixed.inv.var.pretty.names binary.fixed.inv.var.value.info binary.fixed.meta.regression binary.fixed.mh binary.fixed.mh.is.feasible binary.fixed.mh.is.feasible.for.funnel binary.fixed.mh.overall binary.fixed.mh.parameters binary.fixed.mh.pretty.names binary.fixed.mh.value.info binary.fixed.peto binary.fixed.peto.is.feasible binary.fixed.peto.is.feasible.for.funnel binary.fixed.peto.overall binary.fixed.peto.parameters binary.fixed.peto.pretty.names binary.fixed.peto.value.info binary.random binary.random.is.feasible.for.funnel binary.random.meta.regression.parameters binary.random.overall binary.random.parameters binary.random.pretty.names binary.random.value.info binary.transform.f compute.bin.point.estimates compute.for.one.bin.study create.binary.data.array get.res.for.one.binary.study write.bin.study.data.to.file arcsine.sqrt invarcsine.sqrt freeman_tukey invfreeman_tukey logit invlogit
#' @name RCMetaR-binary-methods
NULL

#' Continuous outcome analysis functions
#'
#' Functions for continuous meta-analysis endpoints. RCMetaR supports
#' fixed-effect and random-effects analyses for raw mean differences,
#' standardized mean differences, and one-arm treatment means.
#'
#' @section Analysis entry points:
#' \describe{
#'   \item{\code{continuous.fixed()}}{Runs a fixed-effect continuous outcome meta-analysis.}
#'   \item{\code{continuous.random()}}{Runs a random-effects continuous outcome meta-analysis.}
#' }
#'
#' @section Study-level calculations:
#' \code{compute.for.one.cont.study()}, \code{get.res.for.one.cont.study()},
#' \code{create.cont.data.array()}, and \code{write.cont.study.data.to.file()}
#' prepare per-study estimates, display tables, and exported data files.
#'
#' @section Method metadata:
#' Functions ending in \code{.parameters}, \code{.pretty.names},
#' \code{.value.info}, \code{.overall}, or \code{.is.feasible.for.funnel}
#' expose UI-facing method metadata.
#'
#' @section References:
#' See \code{rcmetar.method.references("rma.uni.fixed")} and
#' \code{rcmetar.method.references("rma.uni.random")} for the statistical
#' method citations used in result payloads.
#'
#' @aliases continuous.fixed continuous.fixed.is.feasible.for.funnel continuous.fixed.overall continuous.fixed.parameters continuous.fixed.pretty.names continuous.fixed.value.info continuous.random continuous.random.is.feasible.for.funnel continuous.random.overall continuous.random.parameters continuous.random.pretty.names continuous.random.value.info continuous.transform.f compute.for.one.cont.study create.cont.data.array get.res.for.one.cont.study write.cont.study.data.to.file
#' @name RCMetaR-continuous-methods
NULL

#' Diagnostic test accuracy analysis functions
#'
#' Functions for diagnostic test accuracy meta-analysis. RCMetaR supports
#' univariate fixed-effect and random-effects analyses, bivariate mixed models,
#' HSROC analyses, SROC plotting, and predictive-value calculations.
#'
#' @section Analysis entry points:
#' \describe{
#'   \item{\code{diagnostic.fixed.inv.var()}}{Runs a fixed-effect inverse-variance diagnostic analysis.}
#'   \item{\code{diagnostic.fixed.mh()}}{Runs a fixed-effect Mantel-Haenszel diagnostic analysis.}
#'   \item{\code{diagnostic.fixed.peto()}}{Runs a fixed-effect Peto diagnostic analysis.}
#'   \item{\code{diagnostic.random()}}{Runs a random-effects diagnostic analysis.}
#'   \item{\code{diagnostic.hsroc()}}{Runs the HSROC sampler-backed diagnostic workflow.}
#'   \item{\code{diagnostic.bivariate.ml()}}{Runs the bivariate maximum-likelihood diagnostic workflow.}
#' }
#'
#' @section Study-level calculations:
#' \code{adjust.raw.data()}, \code{compute.diag.point.estimates()},
#' \code{compute.diagnostic.terms()}, \code{get.res.for.one.diag.study()},
#' and \code{diagnostic.transform.f()} normalize count data and derive
#' diagnostic metrics.
#'
#' @section Multi-run helpers:
#' \code{multiple.diagnostic()} runs a sequence of diagnostic analyses and
#' \code{append.image.order()} preserves plot ordering in result payloads.
#'
#' @section Plot and predictive-value helpers:
#' \code{create.sroc.plot.data()}, \code{create.side.by.side.plot.data()},
#' \code{plot.bivariate()}, \code{bivariate.dx.test()},
#' \code{compute.ppv()}, \code{compute.npv()}, and
#' \code{plot.ppv.npv.by.prev()} build diagnostic displays.
#'
#' @section References:
#' See \code{rcmetar.method.references("rma.uni.fixed")},
#' \code{rcmetar.method.references("rma.uni.random")},
#' \code{rcmetar.method.references("rma.mh")},
#' \code{rcmetar.method.references("rma.peto")},
#' \code{rcmetar.method.references("hsroc")}, and
#' \code{rcmetar.method.references("diagnostic.bivariate")} for the
#' statistical method citations used in result payloads.
#'
#' @aliases adjust.raw.data append.image.order bivariate.dx.test compute.diag.point.estimates compute.diagnostic.terms compute.npv compute.ppv create.side.by.side.plot.data create.sroc.plot.data diagnostic.bivariate.ml diagnostic.bivariate.ml.is.feasible diagnostic.bivariate.ml.parameters diagnostic.bivariate.ml.pretty.names diagnostic.fixed.inv.var diagnostic.fixed.inv.var.is.feasible diagnostic.fixed.inv.var.overall diagnostic.fixed.inv.var.parameters diagnostic.fixed.inv.var.pretty.names diagnostic.fixed.mh diagnostic.fixed.mh.is.feasible diagnostic.fixed.mh.overall diagnostic.fixed.mh.parameters diagnostic.fixed.mh.pretty.names diagnostic.fixed.peto diagnostic.fixed.peto.is.feasible diagnostic.fixed.peto.overall diagnostic.fixed.peto.parameters diagnostic.fixed.peto.pretty.names diagnostic.hsroc diagnostic.hsroc.is.feasible diagnostic.hsroc.ml.is.feasible diagnostic.hsroc.parameters diagnostic.hsroc.pretty.names diagnostic.random diagnostic.random.is.feasible diagnostic.random.overall diagnostic.random.parameters diagnostic.random.pretty.names diagnostic.transform.f get.res.for.one.diag.study multiple.diagnostic plot.bivariate plot.ppv.npv.by.prev
#' @name RCMetaR-diagnostic-methods
NULL

#' HSROC recovery, validation, and display helpers
#'
#' Support functions used by \code{diagnostic.hsroc()} to run the HSROC sampler,
#' validate generated chain files, recover from nonconverged runs, repair summary
#' intervals, and convert generated PDF plots into displayable images.
#'
#' @section Sampler output:
#' \code{hsroc.required.chain.files()} lists expected sampler output files.
#' \code{hsroc.read.chain.samples()} reads binary or text sampler output.
#' \code{hsroc.chain.validation.error()} returns a human-readable validation
#' message or \code{NULL}. \code{run.hsroc.with.recovery()} retries failed or
#' invalid sampler runs in a retry directory.
#'
#' @section Summary repair:
#' \code{hsroc.retained.iterations()} computes retained iterations after
#' burn-in and thinning. \code{hsroc.retained.chain.samples()} extracts retained
#' samples across chain directories. \code{hsroc.hpd.interval()} computes HPD
#' intervals when \pkg{coda} is available and falls back to quantile intervals.
#' \code{hsroc.repair.summary()} and
#' \code{hsroc.validate.summary.intervals()} repair and validate HSROC summary
#' tables before they are returned to the caller.
#'
#' @section Plot paths:
#' \code{hsroc.rasterize.pdf()}, \code{hsroc.display.image.path()},
#' \code{hsroc.path.in.out.dir()}, \code{hsroc.stock.pdf.plots()},
#' \code{hsroc.display.images()}, and \code{hsroc.summary.path.argument()}
#' handle file paths and plot conversions for the UI.
#'
#' @section References:
#' See \code{rcmetar.method.references("hsroc")} for the HSROC statistical
#' method citations used in result payloads.
#'
#' @aliases hsroc.chain.validation.error hsroc.display.image.path hsroc.display.images hsroc.hpd.interval hsroc.nonconverged.try.error hsroc.path.in.out.dir hsroc.rasterize.pdf hsroc.read.chain.samples hsroc.repair.summary hsroc.required.chain.files hsroc.retained.chain.samples hsroc.retained.iterations hsroc.retry.out.dir hsroc.stock.pdf.plots hsroc.summary.path.argument hsroc.validate.summary.intervals run.hsroc.with.recovery
#' @name RCMetaR-hsroc-helpers
NULL

#' Sequential, subgroup, leave-one-out, and bootstrap analyses
#'
#' Higher-level analysis wrappers that repeat a base meta-analysis over study
#' orderings, omitted studies, subgroup covariates, bootstrap replicates, or
#' multiple diagnostic analysis requests.
#'
#' @section Cumulative analyses:
#' \code{cum.ma.binary()}, \code{cum.ma.continuous()},
#' \code{cum.ma.diagnostic()}, and \code{multiple.cum.ma.diagnostic()} build
#' cumulative result lists. \code{construct.sequential.res.output()} formats
#' repeated-analysis output.
#'
#' @section Leave-one-out analyses:
#' \code{loo.ma.binary()}, \code{loo.ma.continuous()},
#' \code{loo.ma.diagnostic()}, \code{multiple.loo.diagnostic()}, and
#' \code{create.loo.side.by.side.plot.data()} support influence-style workflows.
#'
#' @section Subgroup analyses:
#' \code{subgroup.ma.binary()}, \code{subgroup.ma.continuous()},
#' \code{subgroup.ma.diagnostic()}, \code{multiple.subgroup.diagnostic()},
#' \code{get.subgroup.data.binary()}, \code{get.subgroup.data.cont()},
#' \code{get.subgroup.data.diagnostic()}, and
#' \code{create.subgroup.side.by.side.plot.data()} split data by covariate
#' levels and format subgroup results.
#'
#' @section Bootstrap analyses:
#' \code{bootstrap()}, \code{bootstrap.binary()},
#' \code{bootstrap.continuous()}, \code{boot.ma.output.results()},
#' \code{boot.meta.reg.output.results()},
#' \code{boot.meta.reg.cond.means.output.results()},
#' \code{construct.boot.res.and.value.info.for.results()},
#' \code{calc.meta.reg.coeffs.and.cis()}, and \code{plot.custom.boot()} handle
#' resampling summaries and bootstrap plots.
#'
#' @section References:
#' See \code{rcmetar.method.references("bootstrap")} for the bootstrap
#' method citations used in result payloads.
#'
#' @aliases boot.ma.output.results boot.meta.reg.cond.means.output.results boot.meta.reg.output.results bootstrap bootstrap.binary bootstrap.continuous calc.meta.reg.coeffs.and.cis construct.boot.res.and.value.info.for.results construct.sequential.res.output construct.subgroup.res.output construct.subgroup.value.info create.loo.side.by.side.plot.data create.subgroup.side.by.side.plot.data cum.ma.binary cum.ma.continuous cum.ma.diagnostic get.subgroup.data.binary get.subgroup.data.cont get.subgroup.data.diagnostic loo.ma.binary loo.ma.continuous loo.ma.diagnostic multiple.cum.ma.diagnostic multiple.loo.diagnostic multiple.subgroup.diagnostic plot.custom.boot subgroup.ma.binary subgroup.ma.continuous subgroup.ma.diagnostic update.plot.data.multiple
#' @name RCMetaR-repeated-analyses
NULL

#' Meta-regression and covariate-model helpers
#'
#' Functions that build model matrices, call \pkg{metafor} regression routines,
#' compute conditional means, and format model output for rc-metastudio.
#'
#' @section Regression wrappers:
#' \code{meta.regression()} is the primary exported meta-regression workflow.
#' \code{regression.wrapper()}, \code{g.meta.regression()},
#' \code{g.meta.regression.cond.means()},
#' \code{g.bootstrap.meta.regression()}, and
#' \code{g.bootstrap.meta.regression.cond.means()} provide lower-level wrappers
#' around model fitting and resampling.
#'
#' @section Covariate design:
#' \code{make.mods.str()}, \code{make.design.matrix()},
#' \code{get.row.vector.cat.cat()}, \code{get.row.vector.cat.cont()},
#' \code{coded.cat.mod.level()}, \code{is.single.numeric.covariate()},
#' \code{extract.cov.data()}, and \code{cond.means.info()} prepare covariate
#' model terms and conditional-mean metadata.
#'
#' @section Display and plotting:
#' \code{create.regression.display()}, \code{adjusted_means_display()},
#' \code{g.create.plot.data.reg()}, \code{g.get.scale()},
#' \code{g.round.display.zval()}, \code{meta.regression.plot()},
#' \code{categorical.meta.regression()}, and
#' \code{random.meta.regression()} build model summaries and plots.
#'
#' @section References:
#' See \code{rcmetar.method.references("meta.regression")} for the
#' meta-regression method citations used in result payloads.
#'
#' @aliases adjusted_means_display categorical.meta.regression coded.cat.mod.level cond.means.info create.regression.display extract.cov.data g.bootstrap.meta.regression g.bootstrap.meta.regression.cond.means g.create.plot.data.reg g.get.scale g.meta.regression g.meta.regression.cond.means g.round.display.zval get.row.vector.cat.cat get.row.vector.cat.cont is.single.numeric.covariate make.design.matrix make.mods.str meta.regression meta.regression.plot random.meta.regression regression.wrapper
#' @name RCMetaR-meta-regression
NULL

#' Forest render bundle and display data builders
#'
#' Functions that turn analysis results into rc-metastudio plot data,
#' metafor Forest Render Bundles, formatted labels, and result tables.
#'
#' @section Plot data:
#' \code{create.plot.data.generic()}, \code{create.plot.data.binary()},
#' \code{create.plot.data.continuous()}, \code{create.plot.data.diagnostic()},
#' \code{create.plot.data.overall()}, \code{create.plot.data.cum()},
#' \code{create.plot.data.loo()}, \code{create.plot.data.reg()},
#' \code{create.subgroup.plot.data.generic()},
#' \code{create.subgroup.plot.data.binary()},
#' \code{create.subgroup.plot.data.cont()}, and
#' \code{create.subgroup.plot.data.diagnostic()} build data structures consumed
#' by plotting functions and the metafor forest renderer.
#'
#' @section Forest plot drawing:
#' \code{rcmetar.draw.forest.plot()} and \code{sroc.plot()} draw analysis figures.
#'
#' @section Layout and labels:
#' \code{calc.plot.range()}, \code{calculate.radii()}, \code{check.label()},
#' \code{create.effect.size.label()}, \code{format.data.cols()},
#' \code{format.effect.sizes()}, \code{format.raw.data.col()},
#' \code{set.plot.options()}, and
#' \code{update.changed.plot.params()} control display formatting.
#'
#' @aliases calc.plot.range calculate.radii check.label create.effect.size.label create.plot.data.binary create.plot.data.continuous create.plot.data.cum create.plot.data.diagnostic create.plot.data.generic create.plot.data.loo create.plot.data.overall create.plot.data.reg create.subgroup.plot.data.binary create.subgroup.plot.data.cont create.subgroup.plot.data.diagnostic create.subgroup.plot.data.generic format.data.cols format.effect.sizes format.raw.data.col create.overall.display create.subgroup.display create.summary.disp pretty.metric.name set.plot.options sroc.plot update.changed.plot.params
#' @name RCMetaR-plotting
NULL

#' Data completion, transformations, and scale helpers
#'
#' Functions that impute missing fields, rescale confidence intervals, calculate
#' estimates and variances, and identify the transformation scale for a metric.
#'
#' @section Imputation and consistency checks:
#' \code{gimpute.bin.data()}, \code{gimpute.cont.data()},
#' \code{gimpute.diagnostic.data()}, \code{fillin.cont.1spell()},
#' \code{fillin.cont.AminusB()}, \code{fillin.missing.effect.quantity()},
#' \code{check.1spell.res()}, \code{isnt.null()}, and \code{isnt.na()} fill or
#' validate partial study rows.
#'
#' @section Estimate and scale helpers:
#' \code{calc.est.var()}, \code{calc.ci.bounds()},
#' \code{rescale.effect.and.ci.conf.level()}, \code{get.transform.name()},
#' \code{get.scale()}, \code{metric.is.log.scale()},
#' \code{metric.is.logit.scale()}, \code{metric.is.arcsine.scale()}, and
#' \code{metric.is.freeman_tukey.scale()} support transformed metrics.
#'
#' @section Global confidence level:
#' \code{validate.conf.level()}, \code{set.global.conf.level()},
#' \code{get.global.conf.level()}, and \code{get.mult.from.conf.level()} manage
#' the confidence level multiplier used across display and analysis code.
#'
#' @aliases calc.ci.bounds calc.est.var check.1spell.res fillin.cont.1spell fillin.cont.AminusB fillin.missing.effect.quantity get.global.conf.level get.mult.from.conf.level get.scale get.transform.name gimpute.bin.data gimpute.cont.data gimpute.diagnostic.data isnt.na isnt.null metric.is.arcsine.scale metric.is.freeman_tukey.scale metric.is.log.scale metric.is.logit.scale rescale.effect.and.ci.conf.level set.global.conf.level validate.conf.level
#' @name RCMetaR-data-completion
NULL

#' Output, persistence, and formatted summary helpers
#'
#' Helpers that format RCMetaR result objects for display, write results to
#' files, and preserve plot data alongside analysis parameters.
#'
#' @section Display helpers:
#' \code{print.summary.display()} and \code{print.summary.data()} provide S3
#' print methods for RCMetaR summary objects. \code{create.repeat.string()},
#' \code{pad.with.spaces()}, \code{round.display()},
#' \code{capture.output.and.collapse()}, \code{results.short.list()}, and the
#' \code{*.value.info()} helpers format display rows and labels.
#'
#' @section Persistence:
#' \code{save.plot.data()}, \code{save.plot.data.and.params()},
#' \code{save.data()}, and \code{write.results.to.file()} write generated data,
#' analysis parameters, and formatted summaries to disk.
#'
#' @aliases capture.output.and.collapse create.repeat.string cumul.rma.mh.value.info cumul.rma.uni.value.info loo.rma.mh.value.info loo.rma.uni.value.info pad.with.spaces print.summary.data print.summary.display results.short.list rma.uni.value.info round.display save.data save.plot.data save.plot.data.and.params write.results.to.file
#' @name RCMetaR-output-helpers
NULL

#' Permutation test helpers
#'
#' Functions for permutation-based meta-analysis and meta-regression workflows.
#' They generate permuted results and format permutation distributions for the
#' RC MetaStudio display layer.
#'
#' @aliases permuted.ma permuted.meta.reg permutest.value.info
#' @name RCMetaR-permutation
NULL
