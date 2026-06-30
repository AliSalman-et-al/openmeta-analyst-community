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

Install the required R packages:

```r
Sys.setenv(R_LIBS_USER = "path/to/local/r-library")
source("scripts/install-modern-r-deps.R")
```

Build and install the local `OpenMetaR` package from `src/R`. `HSROC` is installed from the CRAN Archive by `scripts/install-modern-r-deps.R`; `OpenMetaR` is the only local R package.

```sh
cd src/R
R CMD build OpenMetaR
R CMD INSTALL OpenMetaR_1.0.tar.gz
```

## Tests

Run the modern full-app automation test first when checking GUI launch behavior:

```powershell
uv run pytest tests\modern\test_metaform_automation_launch.py
```

Run the remaining modern pytest suite with the automation test excluded:

```powershell
uv run pytest tests\modern --ignore=tests\modern\test_metaform_automation_launch.py
```

## Windows Binary Builds

The maintained Windows build path is the modern Python 3/PyQt5 workflow:

```text
.github/workflows/modern-python.yml
```

It packages `src/launch.py` through PyInstaller so the artifact starts the real `MetaForm` application path. The ZIP includes the PyQt5 runtime, bundled R package sources, sample data, bundled help, and a launcher script as `OpenMetaAnalyst-modern-windows-x64.zip`.

Run the same modern workflow locally with `uv`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-modern-workflow-local.ps1 -ArtifactName OpenMetaAnalyst-modern-windows-x64
```

The local script syncs the committed `uv.lock` into `.venv`, runs `tests\modern` through `uv run`, and builds the modern Windows artifact through PyInstaller.

## macOS Binary Builds

macOS packaging is available as an explicit opt-in path for Intel and Apple Silicon runners:

```bash
bash ./scripts/run-modern-workflow-local.sh --target macos-intel
bash ./scripts/run-modern-workflow-local.sh --target macos-arm64
```

The GitHub workflow keeps Windows active by default on push and pull request. macOS package jobs run from `workflow_dispatch` when `build_macos` is enabled.

Apple Silicon packaging is present as an opt-in CI target. With the current single Qt runtime policy (`PyQt5-Qt5==5.15.2` everywhere), it is experimental because the common PyPI Qt wheel is Intel-only on macOS; the job is isolated from the default Windows build.

## Release Scope

Windows is the active packaged release target. macOS packages are available for build validation and release-candidate work.
