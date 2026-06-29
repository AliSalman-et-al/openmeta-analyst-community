# Target Python 3 and Qt 5 Before Qt 6

OpenMeta[Analyst] Community is being revitalized from a legacy Python 2.7 and Qt 4 codebase while preserving the existing analysis behavior and a roughly similar desktop GUI. We will first port to Python 3 and Qt 5, rather than moving directly to Qt 6, because Qt 6 would combine the Python runtime migration, Qt API migration, and larger GUI behavior changes into too many simultaneous failure points.

The analysis behavior is the highest-risk compatibility surface, so the migration should prefer staged, verifiable changes over a larger framework jump.
