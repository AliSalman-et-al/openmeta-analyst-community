# Require Meta-Regression and Subgroup Compatibility Before Release

Meta-regression and subgroup analysis are required compatibility areas for the first Python 3 and Qt 5 milestone, but they do not need to be part of the first curated golden set used to bootstrap the harness. The initial harness should start with binary, continuous, diagnostic, and random-effects coverage, then add meta-regression and subgroup golden coverage before the milestone is considered releasable.

This keeps the capture and comparison pipeline small at first while preserving important user-facing analysis functionality before release.
