# Windows packaged project-open recalculation stall

**Date:** 2026-07-17
**Scope:** Issue #341; GitHub Actions run
[`29582050470`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29582050470),
Windows package job
[`87889867796`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29582050470/job/87889867796),
and the packaged `amino.rcms` native smoke.

## Executive finding

The failure is a genuine 900-second child-process timeout, but the retained CI
marker does **not** by itself prove that project opening began. At commit
[`679290f`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/launch.py#L421-L426),
`packaged-workflow:start` was written before `start_automation()`, which in turn
initializes R and constructs the main window before `MetaForm.open()` is called.
The artifact therefore places the stall somewhere after entry to the packaged
workflow, not specifically after entry to `open()`.

An independently bounded local run of the already-built packaged executable
does locate the active slow path. After R initialization and the `loading
...amino.rcms` message, its captured stdout continued through repeated
`effect_for_study` and `generic_convert_scale` calls until the process was
terminated at the bound. The captured run made 38 `effect_for_study` calls and
114 `generic_convert_scale` calls without returning from the native smoke. This
matches the source call graph exactly:

`MetaForm.open()` -> `MetaForm.set_model()` -> `MetaForm.model_updated()` ->
`DatasetModel.try_to_update_outcomes()` -> one
`update_outcome_if_possible()` per study -> rpy2/RCMetaR effect calculation.

The structured project contract makes that recalculation unnecessary on open.
`.rcms` already persists complete effect metadata, and
`project_adapter.project_to_dataset()` restores it into each analysis unit
before the table model is installed. For a loaded structured document, opening
should restore those values and selections; recalculation remains appropriate
for a user edit or a newly created/imported dataset. Skipping only the
open-time recalculation is therefore both the likely performance fix and the
more faithful persistence behavior. The watchdog should remain at 900 seconds
as a guard; increasing it would only permit more duplicate R work.

## Primary evidence

### Hosted failure and retained artifact

The correct Windows package job is `87889867796` (not `87886424585`, which is
from a different run). Its `Build Windows package` step started at
`12:57:11Z`. Deployment inspection completed and packaged smoke checks began at
`13:06:50Z`. At `13:21:51Z`, almost exactly 900 seconds later, the package
watchdog reported that it terminated this process tree:

```text
RCMetaStudio.exe --automation-native-smoke
  "...\\sample_projects\\amino.rcms"
```

These timestamps and the termination message are in the
[job log](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29582050470/job/87889867796).
They show that the command, rather than the broader workflow job, exhausted its
explicit bound.

Diagnostic artifact
[`8408056163`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29582050470/artifacts/8408056163)
contains a successful `runtime-probe.json`, a deployment manifest, and a
two-line `packaged-smoke.log`:

```text
packaged-runtime-probe:passed
packaged-workflow:start
```

The runtime probe establishes that the frozen executable loaded the intended
Windows Qt platform, bundled R 4.6.1 library, and rpy2 3.6.7 before the smoke.
It does not establish which later Python/R phase blocked. The absence of
`packaged-workflow:sample-opened` establishes only that the smoke never
returned from all work preceding that marker.

At the failing commit, the marker order was:

1. write `packaged-workflow:start`;
2. call `start_automation()` (resource setup, settings directories, R library
   loading, `MetaForm` construction, native window show);
3. call `meta.open(sample_path)`;
4. process events;
5. write `packaged-workflow:sample-opened`.

See the exact failing source in
[`launch.py`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/launch.py#L421-L456).
Consequently, granular flushed markers around R-library loading, shell
construction, project-open entry/return, painting, and save/reopen are required
for the next hosted discriminator. Retaining stdout, stderr, and a periodic
[`faulthandler.dump_traceback_later()`](https://docs.python.org/3/library/faulthandler.html#faulthandler.dump_traceback_later)
output will make a future timeout actionable even if it occurs at a different
boundary.

### Hosted follow-up: missing frozen schema resources

The added diagnostics made the next hosted failure decisive. In run
[`29586424908`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29586424908),
Windows package job
[`87904466825`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29586424908/job/87904466825)
again reached the unchanged 900-second child watchdog. Diagnostic artifact
[`8409923144`](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29586424908/artifacts/8409923144)
records `packaged-workflow:shell-created` and
`packaged-workflow:project-open:start`, but never
`packaged-workflow:project-open:return`. Its repeating fault-handler stack is
blocked in `QMessageBox.critical()` inside `MetaForm.open()`'s project-load
exception handler.

Inspection of the frozen bundle found none of the three required v1 schema
files (`manifest.schema.json`, `project.schema.json`, and
`state.schema.json`). `project_format._schema()` loads those files through
`importlib.resources.files("rc_metastudio.project_schemas")`, while the
authoritative PyInstaller specification had collected only the compiled icon
resource and rpy2 metadata. The resulting `FileNotFoundError` was translated to
a `ProjectFormatError`, then the normal interactive open boundary displayed a
modal critical dialog. Because packaged automation has no user to dismiss that
dialog, the resource error was hidden until the watchdog expired.

The production correction keeps PyInstaller as the sole collection definition
and adds the three JSON schemas to its data inventory at
`_internal/rc_metastudio/project_schemas/v1`, the exact path used by the frozen
`importlib.resources` reader. Deployment inspection now rejects any package
missing one of those resources and records their hashes in the manifest. A
local clean PyInstaller 6.21 build confirmed all three files at that frozen
path and in the analysis inventory. The frozen runtime probe now loads and
validates all three schemas through `project_format._schema()` and records the
validated members; a local frozen probe completed with that evidence, while the
deployment inspector rejects a probe that omits any member.

Normal interactive project-open failures still display the existing critical
dialog. Packaged automation explicitly requests exception propagation instead,
so the formatted project error and chained traceback are written to retained
diagnostics and the process exits immediately. The same fail-fast mode is used
for the initial sample open, locale-reset open, and saved-project reopen, which
prevents any of those unattended automation boundaries from becoming another
900-second modal wait.

### Local packaged reproduction

The local packaged control used:

```text
build/windows-package/dist/RCMetaStudio/RCMetaStudio.exe
  --automation-native-smoke
  build/windows-package/dist/RCMetaStudio/sample_projects/amino.rcms
```

It was bounded externally and terminated after it failed to return. The
retained diagnostic streams are:

- `build/windows-package/dist/RCMetaStudio/qualification/local-hang-stdout.log`
- `build/windows-package/dist/RCMetaStudio/qualification/local-hang-stderr.log`

The output first proves successful real-rpy2 startup and R package loading. It
then prints `loading ...amino.rcms` and continuously records the exact calls
made by `DatasetModel.update_outcome_if_possible()`: 38 calls to
`effect_for_study`, 114 calls to `generic_convert_scale`, repeated standard
error recovery, and display-effect calculation. The final output is in the
middle of another study calculation rather than at settings save, window
close, or interpreter finalization.

This is direct evidence of repeated synchronous R work, not merely an
inference from the last user-reported `Fail to impute` / `saved settings`
console lines. Those lines can occur during earlier shell initialization and
are not unique phase boundaries.

## Source call graph

At the failing commit, structured open rebuilt the project and unconditionally
installed it through `set_model()`:

- [`meta_form.py` open](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/meta_form.py#L1550-L1616)
  loads the archive, rebuilds the dataset, then calls `set_model()`.
- [`set_model()`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/meta_form.py#L1724-L1773)
  creates a new `DatasetModel`, restores state, and calls `model_updated()`.
- [`model_updated()`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/meta_form.py#L1775-L1796)
  unconditionally calls `try_to_update_outcomes()` for a selected,
  non-diagnostic outcome.
- [`try_to_update_outcomes()`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/ma_data_table_model.py#L2120-L2124)
  synchronously iterates every study.
- [`update_outcome_if_possible()`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/ma_data_table_model.py#L2149-L2299)
  calls `meta_py_r.effect_for_study()` or
  `continuous_effect_for_study()`, overwrites calculation-scale values, and
  converts them again for display.

The loop is on the GUI thread and has no event-processing or batching boundary.
Its duration therefore directly delays both `MetaForm.open()` return and the
next packaged-smoke marker. The local trace is the expected output of this
specific path.

### Secondary QAction path during menu reconstruction

Disabling the direct `model_updated()` recalculation alone is insufficient.
`model_updated()` may rebuild the metric menu by calling
`populate_metrics_menu()`. Qt emits `QAction.toggled` when checked metric actions
are programmatically checked and can also emit it while old checked actions are
torn down by `QMenu.clear()`. Those actions are connected to
`MetaForm.metric_selected()`, which calls
`DatasetModel.try_to_update_outcomes()`. The resulting secondary path is:

`populate_metrics_menu()` -> `QAction.toggled` -> `metric_selected()` ->
`try_to_update_outcomes()` -> per-study rpy2 calculation.

The menu reconstruction therefore blocks signals on the old actions before
clearing them and around each programmatic `setChecked()` call. Signal blocking
is limited to those reconstruction operations and is immediately released, so
a user's later metric selection still emits `toggled` and performs the required
interactive recalculation.

The combined structured-open regression spies on
`try_to_update_outcomes()` across the complete open and event-processing
boundary, not merely the direct `model_updated()` call. It also serializes the
installed dataset back through `project_adapter.dataset_to_project()` and
compares the complete durable dataset representation with the validated sample
project. This proves both that neither direct nor QAction-mediated
recalculation occurred and that all persisted entered-effect metadata survived
the open unchanged.

## Why `.rcms` should restore without recalculation

The repository's own format specification says that project files contain
"durable analysis data" and "complete entered-effect metadata" and that loaded
documents are rebuilt through `project_adapter`; see
[`docs/development/versioned-project-format.md`](../development/versioned-project-format.md).
The implementation is equally explicit:

- [`dataset_to_project()`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/project_adapter.py#L33-L57)
  persists only effect records containing complete calculation and display
  estimates/intervals. Partial display caches are intentionally omitted.
- The serialized record is assigned to each analysis unit as
  `entered_effects` in
  [`project_adapter.py`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/project_adapter.py#L91-L127).
- [`project_to_dataset()`](https://github.com/AliSalman-et-al/rc-metastudio/blob/679290f944039fcbc76c13f46ef3cf15fb6b8d2b/src/rc_metastudio/project_adapter.py#L166-L230)
  constructs every analysis unit and copies each persisted effect record into
  `unit.effects_dict` before returning the dataset.

The committed `sample_projects/amino.rcms` contains 20 studies, 60 analysis
units, and 133 complete persisted effect/comparison records. Recomputing a
single active metric for every study on each open duplicates work already
performed before the durable save, and it overwrites restored values with the
result of the currently installed R stack. That is undesirable even if it were
fast: a document-open boundary should not silently mutate durable analysis
values merely because R/RCMetaR has changed.

An empty `entered_effects` object is still meaningful: it says no complete
effect was durable for that unit/comparison. It is not a command to calculate
every unit during open. Outcome recalculation belongs at the existing edit/new
dataset boundaries, where raw inputs actually changed. This keeps native open
deterministic while preserving the interactive behavior that derives effects
after user edits.

## Recommended production change and proof

1. Add a narrowly scoped `recalculate_outcomes` policy to model installation,
   defaulting to the current recalculation behavior for edits and new/imported
   models.
2. Have structured `MetaForm.open()` explicitly disable that recalculation so
   the already-restored effect dictionary remains authoritative.
3. Add a regression test that spies on
   `DatasetModel.try_to_update_outcomes()` during a real structured-project
   open and asserts it is not called, while the loaded dataset/effect metadata
   still round-trips to the project representation.
4. Retain the current 900-second watchdog. Do not increase it.
5. In the packaged smoke, retain granular phase markers plus redirected stdout,
   stderr, and periodic fault-handler output. Successful qualification should
   require project-open return, paint completion, workflow exercise completion,
   evidence writing, and post-close markers.
6. Validate with the real packaged executable and bundled R, not only the stub
   backend. The decisive hosted proof is that the next run passes the
   `project-open:return` marker quickly and completes the remaining paint,
   save/reopen, surface, and deployment-evidence gates.

## Implementation validation finding: cleanup could mask the real failure

A bounded real-R source smoke after disabling structured-open recalculation
reached `project-open:return`, `sample-opened`, and `paint:complete`; it then
failed during the later packaged-project exercise on a summary identity
mismatch. Repeating with the current source RCMetaR 0.1.2 produced the same new
identity, proving this was not stale local R: the former expected hash encoded
the old behavior that recomputed every study during open. Rebasing the expected
identity to the persisted-effect behavior produced a complete real-R native
smoke in 24.5 seconds, including both locale variants, analysis, save/reopen,
evidence writing, and clean post-close.

Before that cleanup safeguard, the periodic fault-handler trace showed the main
thread blocked in `MetaForm.prompt_to_save_unsaved_data()` from
`start_automation_smoke()`'s `finally` block. In other words, any smoke
assertion after an edit could be replaced by an unattended modal save prompt,
making a deterministic test failure look like another timeout. The retained
phase log, stdout/stderr, and fault-handler trace are therefore not merely
observability improvements: together with non-interactive cleanup they ensure
the next hosted failure, if any, terminates with the actual cause.

## Confidence and remaining uncertainty

Confidence is **high** that unconditional open-time outcome recalculation is a
real, avoidable performance defect and that the local packaged timeout is in
that path. Confidence is **moderate-to-high** that it is the same active block
on the hosted runner: the retained hosted marker is too coarse to prove this
alone, but the same frozen workflow, sample, real-R requirement, source call
graph, and locally observed non-terminating work align.

The next hosted run should be treated as the final discriminator. If it still
hangs before `project-open:start`, the new R-library and shell-construction
markers plus fault-handler stack will identify that independent block. If it
reaches `project-open:start` but not `project-open:return`, the retained Python
stack and stdout should confirm or disprove the recalculation path without any
further timeout increase.
