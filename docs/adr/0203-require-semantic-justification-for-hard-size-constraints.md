# Require Semantic Justification for Hard Size Constraints

Hard-coded size constraints are permitted only for a documented Semantic Size Invariant, such as a square swatch or icon-only control, a numeric field bounded to its valid value range, an Intrinsic-Ratio Artifact, or a minimum interactive size derived from the active Qt style. Fixed root sizes, historical form dimensions, fixed label widths, and arbitrary control caps must be removed in favor of size hints, policies, layouts, or explicit Overflow Boundaries.
