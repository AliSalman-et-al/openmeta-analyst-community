# Commit a Curated Golden Set and Archive Larger Captures

The repository should commit a small curated golden set that is sufficient to gate core analysis compatibility in normal CI. Larger or exploratory golden output captures should be stored as CI artifacts or release artifacts rather than committed wholesale to the repository.

This keeps compatibility testing reproducible without making the repository large or difficult to review.
