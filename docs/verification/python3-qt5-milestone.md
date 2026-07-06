# Python 3 and Qt 5 Modernization Milestone

This checklist defines the first modernization milestone for RC MetaStudio Community. The goal is to port from Python 2.7 and Qt 4 to Python 3 and Qt 5 while preserving analysis behavior and a roughly similar desktop GUI.

## Scope

- Target Python 3 and Qt 5 before considering Qt 6. See [ADR 0001](../adr/0001-target-python-3-and-qt-5-before-qt-6.md).
- Target PyQt5 for the first Qt port. See [ADR 0006](../adr/0006-target-pyqt5-for-the-first-qt-port.md).
- Use Python 3.11 as the pinned Python Runtime Target for the first port. See [ADR 0014](../adr/0014-target-one-python-3-minor-version-for-the-first-port.md).
- Keep the R stack pinned to the reference environment during the first port. See [ADR 0005](../adr/0005-defer-r-stack-modernization-until-after-python-qt-port.md).
- Focus distributable acceptance on Windows; defer macOS and Linux packaging. See [ADR 0011](../adr/0011-focus-the-first-modernization-milestone-on-windows.md).
- Require Windows Modern CI Path gates for Release Cutover. Linux and macOS checks may be useful developer signals, but they do not block the first modern release unless their packaging scope is explicitly added later.
- Defer network meta-analysis from the first milestone. See [ADR 0035](../adr/0035-defer-network-meta-analysis-from-the-first-milestone.md).
- Require meta-regression and subgroup analysis compatibility before release, after the initial harness fixtures are stable. See [ADR 0036](../adr/0036-require-meta-regression-and-subgroup-compatibility-before-release.md).
- Require at least binary and continuous coverage for meta-regression and subgroup analysis before release. See [ADR 0037](../adr/0037-require-binary-and-continuous-advanced-analysis-coverage.md).

## Reference Baseline

- The legacy Python 2 and PyQt4 Windows CI/build path stayed alive until the maintained path replaced it. It is now retired. See [ADR 0021](../adr/0021-keep-the-legacy-ci-path-until-the-port-replaces-it.md).
- Use the Windows CI conda environment as the reference environment for golden outputs. See [ADR 0004](../adr/0004-use-windows-ci-as-the-reference-environment.md).
- Support local Reference Implementation capture for debugging and fixture development, but treat Windows CI capture as authoritative for Golden Output Bundles and Comprehensive Golden Baseline artifacts. See [ADR 0004](../adr/0004-use-windows-ci-as-the-reference-environment.md).
- The modern Python 3 and PyQt5 path ran in parallel with the legacy path until cutover. See [ADR 0022](../adr/0022-run-the-modern-port-in-parallel-with-the-legacy-path.md).

## Required Acceptance Gates

