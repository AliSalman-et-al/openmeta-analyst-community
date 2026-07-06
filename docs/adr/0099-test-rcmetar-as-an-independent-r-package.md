# Test RCMetaR as an Independent R Package

RCMetaR should be buildable and testable as a normal R package from `r/RCMetaR`, including package-native `R CMD build`, `R CMD check`, and `testthat` coverage without launching the Python GUI. The Python application should then verify integration through focused bridge and end-to-end tests that load and call RCMetaR through the maintained analysis execution path.

This gives the R analysis layer its own maintainable evidence while still protecting the full RC MetaStudio desktop stack.

