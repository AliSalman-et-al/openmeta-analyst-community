# Use a Polyglot RC MetaStudio Repository Layout

RC MetaStudio should move to a polyglot repository layout that separates the Python desktop application, the RCMetaR package, Qt/application resources, sample projects, tests, scripts, and documentation. The Python application should use a `src/rc_metastudio` package layout; the R package should live as a normal package under `r/RCMetaR`; Qt Designer files, images, and bundled help should live under package resources; sample projects should live under `sample_projects` using `.rcms`; and tests should be grouped by Python, R, integration, and packaging evidence.

This matches current packaging guidance better than the legacy loose `src` tree: Python importable code is separated from repository tooling, RCMetaR keeps standard R package structure, and Qt resources are packaged deliberately instead of mixed with source modules and runtime scratch directories.

