# Use a dedicated small-study effects boundary

The small-study effects analysis runs several plots, tests, and sensitivity analyses, so it does not fit the existing one-method `AnalysisRequest`. A dedicated immutable request crosses one serialized R bridge operation that converts the dataset, computes eligibility, and executes the accepted request. Plot-only regeneration remains separate, and results use the existing Results window rather than a second result system.
