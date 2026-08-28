# Verification Build and Test Workflow Plan

This is the current verification strategy. ADR 0078 defines the split between
source verification and packaging; ADR 0080 defines fail-closed R evidence;
ADR 0280 records why lane directories replace the retired per-node taxonomy.

## Lane ownership

Test directories are authoritative and markers are registered for selection:

- `tests/python/fast`: hermetic Python and small Qt contracts;
- `tests/python/gui`: serialized offscreen GUI workflows;
- `tests/analysis_regression/golden`: frozen statistical compatibility;
- `tests/r_stack`: real R/rpy2 and package behavior;
- `tests/packaging/contract`: structured packaging and workflow contracts.

The shared pytest setup derives lane markers from these paths. GUI selections
create one offscreen `QApplication`; GUI and explicitly marked `qsettings`
modules receive isolated per-test `QSettings` storage. No per-node metadata
manifest is generated or checked. Shared process state stays out of parallel
lanes unless the owning tests prove isolation.

## Pull-request verification

1. Run the fast lane over `tests/python/fast` and the golden directory, with
   bounded xdist workers only for those isolated paths.
2. Run the GUI, R Stack, and packaged-smoke evidence in their serialized lanes.
3. Run `tests/packaging/contract` once in the package-relevant job rather than
   once per source platform.
4. For Qt changes, run the native Qt6 cutover checks and platform workflows.

The smoke command remains an optional local preflight. The pull-request source
matrix deliberately invokes the fast runner once per target; the fast runner
already owns its resource generation and prerequisite checks.

Required R lanes set their prerequisite policy before pytest starts. Missing R,
rpy2, or required packages fails that lane; ordinary local selections may
still skip when prerequisites are unavailable. Packaging and release jobs keep
their own native artifact, signing, and deployment evidence.

## Local commands

```powershell
uv run pytest tests/python/fast tests/analysis_regression/golden
uv run pytest tests/python/gui
uv run pytest tests/r_stack
uv run pytest tests/packaging/contract
```

Use `uv run python scripts/verify.py smoke` for a quick preflight, `uv run python
scripts/verify.py fast --require-r-evidence` for the maintained source lane, and
`uv run python scripts/verify.py r-stack --sync` for a cold Full R Stack setup
and run. Omit `--sync` when the locked environment is already synchronized. Keep
workflow and package inputs path-aware, and prefer executable or structured
contract seams over source-spelling assertions.
