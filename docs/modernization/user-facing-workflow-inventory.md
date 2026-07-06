# User-Facing Workflow Inventory

This inventory is the authoritative checklist for Functional Indistinguishability during the Full Legacy App Port. It is built from the Reference Implementation GUI actions, bundled user documentation, sample `.rcms` projects, and R-backed analysis paths.

The Full Legacy App Port covers all non-network desktop workflows before Release Cutover. Network Meta-Analysis remains a user-facing legacy workflow, but it belongs to the later Complete User-Facing Legacy Port milestone.

## Inventory Sources

- `src/rc_metastudio/forms/meta.ui` and generated `src/rc_metastudio/ui_meta.py` for main-window menus, toolbar actions, and visible controls.
- `src/rc_metastudio/meta_form.py` for action handlers, navigation behavior, project open/save, analysis dispatch, and result display.
- `src/rc_metastudio/main_wizard.py` and `src/rc_metastudio/forms/*.ui` for startup, dataset creation, and CSV import workflows.
- `doc/*.html` and `doc/images/*` for documented user workflows and expected concepts.
- `sample_projects/*.rcms` for representative legacy projects.
- `r/RCMetaR` and related R analysis calls for preserved Analysis Behavior.

## Release Cutover Scope

- Startup and project selection workflows.
- Existing `.rcms` project open, display, save, and save-as workflows. Release Cutover keeps `.rcms` as the user-facing read and write project format; save compatibility is proven through representative round-trip tests rather than byte-for-byte identical serialization.
- Recent files and persisted settings workflows.
- Dataset creation workflows for binary, continuous, and diagnostic data.
- Data-table editing workflows, including adding studies, groups, outcomes, follow-ups, and covariates.
- Copy, paste, undo, and redo workflows.
- Metric selection and confidence-level workflows.
- Standard meta-analysis workflows for binary, continuous, and diagnostic data.
- Cumulative analysis workflows.
- Leave-one-out analysis workflows.
- Meta-Regression workflows.
- Subgroup Analysis workflows.
- CSV import workflows.
- Results-window summary and plot display workflows.
- Bundled help workflows. Release Cutover preserves the existing bundled HTML help content, changing only local path or launch mechanics needed under Python 3.11 and PyQt5. Modern installation and compatibility notes belong in release documentation rather than a broad help rewrite.
- Windows distributable launch workflow.

## Porting Order

Before further behavior-changing port work, expand the Golden Analysis Tests into a Comprehensive Golden Baseline for testable user-facing analysis workflows. Drive the baseline from the [Golden Coverage Matrix](golden-coverage-matrix.md), which covers as much functionality as practical across data families, workflows, metrics, methods, options, project states, and generated artifacts. Omitted user-facing branches need documented reasons; uncertain branches should be included. The baseline should capture parsed numeric summaries as the hard oracle and retain generated artifacts such as plots for Plot Similarity review.

After the Comprehensive Golden Baseline gate is satisfied, port project and data-editing workflows before analysis workflow slices. The first full-port slices should stabilize startup/project selection, `.rcms` open/save/save-as, recent files/settings, dataset creation, data-table editing, study/group/outcome/follow-up/covariate editing, copy/paste, and undo/redo. Analysis slices should build on that surface so R-backed behavior is exercised through the same project and model state users create in the GUI.

Adopt `uv` for the Modern Python Environment as soon as the dependency feasibility spike identifies a viable dependency set. `uv` adoption should not precede proof that the R Stack shape works, but it should be the first environment hardening step after that proof.

## Post-Cutover Scope

- Network Meta-Analysis workflows.

## Inventory Rule

Every workflow in Release Cutover Scope needs GUI Verification Evidence in [GUI Verification Evidence](gui-verification-evidence.md) or a documented GUI Compatibility Exception before Release Cutover.

Use scripted verification for workflows that mutate project data, call R-backed Analysis Behavior, save or load `.rcms` files, import CSV data, or affect packaging and launch behavior. Manual GUI Verification Evidence is acceptable for low-risk workflows whose compatibility target is primarily navigational or visual, such as bundled help opening, menu presence, or recognizable dialog layout.

Non-analysis GUI workflows should enter the Comprehensive Golden Baseline when they create or mutate analysis-relevant project state. Pure navigation or visual workflows remain GUI Verification Evidence unless they affect analysis inputs or outputs.

Before the Comprehensive Golden Baseline gate is satisfied, every Release Cutover Scope item must trace explicitly in the [Workflow Traceability Manifest](workflow-traceability.json) to one of: a Golden Coverage Matrix row, GUI Verification Evidence, documented omission, [Compatibility Exception](compatibility-exceptions.json), or [GUI Compatibility Exception](gui-compatibility-exceptions.json). Analysis-relevant workflows should trace to golden coverage. Pure GUI or navigation workflows may trace to GUI Verification Evidence.

Validate the Comprehensive Golden Baseline manifests in CI-visible manifest-completeness mode with:

```powershell
uv run python scripts/validate_golden_baseline_manifests.py
```

Manifest-completeness mode allows pending trace entries while the gate is open. Before closing the Comprehensive Golden Baseline gate, run strict no-pending mode and resolve every pending trace entry:

```powershell
uv run python scripts/validate_golden_baseline_manifests.py --strict-no-pending
```

## Golden Output Bundle Authority

Golden Output Bundle captures record runtime and provenance metadata: Python, OS, R, rpy2, PyQt, relevant package versions, commit SHA, capture mode, capture command, Reference Environment identity, and an authority flag.

Local developer captures are for debugging and fixture development. Capture tooling marks them as `local-debug` by default, and they are not authoritative compatibility evidence.

Windows CI captures may be marked `authoritative` only when their Reference Environment metadata exactly matches the Windows CI conda Reference Environment from ADR 0004: Windows, Python 2.7.18, PyQt 4.11.4, R 3.3.2, and rpy2 2.8.5. CI can provide that identity through `RCMS_GOLDEN_CAPTURE_MODE=authoritative`, `RCMS_GOLDEN_CAPTURE_COMMAND`, and `RCMS_REFERENCE_ENVIRONMENT_*` variables. If the requested authoritative capture does not match that metadata, tooling records the bundle as `local-debug`.
