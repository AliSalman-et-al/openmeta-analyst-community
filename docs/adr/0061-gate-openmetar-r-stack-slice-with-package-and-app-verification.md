# Gate Openmetar R Stack Slice with Package and App Verification

The `openmetar` R Stack modernization slice is not complete when `R CMD build` and `R CMD check` pass alone. The slice must also install bundled `HSROC` plus modernized `openmetar` into an isolated R library, run the R analysis smoke test, run the relevant modern Python/rpy2 bridge tests, and verify the modern artifact workflow where feasible.

R package checks prove package structure and namespace correctness, but the application relies on dynamic R method discovery, rpy2 result parsing, generated plots, and bundled-library packaging that can fail even when the package is formally valid.
