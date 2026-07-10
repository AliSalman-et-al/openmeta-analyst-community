# Compose Side-by-Side Forest Plots with base-graphics layout(), Not patchwork

Status: superseded by ADR 0186.

The Twin-Panel Side-by-Side Forest Plot (diagnostic Sens|Spec and PLR|NLR, currently `two.forest.plots`) should be rebuilt on the metafor Forest Renderer by composing two `metafor::forest()` panels with base-graphics `layout()`/`par(mfrow=c(1,2))` and a matched `ylim`/`rows`, rather than with the `patchwork` package. `patchwork` was evaluated because it offers an ergonomic composition API, but it is "the composer of ggplots": its panel-alignment works on ggplot2 gtables, and base-graphics plots can only be embedded via `wrap_elements(full = ~ forest(...))`, which requires `gridGraphics` and captures each panel as an opaque grob with no cross-panel row alignment. Against base-graphics `forest()`, `patchwork` therefore reduces to a costlier `par(mfrow)` while adding two new dependencies (`patchwork`, `gridGraphics`).

The alignment that matters here — study rows lining up across both panels — is achieved deterministically without `patchwork`, because both twin panels always contain the same studies in the same order: equal-height `layout()` regions with a shared `ylim` and identical `rows=` place the rows identically by construction. Realizing `patchwork`'s actual benefit would require rendering the twin panels as ggplot2 forest plots (e.g. `metaviz::viz_forest` or a hand-built ggplot), which would reopen ADR 0179, split the renderer between base-graphics single plots and ggplot twin panels, and force ggplot reimplementations of the RevMan/BMJ templates — a cost with no offsetting benefit for symmetric same-study panels.

## Consequences

- No new dependency: `ggplot2` is already bundled but unused by RCMetaR; `patchwork` and `gridGraphics` are not added, and the renderer stays uniformly base-graphics per ADR 0179.
- The final ADR 0179 phase that retires `two.forest.plots` implements the twin panel as two `forest()` calls under `layout()`, with device width summed across panels and height driven by the shared row count.
- Whether the RevMan/BMJ styles extend to the twin panel remains the deferred decision noted in ADR 0180; the base-graphics composition does not constrain that either way.
- `grid` remains removable once this phase lands, as already noted in ADR 0179.
