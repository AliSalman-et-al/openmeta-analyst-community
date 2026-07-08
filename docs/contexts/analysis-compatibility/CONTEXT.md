# Analysis Compatibility

This context defines what must remain stable while RC MetaStudio Community is migrated from its legacy Python 2.7 and Qt 4 implementation to a modern Python 3 and Qt 5 implementation.

## Language

**Reference Implementation**:
The current Python 2.7, PyQt4, and bundled R-package application used as the source of truth for preserved behavior during migration.
_Avoid_: Legacy app, old version

**Retired Reference Implementation**:
The former Python 2.7, PyQt4, and bundled R-package application after it no longer serves as the maintained compatibility oracle.
_Avoid_: Active baseline, fallback app

**Reference Environment**:
The reproducible Windows CI conda environment used to run the Reference Implementation and capture Golden Analysis Test outputs.
_Avoid_: Developer machine, local legacy setup

**Retired Legacy CI Path**:
The former Python 2 and PyQt4 Windows CI/build workflow that produced the Reference Environment and legacy distributable before cutover.
_Avoid_: Active fallback, maintained legacy build

**Modern CI Path**:
The Python 3 and PyQt5 test/build workflow used for the maintained release path.
_Avoid_: New workflow, preview build

**Fast Verification Lane**:
The pull-request and push path of the Modern CI Path that proves source changes against locked dependencies, manifests, modern tests, and R Stack verification without producing a full distributable.
_Avoid_: Quick build, lightweight CI

**Smoke Verification Lane**:
The smallest required Modern CI Path gate that fails quickly on broken collection, manifest sanity, representative compatibility parsing, project-load compatibility, or required Default R Evidence prerequisites before the broader Fast Verification Lane runs.
_Avoid_: Mini build, partial CI

**Fast Feedback Budget**:
The target that the Fast Verification Lane should return automated pass/fail feedback in under ten minutes on GitHub and under two minutes locally after dependencies are warm.
_Avoid_: Nice-to-have speed goal, rough timing target

**Packaging Lane**:
The Modern CI Path route that produces a Windows Distributable or macOS application artifact through PyInstaller, bundled R runtime assembly, packaged smoke checks, and artifact upload.
_Avoid_: Release test, build-all path

**Release Cutover**:
The point where the Modern CI Path replaces the Legacy CI Path as the accepted release path.
_Avoid_: Migration complete, switch over

**R Stack**:
The R runtime, rpy2 bridge, bundled R packages, and external R packages used to execute meta-analysis calculations.
_Avoid_: R dependencies, statistical backend

**RCMetaR R Stack Slice**:
The R Stack modernization increment scoped to the bundled `RCMetaR` package, its direct runtime package declarations, and the external packages its functions call directly.
_Avoid_: RCMetaR R Stack Slice, Full R dependency refresh, all CRAN transitive dependency migration

**Default R Evidence**:
The small R Stack check included in the Fast Verification Lane, intended to prove manifest validity and a deterministic RCMetaR load or smoke path without running the full package/build/distributable verification sequence.
_Avoid_: R Stack verification, quick R test

**Degraded Local R Evidence**:
A local-only Default R Evidence mode that reports missing or mismatched R dependencies without satisfying CI-required R evidence.
_Avoid_: Passing CI evidence, soft CI failure

**Full R Stack Evidence**:
The opt-in, scheduled, release, or packaging-gated verification that installs the R dependency bundle, builds and checks RCMetaR, validates installed package versions, runs R analysis smoke coverage, and exercises real rpy2 bridge behavior.
_Avoid_: Required PR R check, default R test

**R Dependency Cache**:
A cache of installed R package dependency inputs keyed by R runtime version, R dependency policy, package metadata, and repository policy, used to avoid repeated CRAN downloads without trusting assembled application outputs.
_Avoid_: Cached distributable, cached build output

**CRAN Repository Policy**:
The configured CRAN-compatible package repository or mirror used by R dependency installation, recorded as part of R dependency acquisition so slow or unreliable package downloads can be improved without hidden behavior changes.
_Avoid_: Hard-coded CRAN mirror, implicit package source

