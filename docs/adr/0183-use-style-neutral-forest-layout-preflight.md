# Use Style-Neutral Forest Layout Preflight

Status: accepted — refines ADR 0179, ADR 0180, and ADR 0182.

The metafor Forest Renderer should use a style-neutral Forest Layout Preflight before drawing with `metafor::forest()`. The preflight owns shared measurement and planning primitives — device size, text scale, row positions, plot limits, annotation positions, header/footer reserves, and axis spacing — while each Forest Plot Style supplies only its column templates, labels, footer blocks, and style-specific constraints. This keeps RCMetaR's forest plots based on `metafor` while preventing responsive sizing logic from being duplicated across Default, RevMan, BMJ, cumulative, leave-one-out, and future style modules.

## Consequences

- The renderer remains Metafor-first: Forest Layout Preflight plans arguments and surrounding annotations for `metafor::forest()` rather than drawing custom forest marks.
- Shared layout logic belongs in a dedicated forest preflight module instead of being scattered through `forest_metafor.r` and style files.
- Style modules remain shallow templates over shared primitives; they should not each implement independent device sizing, row spacing, axis-footer, or text-scale algorithms.
- Responsiveness means fit-to-content first, not arbitrarily shrinking text: preflight should grow device width/height and wrap eligible text before reducing `cex`, and any shrinkage should stay within a journal-readable range with explicit warnings when the floor is reached.
- Device growth is bounded: preflight should cap exported dimensions at documented practical maxima, keep content visible within those caps, and attach explicit layout warnings when a cap or text-size floor affects the result instead of silently clipping.
- Direct Effect-Size Entry is first-class for plotting: preflight should omit raw-data columns that are unavailable, avoid reserving blank space for entirely absent column groups, and allow mixed raw/direct rows without back-calculating values only for presentation.
- Layout diagnostics are severity-scored: routine wrapping and spacing choices are QA/test metadata, quality-affecting caps or text-size floors are user-visible warnings, and missing essential effect/interval inputs are render errors.
- Preflight is deterministic for the same Forest Render Bundle, Forest Plot Style, export format, size policy, and font policy. Measurement should run on a controlled scratch graphics device and must not depend on the current interactive graphics device, previous `par()` state, or plot-pane dimensions.
- The Forest Layout Plan is ephemeral and regenerated per render/export target; it should not be persisted in `.plotdata` or project files, because device caps, font metrics, and export policy can legitimately change without changing Analysis Behavior.
- GUI preview, file export, and QA rendering use the same preflight engine with different explicit size policies (`preview`, `export`, `qa`) rather than separate renderers.
- The migration to Forest Layout Preflight is a refactor-first, QA-guided architectural change delivered as one cohesive commit. Plot output is not frozen during the refactor; visual changes are accepted when the forest visual QA matrix shows improved journal-ready layout without clipping, overlap, bad whitespace, or unreadable text.
- The first architectural commit covers every current forest plot variant — standard, cumulative, and leave-one-out across binary, continuous, and diagnostic data — for both Default and RevMan styles, including sparse/direct-effect and stress visual QA cases.
- The preflight style-constraint interface should be ready for BMJ and future metafor-based styles, but BMJ rendering remains deferred unless a maintained BMJ renderer already exists.
- Preflight measurement stays base-graphics-native: use controlled graphics devices, `strwidth`/`strheight`, and explicit base coordinate conversions so measurement matches the `metafor::forest()` drawing path. Do not introduce `grid`, `gridGraphics`, or `ggplotify` as layout dependencies for this layer.

## Done Criteria

- A dedicated forest preflight module creates Forest Layout Plans consumed by Default and RevMan renderers.
- Shared sizing, row, column, axis, and footer calculations move out of scattered style-specific helpers where practical.
- No `gridGraphics` or `ggplotify` dependency is added for layout.
- Plan-level tests cover invariants for dimensions, rows, columns, text scale, warnings, and sparse/direct-effect inputs.
- Render smoke tests and the forest visual QA matrix cover standard, cumulative, and leave-one-out plots across binary, continuous, and diagnostic data for Default and RevMan styles.
- Contact sheets and individual problem plots show no obvious clipping, overlap, bad whitespace, asymmetry, unreadable text, or marker/CI/diamond color inconsistency.
- CONTEXT language and ADR 0183 remain aligned with the implementation.
