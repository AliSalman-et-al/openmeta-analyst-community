# Use an Out-of-Process R Bridge Before R Stack Modernization

> **Superseded by [ADR 0052](0052-consolidate-on-the-in-process-rpy2-backend.md).** In-process rpy2 was shown to run all analysis types against the bundled R stack, so the out-of-process bridge described below was removed rather than carried forward.

If the dependency feasibility spike shows that the Python 3 runtime cannot use the pinned reference R stack through in-process rpy2, the fallback for Release Cutover is an out-of-process R bridge before upgrading the R stack. This keeps the analysis engine closer to the reference behavior while still allowing the Python 3 and PyQt5 application to move forward.

Upgrading R, rpy2, or analysis packages remains a last resort for the first modernization milestone because it directly increases the risk of statistical drift. Any such upgrade before Release Cutover requires Golden Analysis Test coverage and a documented Compatibility Exception for accepted drift.
