# Adopt mada's Reitsma Model for Diagnostic Bivariate Meta-Analysis

Status: proposed — deferred until the identity/layout migration stabilizes (blocked by ADR 0175 and ADR 0172).

RC MetaStudio should replace its two count-based bivariate diagnostic methods — the custom `lme4::glmer` bivariate model (`diagnostic.bivariate.ml`) and the Bayesian MCMC `HSROC` sampler (`diagnostic.hsroc`) — with a single method backed by `mada::reitsma()`, the frequentist bivariate model of Reitsma et al. (2005). We choose this because `mada` is the maintained standard package for diagnostic accuracy meta-analysis, its documentation establishes that the Reitsma bivariate model is statistically equivalent to the Rutter & Gatsonis (2001) HSROC, and one `reitsma()` fit supplies everything both current methods produce (summary sensitivity/specificity, HSROC parameters, SROC curve) plus AUC, prediction regions, and I² heterogeneity. `mada` is current on CRAN and needs no compilation, so adopting it also lets us drop `HSROC` (an archived CRAN package requiring exact-version pinning), `lme4`, `pdftools`, and `coda`, deleting roughly 750 lines of sampler retry/validation/rasterization scaffolding.

The two current menu entries collapse into one method ("Bivariate (Reitsma) / HSROC"). This is a deliberate method change, not a compatibility-preserving port: the frequentist Reitsma fit produces different numbers than the current models, and the Bayesian HSROC path's MCMC convergence diagnostics and credible intervals are lost. Because the Reference Implementation is retired as the oracle (ADR 0068/0069), the resulting drift is re-blessed against the Modern Behavior Baseline rather than logged as a legacy Compatibility Exception. Legacy Project Data Compatibility is unaffected: `.rcms` files persist only the dataset, and analysis methods are resolved live.

## Consequences

- **Supersedes** ADR 0072, ADR 0075, ADR 0076, and ADR 0077 (all HSROC-archive-specific) once executed.
- **Deferred by** ADR 0172 (keep R dependency policy stable) and ADR 0175 (freeze statistical feature scope) — this work must not land during the current migration.
- Execution is planned as two phases: add `diagnostic.reitsma` (with `mada`, `mvmeta`, `ellipse`, `mvtnorm`) alongside the existing methods and verify against a captured Modern Behavior Baseline; then collapse the menu and remove the old methods and their dependencies.
- Diagnostic golden baselines are regenerated; the reitsma fit is deterministic, and pooled LR+/LR−/DOR are made reproducible by seeding `mada::SummaryPts`.
