# OpenMeta[Analyst] Community

OpenMeta[Analyst] Community is a community-maintained fork of the original OpenMeta[Analyst] project. It is not affiliated with or endorsed by Brown University or the original maintainers.

OpenMeta[Analyst] is an open-source application for conducting meta-analyses from a graphical desktop interface.

## Running From Source

To run OpenMeta[Analyst] Community from source, install the R and Python dependencies, build the bundled R packages, and then launch the Python GUI.

Binary builds for the original project were historically distributed from:

<http://www.cebm.brown.edu/openmeta>

## R Dependencies

Install the required R packages:

```r
install.packages(c("metafor", "lme4", "MCMCpack", "igraph"))
```

Build and install the bundled `HSROC` package and the bundled `openmetar` package from `src/R`.

These packages are distributed with the source tree. Use the bundled `HSROC` package, not the CRAN package.

```sh
cd src/R
R CMD build HSROC
R CMD build openmetar
R CMD INSTALL HSROC_2.0.5.tar.gz
R CMD INSTALL openmetar_1.0.tar.gz
```

This branch uses R 3.x. The legacy Windows build currently targets R 3.3.2 in CI.

## Python Dependencies

Install Python 2.7 and the required libraries:

- PyQt4
- Qt
- rpy2

The original project used PyQt 4.10. The community build environment currently uses PyQt 4.11.4 and rpy2 2.8.5.

Verify `rpy2` from a Python console:

```python
import rpy2
from rpy2 import robjects
```

Launch the GUI:

```sh
python src/launch.py
```

## Tests

The legacy nose tests are run from the `src` directory:

```sh
cd src
nosetests -v test_meta_analysis.py
```

Some tests load optional network meta-analysis dependencies such as `gemtc`, which are not part of the default desktop binary build.

## Windows Binary Builds

The repository includes a GitHub Actions workflow for building a Windows x64 binary artifact:

```text
.github/workflows/windows-binary.yml
```

The workflow creates a legacy conda environment, compiles the bundled R packages, packages the PyQt4 application with PyInstaller, bundles the R runtime and sample data, and uploads `OpenMetaAnalyst-windows-x64.zip` as a workflow artifact.

The same steps can be run locally on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-r-deps.ps1 -EnvName openmeta-analyst-community
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows-binary.ps1 -EnvName openmeta-analyst-community -ArtifactName OpenMetaAnalyst-windows-x64
```

## macOS Binary Builds

The repository includes a GitHub Actions workflow for building a macOS x64 binary artifact:

```text
.github/workflows/macos-binary.yml
```

The workflow creates a legacy conda environment on an Intel macOS runner, compiles the bundled R packages, packages the PyQt4 application with PyInstaller as `OpenMetaAnalyst.app`, bundles the conda R runtime and sample data, and uploads `OpenMetaAnalyst-macos-x64.zip` as a workflow artifact.

When a `v*` tag is pushed, the Windows and macOS workflows both create the GitHub Release only if it does not already exist, then upload their platform-specific ZIP asset.

The same steps can be run locally on macOS:

```bash
bash ./scripts/install-r-deps.sh openmeta-analyst-community
bash ./scripts/build-macos-binary.sh openmeta-analyst-community OpenMetaAnalyst-macos-x64
```

## Legacy Dependency Notes

Important dependency versions:

| Dependency | Version |
| --- | --- |
| R | 3.x |
| Python | 2.7 |
| metafor | 1.6.0-ish historically; CI installs archived `1.9-9` |
| PyQt4 | 4.10-ish historically; CI uses 4.11.4 |