- Use the [User-Facing Workflow Inventory](user-facing-workflow-inventory.md) as the authoritative checklist for Functional Indistinguishability in the Full Legacy App Port.
- Complete a dependency feasibility spike before deeper porting work. See [ADR 0027](../adr/0027-start-implementation-with-a-dependency-feasibility-spike.md).
- Build a headless analysis regression harness before treating the GUI port as complete. See [ADR 0003](../adr/0003-build-headless-analysis-regression-before-gui-port.md).
- Build the headless harness around the existing Python analysis adapter behavior rather than bypassing directly to R. See [ADR 0029](../adr/0029-build-the-headless-harness-around-the-existing-analysis-adapter.md).
- Prove analysis compatibility with golden analysis tests against reference outputs. See [ADR 0002](../adr/0002-use-golden-analysis-tests-as-the-compatibility-oracle.md).
- Use both headless and GUI-driven capture for the Comprehensive Golden Baseline: headless for broad numeric coverage, GUI-driven for representative end-to-end workflows and parameter-state behavior. See [ADR 0048](../adr/0048-capture-a-comprehensive-golden-baseline-before-further-porting.md).
- Capture a Comprehensive Golden Baseline from the [Golden Coverage Matrix](golden-coverage-matrix.md) before further application porting changes touch user-facing behavior. See [ADR 0048](../adr/0048-capture-a-comprehensive-golden-baseline-before-further-porting.md).
- Before satisfying the Comprehensive Golden Baseline gate, trace every Release Cutover workflow in the [User-Facing Workflow Inventory](user-facing-workflow-inventory.md) through the [Workflow Traceability Manifest](workflow-traceability.json) to a Golden Coverage Matrix row, GUI Verification Evidence, or a documented omission, Compatibility Exception, or GUI Compatibility Exception. See [ADR 0050](../adr/0050-use-a-workflow-traceability-manifest.md).
- Add CI-visible Comprehensive Golden Baseline manifest-completeness enforcement before behavior-changing full-port PRs merge. See [ADR 0048](../adr/0048-capture-a-comprehensive-golden-baseline-before-further-porting.md).
- Build thin golden-baseline capture tooling before manually expanding every matrix row, so dynamic method availability and omission rationales come from the Reference Implementation.
- Make legacy Reference Environment capture deterministic before adding comparison mode against the Python 3 branch.
- Store golden outputs as structured JSON plus external artifacts, not raw console snapshots. See [ADR 0030](../adr/0030-store-golden-outputs-as-structured-json-plus-artifacts.md).
- Include exact capture metadata in every Golden Output Bundle, including runtime versions, package versions, commit SHA, capture mode, command, Reference Environment identity, and whether the capture is authoritative or local-debug. See [ADR 0030](../adr/0030-store-golden-outputs-as-structured-json-plus-artifacts.md).
- Commit a small curated golden set for CI and archive larger captures as artifacts. See [ADR 0031](../adr/0031-commit-a-curated-golden-set-and-archive-larger-captures.md).
- Commit golden schemas, manifests, tooling, and the Curated Golden Set; store the broader Comprehensive Golden Baseline as ignored local artifacts or CI/release artifact bundles.
- Cover data-family breadth before method depth in the initial curated golden set. See [ADR 0032](../adr/0032-cover-data-family-breadth-before-method-depth.md).
- Use `amino.rcms`, `continuous.rcms`, and `lymph.rcms` as the initial committed golden datasets. See [ADR 0033](../adr/0033-use-amino-continuous-and-lymph-as-the-initial-golden-datasets.md).
- Prioritize random-effects methods in the initial golden method set. See [ADR 0034](../adr/0034-prioritize-random-effects-in-the-initial-golden-methods.md).
- Add binary and continuous meta-regression and subgroup analysis golden coverage before release. See [ADR 0036](../adr/0036-require-meta-regression-and-subgroup-compatibility-before-release.md) and [ADR 0037](../adr/0037-require-binary-and-continuous-advanced-analysis-coverage.md).
- Compare parsed numeric outputs with explicit tolerances, not exact string equality. See [ADR 0018](../adr/0018-use-explicit-tolerances-for-golden-analysis-tests.md).
- Preserve generated plots as Golden Output Bundle artifacts and verify Plot Similarity for workflows that produce plots, without using pixel-perfect image comparisons as the normal gate. See [ADR 0002](../adr/0002-use-golden-analysis-tests-as-the-compatibility-oracle.md) and [ADR 0048](../adr/0048-capture-a-comprehensive-golden-baseline-before-further-porting.md).
- Emit a compatibility report artifact from golden analysis CI. See [ADR 0023](../adr/0023-emit-compatibility-reports-from-golden-analysis-ci.md).
- Block on statistical drift unless a documented compatibility exception is accepted. See [ADR 0024](../adr/0024-require-documented-exceptions-for-analysis-drift.md).
- Track Compatibility Exceptions and GUI Compatibility Exceptions in committed manifests so Workflow Traceability Manifest references are CI-validatable. Only accepted exceptions with explicit approval and follow-up or expiry can satisfy compatibility gates. See [ADR 0051](../adr/0051-track-compatibility-exceptions-as-manifests.md).
- Use pytest for maintained Python 3 tests. See [ADR 0026](../adr/0026-use-pytest-for-modern-tests-and-nose-for-the-legacy-baseline.md).

