# Fit Vector Plot Artifacts to the Results Window Viewport

Status: accepted.

Supersession note: ADR 0195 supersedes the maximize-on-every-open policy. The plot-fit and responsive viewport rules in this ADR remain active.

The Results Window opens maximized, and every vector Plot Artifact uses one authoritative fit-to-viewport routine for initial creation, show/resize, splitter movement, and in-place regeneration. The routine preserves aspect ratio and the existing 4× scale cap; centralizing the scale calculation keeps the reader view responsive without changing Analysis Behavior or Plot Artifact content.

## Considered Options

- Keep independent constructor-time and resize-time calculations: rejected because the first render and later regeneration can disagree about the available viewport.
- Let each generated SVG choose its own display size: rejected because SVG output dimensions are not a reliable proxy for the available Results Window viewport.

## Consequences

- The Results Window follows the same maximize-on-open policy as the main application window.
- Layout reflow remains responsible for moving later sections when a vector plot changes height, while the shared fit routine owns the target scale.
- The 4× cap remains a safety bound for very wide viewports and very small native SVGs.
