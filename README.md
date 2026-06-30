# OpenMeta[Analyst] Community

OpenMeta[Analyst] Community is a community-maintained fork of the original OpenMeta[Analyst] project. It is not affiliated with or endorsed by Brown University or the original maintainers.

OpenMeta[Analyst] is an open-source application for conducting meta-analyses from a graphical desktop interface.

## Running From Source

The maintained application path uses Python 3.11, PyQt5, and the uv-managed environment committed in `pyproject.toml` and `uv.lock`.

```powershell
uv sync --locked
uv run python src\launch.py
```

## R Dependencies

Normal desktop users do not need to manually install R or R packages before running the Windows distributable. Developer source runs need an R installation with the packages used by the analysis backend.

Install the required R packages. The installer uses `OMA_CRAN_REPO` when set and defaults to `https://cloud.r-project.org`.

```r
Sys.setenv(R_LIBS_USER = "path/to/local/r-library")
Sys.setenv(OMA_CRAN_REPO = "https://cloud.r-project.org")
source("scripts/install-modern-r-deps.R")
```

Build and install the local `OpenMetaR` package from `src/R`. `HSROC` is installed from the CRAN Archive by `scripts/install-modern-r-deps.R`; `OpenMetaR` is the only local R package.

```sh
cd src/R
R CMD build OpenMetaR
R CMD INSTALL OpenMetaR_1.0.tar.gz
```

## Tests

Warm local verification skips dependency sync by default. Run the Smoke Verification Lane for the fastest first check:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-modern-smoke.ps1
```

Daily source verification uses the Fast Verification Lane:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-modern-fast.ps1
```

Use `-Sync` when dependency inputs changed, or `-RecreateVenv` for a clean environment rebuild. The Fast Verification Lane runs `tests\modern\fast`, `tests\modern\golden`, and `tests\modern\packaging_contract` with a bounded pytest-xdist worker count by default. Use `-FastWorkers 1` when debugging a fast-lane failure without parallel workers. CI always calls the lane scripts with `-Sync`.

Run GUI or R Stack lanes directly when working in those areas:

```powershell
uv run pytest tests\modern -m gui
powershell -ExecutionPolicy Bypass -File .\scripts\verify-modern-r-stack-full.ps1
```

## Windows Binary Builds

Fast verification and packaging are separate GitHub workflows:

```text
.github/workflows/modern-fast.yml
.github/workflows/modern-package.yml
```

It packages `src/launch.py` through PyInstaller so the artifact starts the real `MetaForm` application path. The ZIP includes the PyQt5 runtime, bundled R package sources, sample data, bundled help, and a launcher script as `OpenMetaAnalyst-modern-windows-x64.zip`.

Build the modern Windows package locally only when packaging evidence is needed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-modern-windows.ps1 -ArtifactName OpenMetaAnalyst-modern-windows-x64
```

The packaging script syncs the committed `uv.lock`, runs Full R Stack Evidence unless skipped, and builds the modern Windows artifact through PyInstaller.

Full R Stack Evidence and packaging share the R dependency cache under `artifacts\r-library-cache` by default. The package wrapper uses one source R runtime for both verification and artifact assembly, then reinstalls only the local `OpenMetaR` package into the bundle. Delete that cache only when debugging dependency acquisition or intentionally forcing a cold R package install.

## macOS Binary Builds

macOS packaging is available as an explicit opt-in path for Intel and Apple Silicon runners:

```bash
bash ./scripts/package-modern-macos.sh --architecture x64
bash ./scripts/package-modern-macos.sh --architecture arm64
```

The GitHub fast workflow runs on push and pull request. Package jobs run from `workflow_dispatch`, release tags, and packaging-relevant path changes. macOS package jobs remain manual opt-in.

Apple Silicon packaging is present as an opt-in CI target. With the current single Qt runtime policy (`PyQt5-Qt5==5.15.2` everywhere), it is experimental because the common PyPI Qt wheel is Intel-only on macOS; the job is isolated from the default Windows build.

## Release Scope

Windows is the active packaged release target. macOS packages are available for build validation and release-candidate work.
