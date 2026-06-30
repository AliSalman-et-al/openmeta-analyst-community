# Use Package-Native testthat for OpenMetaR R Tests

Retained R-level tests for `OpenMetaR` should be rewritten as package-native `testthat` tests under `src/R/OpenMetaR/tests/testthat`, with `testthat` declared in `Suggests`, so fast package behavior checks run during `R CMD check`. Heavier end-to-end verification that crosses the Python/rpy2 bridge, GUI automation, or artifact packaging boundary should remain in the modern external test and verification workflow.

Legacy ad-hoc R test files should be mined for useful Analysis Behavior intent rather than copied wholesale. Commented manual snippets, scratch experiments, and obsolete dependency paths should be removed unless they protect an active user-facing workflow.