**Out-of-Process R Bridge**:
A process boundary where the Python 3 application invokes analysis code running in a separate R-capable environment instead of embedding R through in-process rpy2.
_Avoid_: R subprocess hack, external script

**Analysis Behavior**:
The statistical inputs, model choices, numerical outputs, result summaries, and generated analysis artifacts that users rely on when conducting meta-analyses.
_Avoid_: Exact functionality, analysis functionality

**Entered Diagnostic Effect Estimate**:
A diagnostic sensitivity, specificity, likelihood-ratio, or diagnostic-odds-ratio estimate entered directly with its confidence interval instead of being computed from TP/FN/FP/TN counts.
_Avoid_: Pre-computed diagnostic data, manual diagnostic value

**Direct Effect-Size Entry**:
A study-level effect estimate entered directly with its confidence interval or standard error instead of being computed from raw study measurements.
_Avoid_: Manual outcome, precomputed row

**Raw Count Entry**:
Study-level binary or diagnostic count data entered as the primary evidence for an effect estimate, such as event/non-event counts or TP/FP/FN/TN counts.
_Avoid_: Manual 2x2, reconstructed counts

**Derived 2x2 Margin**:
A displayed row, column, or grand total in a binary or diagnostic 2x2 calculator that is calculated from Raw Count Entry rather than entered as primary evidence.
_Avoid_: Editable total, independent margin

**Back-Calculation**:
The optional workflow that infers compatible raw counts from a Direct Effect-Size Entry when the user has a published estimate and interval but not the original raw counts.
_Avoid_: Raw-data edit, consistency check

**Count-Based Diagnostic Accuracy Method**:
A diagnostic method that needs complete TP/FN/FP/TN counts for each included study because direct entered estimates do not carry the paired count information the model requires.
_Avoid_: Direct-effect bivariate method, manual HSROC

**Golden Analysis Test**:
A regression test that compares modernized analysis behavior against outputs captured from the Reference Implementation using representative project data.
_Avoid_: Snapshot test, golden master

**Modern Behavior Baseline**:
A regression baseline captured from the maintained modern application, current R Stack, and `RCMetaR` package after the Reference Implementation is retired as the compatibility oracle.
_Avoid_: Legacy golden set, reference environment

**Golden Output Bundle**:
A structured set of reference outputs for a Golden Analysis Test, including JSON comparison data and external generated artifacts such as plots.
_Avoid_: Raw snapshot, console output

**Comprehensive Golden Baseline**:
The hard-gated pre-port capture of Reference Implementation outputs across the testable user-facing analysis workflows needed to protect Functional Indistinguishability before further behavior-changing modernization changes are made.
_Avoid_: Nice-to-have test expansion, later coverage, exhaustive proof of everything

**Coverage Matrix**:
The explicit list of data families, analysis workflows, metrics, methods, options, project states, and generated artifacts included in the Comprehensive Golden Baseline, with documented reasons for any omitted user-facing branch.
_Avoid_: Representative sample, implicit coverage, best-effort tests

**Curated Golden Set**:
The small committed set of Golden Output Bundles required to gate core compatibility in normal CI.
_Avoid_: Full capture, all snapshots

**Data-Family Breadth**:
Golden Analysis Test coverage that samples the major analysis data families before exhaustively covering every method within one family.
_Avoid_: Broad test coverage, representative tests

**Initial Golden Projects**:
The first committed project files used to capture and compare Golden Output Bundles: `amino.rcms`, `continuous.rcms`, and `lymph.rcms`.
_Avoid_: Sample data, fixture set, initial golden datasets

**Initial Golden Methods**:
The first analysis methods captured for the Curated Golden Set, prioritizing random-effects analyses across the Initial Golden Datasets.
_Avoid_: Method fixtures, first methods

**Network Meta-Analysis**:
The optional network-analysis feature area that depends on packages outside the default desktop binary build.
_Avoid_: Network feature, optional analysis

