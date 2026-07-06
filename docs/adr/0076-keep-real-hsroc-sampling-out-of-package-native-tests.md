# Keep Real HSROC Sampling Out of Package-Native Tests

`OpenMetaR` package-native `testthat` tests should not run real `HSROC` MCMC sampling. Fast R package checks should cover HSROC feasibility and `OpenMetaR` wrapper behavior with deterministic fixtures or mocked `HSROC` and `HSROCSummary` calls, while real archived-`HSROC` execution should remain in the external modern verification suite.

This keeps `R CMD check` stable and reasonably fast without dropping evidence that downloaded `HSROC 2.1.9` installs, exports the required namespace behavior, and can run a low-iteration diagnostic smoke workflow.
