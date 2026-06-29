# Port by Runnable Compatibility Slices

The Python 3 and Qt 5 migration will be organized around runnable compatibility slices rather than a single repository-wide mechanical conversion. The first slices should make analysis behavior testable outside the full GUI, then progressively bring up launch and main GUI workflows while comparing behavior against the reference implementation.

A broad `2to3` plus PyQt import rewrite would create a large diff with unclear behavior changes around strings, Qt compatibility types, generated UI files, and rpy2 conversions.
