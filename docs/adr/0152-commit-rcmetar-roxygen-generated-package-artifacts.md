# Commit RCMetaR Roxygen-Generated Package Artifacts

RCMetaR should commit generated R package artifacts such as `NAMESPACE` and `man/` documentation when they are required by normal R package build and check workflows. Roxygen comments in `R/*.r` remain the documentation source, and generated artifacts should be refreshed through documented tooling.

This is an intentional exception to the general rule against committed generated artifacts because R package workflows commonly expect these files, unlike disposable Python Qt generated UI modules.