## First GUI Compatibility Slice

- Use runnable compatibility slices instead of a repository-wide mechanical conversion. See [ADR 0007](../adr/0007-port-by-runnable-compatibility-slices.md).
- Treat GUI similarity as workflow and recognizable-layout preservation, not pixel-perfect matching. See [ADR 0038](../adr/0038-define-gui-similarity-as-workflow-and-recognizable-layout-preservation.md).
- Preserve GUI workflows unless a GUI compatibility exception is documented. See [ADR 0039](../adr/0039-preserve-gui-workflows-unless-an-exception-is-documented.md).
- First GUI slice: open an existing `.rcms` sample project, display the data table, run a binary random-effects meta-analysis, and show the result summary plus forest plot. See [ADR 0008](../adr/0008-use-standard-binary-analysis-as-the-first-gui-slice.md).
- Use automated headless analysis regression as the first hard gate; allow manual or lightweight scripted GUI verification initially. See [ADR 0017](../adr/0017-use-analysis-regression-as-the-first-automated-gate.md).

## Full Legacy App Port Sequence

- Complete the Comprehensive Golden Baseline gate and workflow traceability before behavior-changing full-port slices proceed.
- Keep the preview slice removed from the modern packaging entry point; the Windows artifact must launch the real `launch.py` and `MetaForm` path. See [ADR 0043](../adr/0043-retire-the-preview-slice-as-the-full-port-entry-point.md).
- Launch the real `MetaForm` shell first through an explicit automation entry mode. See [ADR 0044](../adr/0044-launch-the-real-metaform-shell-as-the-first-full-port-slice.md) and [ADR 0045](../adr/0045-use-an-explicit-automation-entry-mode-for-full-app-port-slices.md).
- Regenerate all canonical UI modules with PyQt5 and remove Python 2 syntax before workflow slices. See [ADR 0046](../adr/0046-regenerate-all-ui-modules-before-workflow-slices.md) and [ADR 0047](../adr/0047-remove-python-2-syntax-before-gui-workflow-slices.md).
- Use direct review and targeted static scans for any future migration cleanup. Historical conversion scripts were migration aids, not part of the maintained runtime.
- Bring forward project open, data-table rendering, save/save-as, startup project-selection behavior, recent files, and settings before broader data-entry and analysis workflows.
- Bring forward binary, continuous, and diagnostic data-entry workflows before standard analysis, cumulative analysis, leave-one-out analysis, Meta-Regression, Subgroup Analysis, CSV import, help, and full Windows packaging.

## Project Files

- Existing `.rcms` files must open without user-visible migration steps. See [ADR 0009](../adr/0009-require-oma-read-compatibility-before-byte-perfect-writes.md).
- Save compatibility is initially proven through representative round-trip tests rather than byte-for-byte identical output. See [ADR 0009](../adr/0009-require-oma-read-compatibility-before-byte-perfect-writes.md).
- Defer project file format evolution until after the port is stable. See [ADR 0019](../adr/0019-defer-project-file-format-evolution.md).

## Porting Rules

