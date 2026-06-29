# Defer R Stack Modernization Until After Python Qt Port

The first modernization milestone will keep the R stack pinned to the reference environment while porting the application to Python 3 and Qt 5. Upgrading R, rpy2, bundled R packages, or external R packages during the same milestone would make statistical drift harder to attribute and could hide whether regressions came from the Python/Qt port or from changed analysis engines.

R-stack modernization can be planned as a separate migration after golden analysis tests pass against the reference behavior.
