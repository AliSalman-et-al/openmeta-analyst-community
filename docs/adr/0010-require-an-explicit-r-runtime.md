# Require an explicit R runtime

Production startup constructs one real R runtime and fails with a typed actionable error when it cannot start; it never installs a fabricated backend after catching an arbitrary exception. Tests may provide explicit local fakes at narrow application seams, accepting a small amount of test composition in exchange for eliminating plausible but false statistical behavior from production.
