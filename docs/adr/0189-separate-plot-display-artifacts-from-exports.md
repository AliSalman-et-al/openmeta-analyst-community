# Separate Plot Display Artifacts from User Exports

Status: accepted.

Each vector Plot Artifact has an internal SVG display artifact in managed analysis storage, carried explicitly across the Analysis Adapter boundary separately from the requested output file. The Results Window uses that explicit display artifact for Qt SVG rendering; it does not infer a sidecar path from the output extension.

User exports remain format-clean. Rendering a PNG, PDF, or TIFF outside the analysis output lifecycle uses a temporary SVG for conversion and removes it after export. Regenerating the original analysis output updates its internal SVG display artifact in place.

## Considered Options

- Persist an SVG beside every requested output: rejected because user exports must not create unrequested sidecar files.
- Infer an SVG by replacing the returned output extension: rejected because the Analysis Adapter must declare artifact identity explicitly and raster-only plots need an unambiguous fallback.
- Display only the requested raster output: rejected because destructive constructor-time raster scaling cannot provide responsive, lossless Results Window resizing.

## Consequences

- Forest, diagnostic forest, and Meta-Regression Bubble Plot results carry an optional display-artifact mapping keyed by the same titles as their Plot Artifacts.
- Vector display artifacts use the authoritative viewport routine from ADR 0188.
- Raster-only Plot Artifacts retain their original pixmap and regenerate viewport-sized previews from that source on resize.
- Export and display lifecycles can evolve independently without weakening the Plot Capability Descriptor contract.