**Meta-Regression**:
An analysis feature that models study-level covariates as predictors of effect estimates and must remain compatible before the first modernization milestone is releasable.
_Avoid_: Regression feature, covariate analysis

**Meta-Regression Bubble Plot**:
The generated plot for a single-continuous-covariate Meta-Regression, showing study effect estimates as precision-weighted bubbles against the moderator with the fitted regression line and optional interval bands.
_Avoid_: Regression scatter, covariate chart

**Bubble Plot Style**:
The publication presentation template for a Meta-Regression Bubble Plot, using the same Default, RevMan, and BMJ style vocabulary as Forest Plot Style while remaining a separate plot contract.
_Avoid_: Bubble theme, regression skin

**Subgroup Analysis**:
An analysis feature that compares effect estimates across study groups or categorical covariates and must remain compatible before the first modernization milestone is releasable.
_Avoid_: Group analysis, subgroup feature

**Required Advanced Analysis Coverage**:
The milestone-1 compatibility coverage required for Meta-Regression and Subgroup Analysis before release.
_Avoid_: Advanced tests, full matrix

**Confidence Level**:
The percentage level used to compute confidence intervals for analysis results and displayed confidence intervals; the default Confidence Level is 95.0% unless a project or user action sets another value.
_Avoid_: CI setting, interval percentage, confidence placeholder

**Modern Test Runner**:
The test runner used by Python 3 modernization tests and compatibility harness work.
_Avoid_: Test cleanup, new tests

**Test Taxonomy & Audit**:
The review pass that classifies modern tests by evidence type, execution cost, external dependencies, and CI lane before the Modern CI Path is restructured around selective execution.
_Avoid_: Test cleanup, marker pass

**Taxonomy Enforcement Backlog**:
The Test Taxonomy & Audit manifest when it is used to record keep, rewrite, merge, move, and remove decisions before every cleanup action has been implemented.
_Avoid_: Aspirational test list, all-keep inventory

**Evidence-Carrying Test**:
A test whose failure would identify a meaningful regression against Analysis Behavior, GUI compatibility, R Stack integration, packaging contract, or migration infrastructure.
_Avoid_: Useful test, important test

**Low-Value Test**:
A test that mainly asserts implementation text, duplicates stronger coverage, preserves obsolete behavior, or creates CI cost without carrying distinct compatibility or release-readiness evidence.
_Avoid_: Useless test, bad test

**Structured Contract Test**:
A packaging, workflow, manifest, or script contract test that inspects parsed structure, function behavior, command outcomes, or stable data models instead of asserting raw source text substrings.
_Avoid_: Raw string assertion, source-text check

**Compatibility Report**:
A CI artifact that records the datasets, analysis methods, metrics, tolerances, and observed drift values from Golden Analysis Tests.
_Avoid_: Test log, CI summary

**Numerical Equivalence**:
Compatibility between analysis outputs when parsed numerical values match the Reference Implementation within explicit tolerances for each output type.
_Avoid_: Exact match, string equality

**Plot Similarity**:
Compatibility where generated plots preserve the same analysis content, labels, grouping, ordering, and recognizable presentation as the Reference Implementation without requiring pixel-perfect image equality.
_Avoid_: Pixel-perfect plot diff, unchecked plot artifact, cosmetic clone

**Compatibility Exception**:
An explicitly documented, reviewed difference from Reference Implementation Analysis Behavior that is accepted despite failing normal golden-test equivalence.
_Avoid_: Known failure, acceptable drift

**Statistical Modernization Drift**:
A reviewed Analysis Behavior difference caused by moving the R Stack to current statistical package behavior, where the modern output is accepted because it is correct for the updated methods and APIs even though it differs from the Reference Implementation.
_Avoid_: Regression, silent statistical change

**Compatibility Exception Manifest**:
A machine-readable list of accepted Compatibility Exceptions with stable IDs, affected workflows, reasons, approval references, and follow-up expectations.
_Avoid_: Exception notes, known-fail list

