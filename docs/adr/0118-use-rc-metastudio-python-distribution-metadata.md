# Use RC MetaStudio Python Distribution Metadata

The Python project metadata should use the maintained RC MetaStudio identity. `pyproject.toml` should name the distribution `rc-metastudio`, describe RC MetaStudio rather than OpenMeta[Analyst] Community or modernization, and define package entry points for the application startup path.

Once the importable package exists under `src/rc_metastudio`, the project should no longer rely on `package = false` as the long-term configuration.

