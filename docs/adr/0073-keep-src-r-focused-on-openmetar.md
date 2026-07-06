# Keep src/R Focused on OpenMetaR

The `src/R` directory should contain only the custom `OpenMetaR` package source after the R Stack cleanup. Third-party R package source trees, generated tarballs, reinstall scripts, temporary R build output, scratch experiments, and legacy ad-hoc testing folders should be removed from `src/R`; reusable verification should live in the modern scripts and test harnesses instead.

Any useful legacy R test intent should be re-implemented deliberately under `OpenMetaR` or the modern test suite, not copied wholesale. This keeps the package source area aligned with current R package conventions while preserving Analysis Behavior through maintained tests.
