# Use metafor regplot for Meta-Regression Bubble Plots

Status: accepted.

RC MetaStudio should render single-continuous-covariate Meta-Regression Bubble Plots with `metafor::regplot()` from the fitted `rma` object instead of maintaining the legacy hand-drawn scatterplot. The persisted plot data becomes a self-contained bubble render bundle carrying the `rma` result, moderator metadata, effects, style, and params, while the exported `rcmetar.draw.regression.plot()` facade stays stable for saved-plot redraw and PDF/PNG export.

## Consequences

- Default, RevMan, and BMJ Bubble Plot Styles are presentation variants over the same metafor-backed analysis object; they do not change Meta-Regression Analysis Behavior.
- Study labels are always disabled for Bubble Plots because point labeling is inherently collision-prone in dense meta-regression plots and is not required for journal-ready presentation.
- Confidence bands, prediction intervals, transformed display axes, precision-scaled bubbles, legends, and export sizing are delegated to `metafor::regplot()` where possible, with RCMetaR owning only style arguments, device export, and compatibility fallbacks.
- Older saved regression plot data without an embedded `rma` object remains redrawable through the legacy scatter fallback, but newly generated plots use the metafor bundle.
