# RC MetaStudio

RC MetaStudio supports evidence synthesis and the interpretation of meta-analysis results.

## Language

**Small-study effects analysis**:
A guided analysis of associations between study size or precision and observed effects. Its results can suggest several causes and do not establish that publication bias exists.
_Avoid_: Publication bias analysis, publication-bias test

**Publication Bias**:
The short user-interface label that helps users find the small-study effects analysis. It is a navigation label, not the interpretation of the analysis.
_Avoid_: Proof of publication bias, bias detection

**Primary asymmetry test**:
The one method that the small-study effects analysis recommends for the current effect measure, study design, and available data. Other reported methods do not vote with it to produce a verdict.
_Avoid_: Best test, publication-bias test

**Exploratory asymmetry test**:
An optional method retained for context despite limitations that prevent it from being the primary asymmetry test.
_Avoid_: Confirmatory test, sensitivity vote

**Pooled display model**:
The model whose estimate can appear on a funnel plot or in a pooled-estimate comparison. It does not configure the distinct models and inference rules used by asymmetry tests.
_Avoid_: Reference model, test model

**Eligible study set**:
The included studies that supply every input required by a selected method. Release 1 does not silently reduce this set for individual methods.
_Avoid_: Available cases, implicit complete cases

**Trim-and-fill sensitivity analysis**:
An assumption-dependent analysis that estimates and adds studies to a funnel plot under a specified asymmetry scenario. Its augmented estimate is not a corrected or more valid pooled effect.
_Avoid_: Bias correction, adjusted true effect

**Extrapolated infinite-precision estimate**:
An exploratory regression estimate evaluated where its standard-error predictor approaches the large-study limit. It is not a corrected estimate of the true effect.
_Avoid_: Regression limit estimate, bias-adjusted estimate

**Deeks effective-sample-size funnel**:
The diagnostic small-study-effects plot of log diagnostic odds ratio against inverse square-root effective sample size, with the Deeks weighted regression line. It is distinct from an ordinary effect-versus-standard-error funnel and has no triangular pseudo-confidence region.
_Avoid_: Diagnostic funnel plot, contour-enhanced DOR funnel

**Deeks test (`meta` implementation)**:
The diagnostic primary asymmetry test supplied by the pinned `meta` package. Results disclose the package version and actual regression predictor because this implementation differs from the equation in the primary paper.
_Avoid_: Exact Deeks-paper reproduction, generic diagnostic Egger test

**Studies with any zero cell**:
A continuity-correction target that adjusts every cell in each study containing at least one zero cell.
_Avoid_: Only zero-event studies, only zero cells

**All studies**:
A continuity-correction target that adjusts every cell in every study unconditionally.
_Avoid_: All studies if any zero exists

**All studies if any zero exists**:
A continuity-correction target that adjusts every cell in every study only when at least one included study contains a zero cell.
_Avoid_: All studies

**Reitsma bivariate model**:
The joint random-effects model of sensitivity and false-positive rate used for count-based diagnostic meta-analysis. It has an equivalent HSROC parameterization but does not reproduce the removed Bayesian HSROC estimator.
_Avoid_: Reitsma / HSROC method, Bayesian HSROC

**Summary operating point**:
The Reitsma model's paired summary sensitivity and specificity estimates.
_Avoid_: Summary accuracy, pooled accuracy

**Sampling-based summary ratios**:
The mean, median, and equal-tail interval for positive likelihood ratio, negative likelihood ratio, and diagnostic odds ratio returned by `mada::SummaryPts()` for an intercept-only Reitsma fit.
_Avoid_: Reitsma-derived summary ratios, ratios at the summary operating point

**Univariate pooled ratios**:
Likelihood-ratio or diagnostic-odds-ratio estimates from a model that pools one diagnostic measure separately rather than fitting sensitivity and specificity jointly.
_Avoid_: Sampling-based summary ratios

**False-positive rate**:
The proportion of participants without the target condition who receive a positive test result. The Reitsma bivariate model uses it as the complement of specificity.
_Avoid_: False-positive probability

**Joint prediction region**:
The region for the underlying paired sensitivity and specificity of a new study under the fitted Reitsma bivariate model. It does not predict observed counts or include a new study's binomial sampling error.
_Avoid_: Confidence region, marginal prediction intervals

**Reitsma bivariate meta-regression**:
A Reitsma bivariate model in which selected study characteristics jointly explain sensitivity and false-positive rate. It is distinct from separate univariate meta-regressions of sensitivity, specificity, or diagnostic odds ratio.
_Avoid_: Adjusted Reitsma model, diagnostic meta-regression

**Moderator block test**:
A likelihood-ratio test that removes every sensitivity-side and false-positive-rate-side coefficient belonging to one moderator, including all levels of a categorical moderator.
_Avoid_: Coefficient test, moderator Wald test

**SROC AUC**:
The area under the Reitsma summary ROC curve evaluated over false-positive rates from 0.01 through 0.99.
_Avoid_: Full AUC, ROC AUC

**Normalized partial SROC AUC**:
The `mada`-reported normalized area under the Reitsma summary ROC curve over observed false-positive-rate bounds truncated to 0.01 through 0.99. The package calculates it on a fixed grid, so it is an approximation rather than an exact normalized trapezoidal area.
_Avoid_: Partial AUC, observed AUC

**Statistical authority package**:
The field-maintained R package whose estimator, inference, and reported numerical results define an RC MetaStudio analysis. RC MetaStudio validates inputs and presents package results but does not silently replace or correct their statistical calculations.
_Avoid_: Gold-standard package, calculation backend

**Residual diagnostic I² estimates**:
The Zhou–Dendukuri and Holling I² values returned by `mada` for unexplained heterogeneity after fitting a Reitsma bivariate meta-regression. They are a named family of estimates, not one generic I² statistic.
_Avoid_: Adjusted I², meta-regression I²

**Moderator coefficient plot**:
An editable forest plot of moderator coefficients for one modeled side of a Reitsma bivariate meta-regression. Sensitivity and specificity use separate plots.
_Avoid_: Meta-regression bubble plot, two-panel coefficient plot
