# Native Qt6 Results evidence

Issue #338 restores the post-analysis reader through the real PyQt6 Results
Window and Network View. The maintained evidence deliberately compares
workflow and artifact semantics, not Qt5 pixels.

`scripts/native_results_smoke.py` launches a fresh native `qwindows` process at
effective device-pixel ratios 1.0, 1.25, 1.5, and 1.75. It constructs the real
Results Window with summary text, references, a validated Plot Capability
Descriptor, and an SVG Plot Artifact containing readable text and a confidence
interval. It also opens the real Network View with its typed outcome and
follow-up state. Each process captures both visible windows and records:

- the effective device-pixel ratio and native QPA;
- Results navigation and the authenticated Plot Capability Descriptor;
- exact summary/reference text plus the SVG artifact size and SHA-256;
- the SVG display ratio, which must remain 2:1 at every scale;
- Network View selector state and scene item count; and
- canonical relative PNG paths, exact byte sizes, SHA-256 hashes, decoded pixel
  dimensions, logical frame geometry, screen geometry, and physical crop
  coordinates; and
- the capture method, compositor retry count, and a nonblank pixel-variation
  assertion for each window.

Every screenshot is a crop of `QScreen.grabWindow(0)`, not a client-only
`QWidget.grab()`. The client grab is used only as a paint-readiness probe. The
smoke waits for Windows to expose a bounded normal window, converts its logical
frame to physical pixels through the audited half-up geometry boundary, and
retries a blank or incomplete compositor frame at most five times. Exhausting
that budget fails the run rather than accepting weak evidence.

The parent process first measures the host's native device-pixel ratio and uses
Qt's pass-through scale policy to reach each exact target. This keeps native
platform scaling enabled and avoids assuming that a developer or CI display is
configured at 100 percent. `--validate-only` re-authenticates a downloaded or
relocated evidence bundle without opening a window. Validation rejects absolute,
noncanonical, traversing, non-PNG, corrupted, blank, resized, re-encoded, or
metadata-tampered captures. It recomputes hashes and byte sizes, decodes each
PNG explicitly, and derives the expected physical frame from the recorded
logical geometry and DPR instead of trusting the manifest.

All evidence numbers pass through central strict validators. Integer fields do
not accept booleans or floating-point lookalikes; numeric fields reject
booleans, strings, nulls, NaN, and either infinity. Sizes and DPRs must be
positive, retry counts remain within the five-attempt capture budget, and both
logical and physical rectangles must fit their recorded screens. The requested
scale encoded by each evidence filename is the record's one authoritative
expected DPR. The nominal `scale_factor`, top-level window DPR, every compositor
capture DPR, and every captured pixmap's internal DPR must each be directly
within `0.01` of that target. As a second defense, the maximum and minimum of
all those recorded values may not span more than `0.01`; chained near-matches
cannot drift across a wider band. Physical crops are derived from the exact
validated DPR of their own capture rather than from the nominal target. The
`0.01` tolerance accounts only for Qt's floating-point DPR reporting. The JSON
loader also rejects Python's non-standard `NaN` and `Infinity` constants before
field validation.

The source gate supplements this evidence with the ported Results and Network
View GUI suites, strict `ty` checking, the existing Plot Capability Descriptor
tests, Golden Analysis compatibility, and Full R Stack Evidence. The visible
smoke is packaged-artifact-ready: later packaging qualification can run the
same semantic validator against evidence emitted by the exact downloadable
artifact rather than changing its acceptance vocabulary.