**GUI Verification Evidence**:
Manual or scripted proof that a GUI Compatibility Slice can be completed with preserved workflow behavior and GUI Similarity.
_Avoid_: GUI test suite, visual snapshot

**GUI Compatibility Exception**:
An explicitly documented difference from the Reference Implementation GUI workflow or layout that is accepted for the modernization milestone.
_Avoid_: UI change, simplification

**GUI Compatibility Exception Manifest**:
A machine-readable list of accepted GUI Compatibility Exceptions with stable IDs, affected workflows, before and after behavior, reasons, approval references, and follow-up expectations.
_Avoid_: UI exception notes, visual-diff list

**Headless Analysis Harness**:
A test harness that exercises Analysis Behavior without requiring the full desktop window lifecycle.
_Avoid_: GUI test harness, analysis runner

**Analysis Adapter**:
The Python boundary that prepares analysis inputs, invokes R-backed analysis behavior, and normalizes returned summaries and artifacts for the application.
_Avoid_: R wrapper, direct R call

**Compatibility Slice**:
A small migration increment that produces a runnable or testable path whose behavior can be compared against the Reference Implementation.
_Avoid_: Mechanical conversion batch, big-bang port

**Compatibility-First Port**:
A migration approach that preserves existing code organization unless a local change is required to make a compatibility slice run under the target runtime.
_Avoid_: Cleanup port, rewrite

**Post-Port Refactor**:
A planned modernization phase after compatibility slices are stable, focused on improving module boundaries and maintainability without changing Analysis Behavior.
_Avoid_: Future cleanup, code reorganization

**GUI Compatibility Slice**:
A Compatibility Slice that proves a user-visible desktop workflow still works with GUI Similarity and preserved Analysis Behavior.
_Avoid_: GUI milestone, screen port

**Full Legacy App Port**:
The modernization target where all non-network desktop workflows from the Reference Implementation are available through the Modern CI Path before Release Cutover.
_Avoid_: Full rewrite, preview slice, modern demo

**Complete User-Facing Legacy Port**:
The post-cutover modernization target where every user-facing desktop workflow from the Reference Implementation, including Network Meta-Analysis, is available through the Modern CI Path.
_Avoid_: First milestone, release cutover, all-at-once port

**Functional Indistinguishability**:
Compatibility where a user can complete the same user-facing workflow with the same project data, choices, outputs, side effects, and error handling as the Reference Implementation, even when the Qt 5 interface is not pixel-perfect.
_Avoid_: Pixel-perfect clone, approximate feature parity, modernized behavior

**User-Facing Workflow Inventory**:
The authoritative checklist of Reference Implementation workflows that must be preserved for the Full Legacy App Port, built from legacy GUI actions, bundled user documentation, sample projects, and R-backed analysis paths.
_Avoid_: Feature brainstorm, implementation task list, partial menu audit

**Workflow Traceability Manifest**:
A machine-readable map from each Release Cutover workflow to its Golden Analysis Test coverage, GUI Verification Evidence, documented omission, Compatibility Exception, or GUI Compatibility Exception.
_Avoid_: Manual checklist, prose-only trace, informal audit

**Standard Binary Analysis Workflow**:
The first GUI Compatibility Slice: open an existing `.rcms` sample project, display the data table, run a standard binary random-effects meta-analysis, and show the result summary plus forest plot.
_Avoid_: First GUI test, binary demo

**Project File Read Compatibility**:
The requirement that the modernized application can open existing `.rcms` project files without user-visible migration steps.
_Avoid_: File support, import compatibility

**Legacy Project Data Compatibility**:
The requirement that user project files created by earlier RC MetaStudio releases remain usable in the maintained modern application.
_Avoid_: Reference Implementation support, legacy runtime support

**Project File Round Trip**:
A compatibility check that opens a representative `.rcms` project file, saves it through the modernized application, and verifies that the saved project can be reopened by the modernized application with equivalent project data.
_Avoid_: Byte-perfect save, file snapshot

**Versioned Project Format**:
A future project file format that can evolve beyond the current `.rcms` representation while preserving access to existing projects through migration tooling.
_Avoid_: New save format, file rewrite

