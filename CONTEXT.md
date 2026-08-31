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
An exploratory regression estimate evaluated where its precision predictor approaches the large-study limit. It is not a corrected estimate of the true effect.
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
