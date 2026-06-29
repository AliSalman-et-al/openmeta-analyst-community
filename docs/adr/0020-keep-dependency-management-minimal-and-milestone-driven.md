# Keep Dependency Management Minimal and Milestone Driven

Dependency management changes during the first Python 3 and Qt 5 milestone should be limited to what is needed for a reproducible modern Python environment, CI, and Windows packaging. A broader packaging-system redesign is out of scope until compatibility slices are stable, because the primary goal is preserving analysis behavior rather than making the repository packaging architecture elegant.

`uv` is the modern Python environment and command runner for Release Cutover because its project workflow supports `pyproject.toml`, lockfiles, `uv sync --locked`, `uv run`, and GitHub Actions setup. It owns Python selection, dependency sync, lockfile reproducibility, and developer and CI commands. It is not a replacement for the Windows distributable builder; PyInstaller remains the packaging candidate unless it proves unsuitable.
