# Use mada Reitsma for joint diagnostic models

RCMetaR will replace its exact-binomial bivariate model and Bayesian HSROC sampler with `mada::reitsma()` as the sole count-based joint sensitivity-specificity model. Standard analysis and additive diagnostic meta-regression will ship in the same release, with no aliases, parameter translation, hidden retries, or fallback estimators; separate univariate diagnostic models remain available. Reitsma consumes raw diagnostic counts and is an explicit exception to ADR-0003, which governs methods that consume derived effects.

Reported fits default to REML and may use ML, while overall and moderator block likelihood-ratio tests always compare separate ML fits over one frozen study set. Meta-regression rejects incomplete diagnostic counts, permits user-confirmed exclusions for missing selected moderators, and does not report conditional summary operating points or SROC measures without a specified moderator profile.

RCMetaR will report `mada`'s named diagnostic I-squared estimates and disclose the package version and methodological uncertainty around those statistics. This accepts a deliberate change in estimator and numerical results in exchange for one maintained model with SROC, prediction, meta-regression, and heterogeneity support.
