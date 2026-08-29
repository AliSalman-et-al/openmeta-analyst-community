# Domain vocabulary

Use these terms in code, tests, documentation, and issues. Keep external field names unchanged when an R function or the versioned project schema owns them.

- **Project**: the portable document saved as an `.rcms` archive. A project contains an analysis dataset and the application state needed to reopen it.
- **Analysis dataset**: the in-memory collection of studies, outcomes, follow-ups, groups, and covariates.
- **Study**: one included or excluded research record. A study stores metadata, covariate values, and analysis units.
- **Outcome**: a measured result with a binary, continuous, diagnostic, or other data type.
- **Follow-up**: the time point for an outcome. Do not use `time point` as a second name in new APIs.
- **Group**: one arm within an analysis unit, including control or diagnostic groups.
- **Analysis unit**: one study outcome at one follow-up. It owns the raw group data and calculated effects for that combination.
- **Covariate**: a study-level continuous or categorical value used by subgroup analysis or meta-regression.
- **Metric**: the statistical measure selected for an analysis, such as odds ratio or standardized mean difference.
- **Effect**: an estimate and its uncertainty for one metric and group comparison.

Use full domain words in Python names. For example, use `confidence_level`, `covariate`, and `diagnostic_data`. Preserve schema keys such as `conf.level` only at the R boundary.