**Windows Distributable**:
The packaged Windows application artifact that users can run without setting up the source development environment.
_Avoid_: Build artifact, packaged app

**Windows Packaging Candidate**:
The packaging toolchain assumed for the first modern Windows distributable unless dependency feasibility proves it unsuitable.
_Avoid_: Installer choice, packaging stack

**Release Readiness Documentation**:
Minimal user-facing documentation that explains how to run the modern Windows distributable and what compatibility promises the release makes.
_Avoid_: Developer notes, migration docs

**Milestone Platform Scope**:
The operating systems that count toward acceptance for a modernization milestone.
_Avoid_: Platform support, supported systems

**GUI Similarity**:
A rough preservation target for the desktop interface's workflows, layout, and user-facing concepts without requiring pixel-perfect visual equivalence.
_Avoid_: Exact GUI, identical GUI

**Recognizable Layout**:
GUI compatibility where users can identify the same menus, dialogs, tables, controls, and result views even if Qt5 changes spacing, fonts, or widget rendering.
_Avoid_: Pixel match, visual clone

**Qt Binding Target**:
The Python Qt binding chosen for the first GUI migration milestone.
_Avoid_: Qt wrapper, GUI framework choice

**Python Runtime Target**:
The specific Python 3 minor version chosen for the first modernization milestone.
_Avoid_: Python 3, modern Python

**Modern Python Environment**:
The reproducible Python 3 dependency environment used for the port, tests, and packaging work.
_Avoid_: Dependency cleanup, dev setup

**Dependency Feasibility Spike**:
The first implementation investigation that proves whether the proposed Python runtime, PyQt5, rpy2 bridge, and pinned R stack can work together.
_Avoid_: Setup task, environment check

**Text Boundary**:
A boundary where project-file data, GUI labels, model values, or R-bridge inputs must be normalized between legacy Python 2 text types and Python 3 strings.
_Avoid_: String fix, unicode issue

**Canonical UI Form**:
A Qt Designer `.ui` file that is treated as the source of truth for generated Python UI code.
_Avoid_: Generated UI module, hand-ported UI file

**Signal Migration**:
The conversion of PyQt4 old-style signal and slot connections to PyQt5-compatible signal handling.
_Avoid_: Signal cleanup, connect rewrite

**Qt Compatibility Helper**:
A small focused helper for repeated PyQt4-to-PyQt5 API differences used only where local replacement would duplicate behavior across slices.
_Avoid_: PyQt4 shim, compatibility layer

**Narrow Qt Compatibility Helper**:
A Qt Compatibility Helper with an explicit, limited charter for repeated PyQt5 migration boundaries such as text extraction and file-dialog return normalization. Modern GUI modules should prefer direct PyQt5 imports and local Qt5 methods over shared Qt compatibility behavior.
_Avoid_: Fake PyQt4 layer, QString clone, QVariant clone

**Modern Bootstrap Helper**:
A minimal setup helper for modern tests and automation that selects the modern R backend. It is not a Qt binding compatibility layer.
_Avoid_: PyQt4 bootstrap, fake Qt module installer

**metafor Forest Renderer**:
The post-cutover forest-plot renderer that draws plots with `metafor::forest()` and `addpoly()` from the `rma` result, replacing the retired custom grid-graphics engine. It reuses the existing `metafor` dependency and changes presentation only, not Analysis Behavior.
_Avoid_: New plotting library, custom grid engine

**Forest Layout Preflight**:
The measurement and planning pass that runs before the metafor Forest Renderer draws, choosing device size, text scale, row positions, plot limits, annotation positions, header/footer reserves, and style-specific spacing from a Forest Render Bundle. It does not compute statistics and does not draw plot marks.
_Avoid_: Sizing helper, renderer, custom plot engine

**Forest Layout Plan**:
The computed, per-render output of Forest Layout Preflight: device dimensions, typography, row positions, plot limits, annotation positions, column positions, headers, footer reserves, and style constraints consumed by the metafor Forest Renderer. It is ephemeral, regenerated for each render/export target, and should not contain statistical results beyond layout-ready values copied from the Forest Render Bundle.
_Avoid_: Plot data, render bundle, style config

