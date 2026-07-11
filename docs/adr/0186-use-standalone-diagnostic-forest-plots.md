# Use Standalone Diagnostic Forest Plots

Status: accepted - supersedes ADR 0181.

Diagnostic analyses should emit one standalone Forest Plot Artifact per metric.
Sensitivity, Specificity, Positive Likelihood Ratio, and Negative Likelihood
Ratio therefore each own a Forest Render Bundle, output path, result title, and
plot-parameter path.

The twin-panel composition from ADR 0181 made two metrics share one render
contract. That special case prevented ordinary Edit Plot behavior and required
separate rendering, persistence, and export paths. Independent artifacts use
the same metafor Forest Renderer and Plot Options Surface as other forest plots
without changing the statistical estimates.

## Consequences

- Sensitivity/Specificity and NLR/PLR appear as four independently editable and
  exportable forest plots when all four metrics are requested.
- Multi-metric, leave-one-out, and subgroup diagnostic workflows package each
  metric independently.
- The side-by-side renderer, paired plot-data builders, title-based GUI
  exclusions, and special export flag are retired.
- The shared SROC artifact remains available for non-bivariate
  Sensitivity/Specificity analyses.
