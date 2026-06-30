# Testing

The maintained test workflow uses the uv-managed Python 3.11/PyQt5 environment in `pyproject.toml` and `uv.lock`, with pytest tests under `tests/modern`.

## Modern uv environment

Sync the locked modern environment from the repository root:

```powershell
uv sync --locked
```

Warm local verification skips dependency sync by default. Run the Smoke Verification Lane for the fastest first check:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-modern-smoke.ps1
```

Daily local verification uses the Fast Verification Lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-modern-fast.ps1
```

Use `-Sync` when dependency inputs changed, or `-RecreateVenv` for a clean environment rebuild. GitHub calls smoke and fast verification with `-Sync`.

Run lane-specific tests when working in an area:

```powershell
uv run pytest tests\modern -m gui
uv run pytest tests\modern -m r_stack
uv run pytest tests\modern -m golden
uv run pytest tests\modern -m packaging_contract
```

Run Full R Stack Evidence before R Stack changes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-modern-r-stack-full.ps1
```

Full R Stack Evidence uses `artifacts\r-library-cache` by default to avoid repeated CRAN downloads on warm runs. Set `OMA_CRAN_REPO` to choose a faster reliable CRAN-compatible mirror when needed.

Build the Windows package only when packaging evidence is needed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-modern-windows.ps1 -ArtifactName OpenMetaAnalyst-modern-windows-x64
```

On macOS, use the package script for the matching host architecture:

```bash
bash ./scripts/package-modern-macos.sh --architecture x64
bash ./scripts/package-modern-macos.sh --architecture arm64
```

Windows remains the default active package target. macOS package jobs are opt-in through the GitHub Actions `workflow_dispatch` inputs.

The Apple Silicon package job is currently experimental under the single Qt runtime policy because `PyQt5-Qt5==5.15.2` is the newest PyPI Qt5 runtime wheel with Windows support, but its macOS wheel is Intel-only.

## GUI paint coverage

Modern GUI tests run with `QT_QPA_PLATFORM=offscreen`, which lays out widgets but never
paints them. Paint-only code paths are therefore invisible to most tests: Qt queries
`data()`/`headerData()` for paint roles such as `Qt.BackgroundColorRole`, `Qt.DecorationRole`,
and `Qt.FontRole` only while rendering, not during offscreen layout or `sizeHint`. A
Python-3 porting bug in one of those branches raises out of the C++ paint virtual and
aborts the process with exit code `0xC0000409` and no traceback.

Two mechanisms guard this class of bug; keep both working when touching table models or
delegates:

- `tests/modern/gui/test_metaform_automation_launch.py::test_table_paint_roles_do_not_raise_across_all_cells`
  sweeps every cell and header section against all paint roles in-process, turning a
  paint-time abort into a clean test failure. Extend it when a model gains new roles.
- The packaged smoke test (`launch.start_automation_smoke` via `Invoke-PackagedAppSmokeTest`)
  calls `load_R_libraries` and forces a real paint pass (`_force_table_paint`) so both
  R-bridge and paint regressions fail the build gate with a non-zero exit instead of
  shipping. The plain `--automation-smoke` flag alone does not paint.

## R package setup in focused tests

`DatasetModel` initialization calls OpenMeta R functions such as `set.global.conf.level`. Focused tests that instantiate `DatasetModel` without the full application setup should load only the needed package:

```python
meta_py_r.RlibLoader().load_OpenMetaR()
```

Avoid `load_all()` for narrow tests unless network meta-analysis packages are required; this local environment currently lacks `gemtc`.