**Forest Render Bundle**:
The self-contained render spec persisted for a forest plot (the redefined `.plotdata` object): the `rma` result or normalized effect/CI/`slab` vectors, a precomputed ilab spec (ilab column matrix, headers, weights, effect/CI values, subgroup structure) for the chosen style, params, data-type, side-by-side flag, and Forest Plot Style. A builder (`rcmetar.regenerate.plot.data`) emits it from `(om.data, res, params, style)`; the renderer (`rcmetar.draw.forest.plot`) is a pure placer over `metafor::forest()`. It keeps the edit, save-as, and regenerate round-trip stable without reloading `om.data`.
_Avoid_: Legacy plot.data, pickled plot

**Forest Plot Style**:
The per-plot presentation template chosen for a forest plot, stored as the `fp_style` param and selectable in the Edit Forest Plot dialog: one of Default Forest Style, RevMan Forest Style, or BMJ Forest Style. Defaults to Default Forest Style, including for projects saved before the param existed.
_Avoid_: Plot theme, forest skin

**Default Forest Style**:
The plain `metafor::forest()` layout, the universal fallback that renders every data family and forest variant and the style of the first auto-generated plot.
_Avoid_: Basic plot, no style

**RevMan Forest Style**:
A full faithful reproduction of the Cochrane Review Manager forest layout on the metafor Forest Renderer, with per-data-family column templates and weight, effect/CI, subtotal, and heterogeneity blocks. Implemented without risk-of-bias columns, symbols, or legend.
_Avoid_: Cochrane theme, RevMan clone with risk of bias

**Sparse RevMan Template**:
The RevMan Forest Style layout used when raw arm-level columns are unavailable or only partially available. It preserves RevMan's header, rule, weight/effect columns, summary, footer, and axis conventions while omitting absent raw-data column groups instead of falling back to Default Forest Style.
_Avoid_: Default fallback, broken RevMan, empty RevMan columns

**RevMan Compact Template**:
The RevMan Forest Style layout used for forest plot variants whose rows are not ordinary study-arm comparisons, such as cumulative and leave-one-out plots. It preserves RevMan's typography, rule, effect/CI annotation, summary, and axis conventions without inventing Experimental/Control arm columns.
_Avoid_: Full RevMan table for cumulative plots, Default cumulative fallback

**BMJ Forest Style**:
A full faithful reproduction of the BMJ house forest layout on the metafor Forest Renderer, using the BMJ accent color and house column arrangement. Brand fonts are approximated with a clean default family rather than shipped.
_Avoid_: BMJ theme, journal skin

**Universal Appearance Controls**:
The Edit Forest Plot controls that apply to every Forest Plot Style: a single accent-color picker driving study points, CI lines, and the summary diamond, plus weight-scaled point sizing with a size multiplier. Distinct from the per-style control panels that own each style's columns.
_Avoid_: Global plot theme, per-style colors only

**Twin-Panel Side-by-Side Forest Plot**:
The paired diagnostic forest plot that shows two metrics over the same studies in aligned panels (Sensitivity|Specificity and PLR|NLR), historically `two.forest.plots`. On the metafor Forest Renderer it is composed from two `metafor::forest()` panels under base-graphics `layout()` with a shared `ylim`/`rows`, not with `patchwork`; rows align by construction because both panels share the same studies in the same order.
_Avoid_: Dual forest plot, patchwork panel

## Headless Harness Notes

The first Headless Analysis Harness loads `.rcms` files into `DatasetModel`, normalizes legacy state, converts the model through the existing Analysis Adapter functions in `meta_py_r`, and runs one binary or continuous method without creating `QApplication` or `MetaForm`.

Remaining GUI coupling: `DatasetModel` still subclasses `QAbstractTableModel` and uses Qt signal/reset behavior while shaping analysis inputs. It now imports PyQt5 directly and owns its Qt5 reset behavior locally.
