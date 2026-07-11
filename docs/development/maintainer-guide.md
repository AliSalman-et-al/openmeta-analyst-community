# Maintainer Guide

This guide collects source, verification, versioning, and packaging information for RC MetaStudio maintainers. RC MetaStudio is not currently accepting unsolicited public code contributions.

## Run From Source

Use the locked uv environment from the repository root:

```powershell
uv sync --locked
uv run rc-metastudio
```

Source runs require an R installation with the packages used by the analysis backend. Install the required R packages into a local R library:

```r
Sys.setenv(R_LIBS_USER = "path/to/local/r-library")
source("scripts/install-r-deps.R")
```

The bundled private R package is RCMetaR. Packaged releases bundle the required R runtime and packages for normal desktop use.

## Verification

Run the smoke verification lane for the fastest local check:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-smoke.ps1
```

Run the fast verification lane for routine local evidence:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-fast.ps1
```

Run area-specific checks when changing GUI, R Stack, golden analysis, or packaging behavior:

```powershell
uv run pytest tests -m gui
uv run pytest tests -m r_stack
uv run pytest tests -m golden
uv run pytest tests -m packaging_contract
```

See [Agent Testing Guidance](../agents/testing.md) for the maintained verification and packaging lanes.

## Versioning

RC MetaStudio and the bundled RCMetaR package use the same version. To update all maintained version surfaces, run:

```powershell
uv run python scripts\bump_version.py 0.1.2 --date 2026-08-09
```

The script updates `pyproject.toml`, `uv.lock`, application version constants, `r/RCMetaR/DESCRIPTION`, and creates a changelog section when one does not already exist. Edit `CHANGELOG.md` afterward so the release notes describe user-visible changes rather than commit history.

## Packaging And Release

The release workflow builds Windows x64 and macOS Intel x64 packages when a `v*` tag is pushed. Apple Silicon packaging remains experimental and opt-in through manual workflow dispatch.

Package locally only when packaging evidence is needed:

```powershell
.\scripts\package-windows.ps1
```

```bash
bash scripts/package-macos.sh --architecture x64
```

Before packaging a release, confirm that bundled third-party components and assets are recorded in the [Third-Party Inventory](../release/third-party-inventory.md) and that their license notices remain separate from RC MetaStudio copyright and provenance.

Use the product names and policies in the root `README.md`, `NOTICE.md`, `CHANGELOG.md`, and repository ADRs when older historical records conflict with maintained release behavior.
