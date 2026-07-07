# Forest Renderer Column Sets, Device Sizing, and Module Layout

Status: accepted — implementation spec for ADR 0179 and ADR 0180.

This ADR fixes the per-family × style column sets, the device-sizing method, and the R module layout for the metafor Forest Renderer.

## Column sets

**Default (metafor)** is a metafor-idiomatic redesign, not a reproduction of the legacy column set: study label | raw-count `ilab` columns | metafor's built-in effect/CI annotation, with the raw counts drawn per family (binary two-group events/total, diagnostic counts, continuous optional mean/SD/N). Its per-style control panel exposes metafor-native toggles for those `ilab` columns rather than the legacy col1–4 abstraction.

**RevMan and BMJ** are full faithful layout templates with per-family `ilab` column sets:
- Binary: Experimental events/total, Control events/total.
- Continuous: Experimental Mean/SD/Total, Control Mean/SD/Total.
- Diagnostic (in-house, no official layout exists): all four `TP`/`FP`/`FN`/`TN` cells as separate columns, matching RevMan's diagnostic-test-accuracy table convention, so the columns stay constant across Sens/Spec/DOR/PLR/NLR.

Both styles additionally render the recognizable faithful blocks for every family: a weight-% column, subgroup subtotals with diamonds, a heterogeneity block (τ²/χ²/df/P/I²), and a test-for-overall-effect line (Z, P). Directional "Favours A / Favours B" axis labels are rendered **only for binary and continuous**, where a favoring direction exists; diagnostic uses a plain metric axis label instead, rather than inventing directional wording RevMan/BMJ do not define.

## Device sizing

The renderer computes PNG/PDF device dimensions with a **measure-then-render two-pass**: open an off-screen scratch device (reusing the existing `INTER` scratch-device pattern), `strwidth`-measure the study labels and `ilab` columns at the target `cex`, compute the exact width (labels + `ilab` columns + plot region + annotation) and height (row count × row height + margins), then open the real device at that size and draw. This preserves today's fit-to-content behavior and avoids clipping on arbitrary datasets, since `metafor::forest()` draws into a fixed-size base-graphics device and does not auto-size it.

## Module layout

The renderer is added as **style-split** private R files behind the stable `rcmetar.draw.forest.plot` facade (the package uses roxygen2 with no `Collate`, so files source alphabetically and only exported functions need `#' @export`):
- `r/RCMetaR/R/forest_metafor.R` — Metafor-backed forest renderer entrypoint, support checks, bundle construction, shared data/appearance primitives, and style dispatch.
- `r/RCMetaR/R/forest_layout_preflight.R` — shared measurement and layout planning for Metafor-backed forest styles.
- `r/RCMetaR/R/forest_style_default.R` — the Default/plain Metafor style templates and renderer.
- `r/RCMetaR/R/forest_style_revman.R` — the RevMan faithful templates.
- `r/RCMetaR/R/forest_style_bmj.R` — the BMJ faithful templates.

The legacy custom engine, SROC, meta-regression scatter, and the legacy `two.forest.plots` stay in `plotting.R` until the ADR 0179 phases retire them.

## Consequences

- The builder computes the full faithful `ilab`/weights/subgroup spec per style so the renderer stays a pure placer; a style change rebuilds the spec through the existing regenerate path.
- Continuous gains Mean/SD/N columns under RevMan/BMJ (and optionally Default), surfacing data the legacy continuous plot never displayed.
- Headless render-smoke tests (ADR 0179) assert the expected `ilab` headers and blocks per style × family, giving the column contract automated coverage without pixel diffs.
