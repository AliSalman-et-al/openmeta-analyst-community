# Modern Windows Cutover Checklist

The modern Python 3 and Qt 5 path has replaced the legacy release path after satisfying every gate below.

- [x] required Modern CI Path gates pass on Windows, the Release Cutover platform for the first modern release.
- [x] the Reference Implementation outputs needed for compatibility were captured before retiring the legacy CI/build path.
- [x] a Comprehensive Golden Baseline has been captured from the Reference Implementation before further behavior-changing port work.
- [x] golden analysis CI passes against reference outputs and publishes the compatibility report.
- [x] every Release Cutover workflow in the [User-Facing Workflow Inventory](user-facing-workflow-inventory.md) has GUI Verification Evidence or a documented GUI Compatibility Exception.
- [x] required GUI slices are complete with verification evidence.
- [x] `.rcms compatibility` is proven by opening representative existing files, saving modern `.rcms` files, and round-tripping selected project files without user-visible migration steps.
- [x] advanced-analysis coverage includes binary and continuous meta-regression and subgroup compatibility.
- [x] Windows packaging produces and verifies `RCMetaStudio-modern-windows-x64.zip` as a normal-user artifact that does not require manual R or R-package installation; required R pieces are bundled or installed through app-managed setup.
- [x] user documentation explains how to run the modern Windows distributable and what compatibility is preserved.

## Issue #34 release evidence

- Local verification command: `scripts\verify-modern-fast.ps1` runs the Fast Verification Lane; `scripts\package-modern-windows.ps1` runs the explicit Windows Packaging Lane.
- Expected artifact: `RCMetaStudio-modern-windows-x64.zip`.
- Representative project-open samples: `sample_data\BCG.rcms` and `sample_data\amino.rcms`.
- Bundled help target: `doc\openMA_help.html`.
- Modern test and packaging instructions: `docs/agents/testing.md`.

## Issue #45 gate evidence

Issue #45 closed the Release Cutover readiness loop on top of the analysis and packaging work delivered by issues #43 and #44.

- Workflow traceability: every Release Cutover workflow has non-pending traceability in [Workflow Traceability Manifest](workflow-traceability.json); `uv run python scripts/validate_golden_baseline_manifests.py --strict-no-pending` passes.
- Exception manifests: [Compatibility Exceptions](compatibility-exceptions.json) and [GUI Compatibility Exceptions](gui-compatibility-exceptions.json) hold only reviewed accepted exceptions; no gate-closing trace points at an unaccepted exception.
- Golden analysis: the curated compatibility report (`artifacts/golden-analysis-compatibility-report.json`) records the accepted golden baseline comparisons.
- GUI slices: required GUI slices have GUI Verification Evidence in [GUI Verification Evidence](gui-verification-evidence.md).
- Advanced analysis: binary and continuous meta-regression and subgroup coverage land through the golden coverage rows traced from the manifest (issue #43).
- Windows packaging and user docs: `RCMetaStudio-modern-windows-x64.zip` and run instructions are covered by [Modern Windows Release Readiness](modern-windows-release-readiness.md) (issue #44).

The retired Python 2 and PyQt4 path is no longer part of the maintained release or build workflow.
