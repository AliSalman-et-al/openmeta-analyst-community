# Adaptive-Layout Native Package Evidence

Issue [#306](https://github.com/AliSalman-et-al/rc-metastudio/issues/306) is the
supported-platform release gate for the adaptive-layout rewrite in PRD
[#293](https://github.com/AliSalman-et-al/rc-metastudio/issues/293). Offscreen Qt
tests remain required, but they are not native rendering evidence.

## Evidence contract

Run the **Package Verification** workflow with both `build_windows` and
`build_macos` selected. Each supported package must complete its packaged smoke
checks and its fail-closed native evidence mode. The evidence mode rejects
offscreen/minimal Qt plugins. At process scale factors 1.0 and 1.5 it captures
both Workspace surfaces at exact 800 by 600 constrained and 1024 by 640
full-usability client viewports. Content-driven Workflow, Transactional, and
Transient surfaces are captured once at their preferred size while owned by the
constrained 800 by 600 Workspace; they are never stretched to Workspace sizes.

The workflow publishes these 30-day artifacts:

- `RCMetaStudio-windows-x64-adaptive-layout-evidence`
- `RCMetaStudio-macos-x64-adaptive-layout-evidence`

Each successful scale directory contains exactly `manifest.json`,
`HUMAN_REVIEW.md`, the intrinsic-ratio PNG, and seven native screenshots. A
failure may also leave an automation log. The package wrapper independently
validates exact scenario/file membership, PNG readability and nonblank content,
pixel dimensions, frame-geometry/DPR consistency, exact viewport and owner
relationships, archetypes, available-screen containment, and every SHA-256
digest. Each screenshot is a deterministic owning-screen crop of the complete
native `frameGeometry`, including the platform titlebar and frame; a separate
client paint probe proves that the application content was painted before the
frame capture. The
manifest records the
Qt platform plugin, system font, logical DPI, device-pixel ratio, owning screen,
window frame/client geometry, table and splitter state, remembered geometry,
runtime resize behavior, an Intrinsic-Ratio Artifact ratio check, screenshot
hashes, and capture method.

## Human review

Download both evidence artifacts and complete every `HUMAN_REVIEW.md` checklist.
Review the screenshots visually; do not add a pixel-diff gate. Confirm:

- professional reflow and appropriate spacing;
- readable Required Content and reachable primary actions;
- undistorted visual artifacts;
- native fonts, icons, paint, and window chrome; and
- consistent behavior across the two supported platforms and both scales.

Any platform defect must be fixed and both package lanes rerun. Record the final
workflow run URL, artifact names, reviewer, date, and verdict in PRD #293 and
issue #306. A source commit or a Windows-only run is not sufficient to mark the
native package evidence complete.

## Current evidence status

The current local Windows run is implementation evidence only. Until a committed
revision is pushed and both native jobs finish, Windows x64 and macOS Intel x64
release evidence remain **pending**, and human review remains **required**.
