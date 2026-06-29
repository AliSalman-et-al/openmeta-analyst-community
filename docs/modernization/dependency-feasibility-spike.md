# Dependency Feasibility Spike

Issue: #29

## Result

The modern developer and CI environment is represented as a uv project targeting Python 3.11 with PyQt5 5.15.11, PyQt5-Qt5 5.15.2, pytest 9.1.1, PyInstaller 6.21.0, and rpy2 3.6.7. PyQt5 5.15.11 is the latest PyQt5 binding release. PyQt5-Qt5 5.15.2 is the newest Qt5 runtime wheel version published for Windows. Newer PyQt5-Qt5 releases exist, but they do not publish Windows wheels, so they cannot be used while preserving the active Windows build.

## R bridge shape

The modern Python 3.11 environment uses the in-process rpy2 backend for R-backed analysis. When R or rpy2 is unavailable in focused GUI tests, the modern path uses the no-R stub described in ADR 0052 rather than restoring the superseded out-of-process bridge.

## Pinned stack

- Python 3.11
- PyQt5 5.15.11
- PyQt5-Qt5 5.15.2, the newest PyPI Qt5 runtime wheel version with Windows support
- pytest 9.1.1
- PyInstaller 6.21.0
- rpy2 3.6.7

## Workflow

Windows CI installs uv, runs `uv sync --locked`, runs modern tests with `uv run pytest tests/modern`, and builds the modern artifact through the uv-managed environment.