- Treat "modern codebase" before Release Cutover as a modern runtime, Qt binding, reproducible environment, test runner, CI path, and packaging surface. Broad module reorganization, new domain architecture, and major R Stack redesign are Post-Port Refactor work unless a local structural change is required for a Compatibility Slice.
- Preserve user-facing Reference Implementation behavior by default, including awkward or buggy behavior, unless changing it is required for Python 3.11, PyQt5, security, packaging, or an explicitly accepted Compatibility Exception or GUI Compatibility Exception.
- Keep R Stack behavior fixed for Release Cutover. R changes are allowed only when required to make the modern bridge or Windows distributable work, and any Analysis Behavior drift must be gated by Golden Analysis Tests plus an accepted Compatibility Exception.
- Preserve the existing module layout during the first port except where a local structural change is required for a compatibility slice. See [ADR 0013](../adr/0013-preserve-module-layout-during-the-first-port.md).
- Plan post-port refactoring after compatibility slices are stable. See [ADR 0013](../adr/0013-preserve-module-layout-during-the-first-port.md).
- Treat Qt Designer `.ui` files as canonical and regenerate Python UI modules for PyQt5. See [ADR 0012](../adr/0012-treat-ui-files-as-canonical-for-the-pyqt5-port.md).
- Normalize legacy text and variant types at project-file, model, and R-bridge boundaries. See [ADR 0015](../adr/0015-normalize-text-and-variant-types-at-boundaries.md).
- Migrate PyQt signals by compatibility slice rather than with a global rewrite. See [ADR 0016](../adr/0016-migrate-pyqt-signals-by-compatibility-slice.md).
- Avoid a broad PyQt4 compatibility shim; use direct PyQt5 replacements or small focused helpers. See [ADR 0040](../adr/0040-avoid-a-broad-pyqt4-compatibility-shim.md).
- Do not install fake `PyQt4` modules on the maintained path. Use `src/rc_metastudio/test_backend_compat.py` only for R-backend bootstrap, and keep project-file compatibility in `src/rc_metastudio/project_pickle.py`. See [ADR 0054](../adr/0054-retire-the-fake-pyqt4-runtime-surface.md).

## Environment and Packaging

- Keep dependency management changes minimal and milestone-driven. See [ADR 0020](../adr/0020-keep-dependency-management-minimal-and-milestone-driven.md).
- Use `uv` as the Modern Python Environment and command runner: `pyproject.toml`, a committed `uv.lock`, `uv sync --locked` for reproducible installs, and `uv run` for tests and developer commands. PyInstaller remains the Windows distributable builder. See [ADR 0020](../adr/0020-keep-dependency-management-minimal-and-milestone-driven.md) and [ADR 0041](../adr/0041-use-pyinstaller-as-the-default-windows-packaging-candidate.md).
- The dependency feasibility spike has produced the first viable dependency set; keep the Modern Python Environment in `pyproject.toml` and the committed `uv.lock`.
- If in-process rpy2 cannot support the pinned R stack, use an out-of-process R bridge before R-stack modernization. See [ADR 0028](../adr/0028-prefer-an-out-of-process-r-bridge-before-r-stack-modernization.md).
- Include a Windows distributable in the first modernization milestone, after the headless harness and first GUI slice. See [ADR 0010](../adr/0010-include-windows-packaging-in-the-first-modernization-milestone.md).
- Use PyInstaller as the default Windows packaging candidate unless feasibility work proves it unsuitable. See [ADR 0041](../adr/0041-use-pyinstaller-as-the-default-windows-packaging-candidate.md).
- Include minimal user-facing release documentation for the Python 3 and Qt 5 Windows build. See [ADR 0025](../adr/0025-include-minimal-user-docs-in-the-first-modernization-release.md).
- Cut over from the legacy release path only after all modern release criteria are met. See [ADR 0042](../adr/0042-cut-over-only-after-modern-release-criteria-are-met.md).
- Track release readiness in [Windows Release Readiness](windows-package-release-readiness.md) and [Windows Cutover Checklist](windows-package-cutover-checklist.md).

## Done Means

- The modern Python 3 and PyQt5 path runs in CI.
- Every Release Cutover workflow in the User-Facing Workflow Inventory has GUI Verification Evidence or a documented GUI Compatibility Exception.
- A Comprehensive Golden Baseline exists for testable user-facing analysis workflows before further behavior-changing port work proceeds.
- Headless golden analysis tests pass against reference outputs and publish a compatibility report.
- Binary and continuous meta-regression and subgroup compatibility coverage is included before release.
- The first GUI compatibility slice can be completed with documented GUI verification evidence.
- Existing representative `.rcms` files open, and selected project files round-trip successfully.
- A Windows distributable is produced.
- Minimal user documentation exists for the Windows distributable.
- Any accepted analysis drift is documented as a compatibility exception.
- The maintained path is the maintained release path after satisfying all cutover criteria.
