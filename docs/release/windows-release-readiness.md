# Windows Release Readiness

This note describes the maintained Python 3 and Qt 5 Windows distributable.

## Run the Windows Distributable

1. Download `RCMetaStudio-windows-x64.zip` from the package verification workflow artifact.
2. Extract the ZIP to a writable folder.
3. Run `LaunchRCMetaStudio.bat`.

The launcher starts `RCMetaStudio.exe` and opens the bundled `sample_projects\amino.rcms` project so the standard binary analysis GUI slice can be checked immediately.

## Compatibility Promises

- Analysis: golden analysis CI remains the compatibility oracle for preserved statistical behavior, with explicit numeric tolerances and documented exceptions for any accepted drift.
- R Stack: normal desktop users should not need to manually install R or R packages before running the Windows distributable; required R pieces must be bundled or launched through an automated app-managed setup.
- R behavior: Release Cutover preserves Reference Implementation R-backed statistical behavior; broad R modernization is post-cutover unless required for the bridge or packaging.
- GUI: milestone 1 preserves required workflows and recognizable layouts, not pixel-perfect Qt 4 rendering.
- `.rcms`: representative existing `.rcms` files must open without user-visible migration steps, and selected project files must round-trip successfully before release.
- Help and legal: RC MetaStudio does not bundle the retired help system; provenance, license, warranty, and issue feedback surfaces are available through About/Legal and static GitHub links.

## Out of Scope

- Deferred network meta-analysis is not part of milestone 1.
- Deferred non-Windows packaging means the first distributable target is Windows.
- Broad R Stack changes and broad GUI redesign are deferred unless required by a compatibility slice.

## Cutover Readiness

Issue #45 closed the Release Cutover readiness loop. Every cutover gate in [Windows Cutover Checklist](windows-package-cutover-checklist.md) is satisfied with recorded evidence: non-pending workflow traceability, accepted-only exception manifests, a published golden analysis compatibility report, GUI Verification Evidence for required slices, `.rcms` round-trip and advanced-analysis coverage from issue #43, and the Windows distributable and user documentation from issue #44.

Closing the loop made the Windows build eligible to be accepted as the release path. This readiness document records that the gates are met.

## Release Path Status

The Python 3 and PyQt5 Windows build is the maintained release path. The old Python 2 and PyQt4 release/build path has been retired.
