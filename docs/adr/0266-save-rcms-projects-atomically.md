# Save RCMS projects atomically

Every `.rcms` save is a crash-safe atomic replacement. The writer creates the complete container in a temporary file on the destination filesystem, validates its schemas and integrity metadata, flushes file content before replacement, and replaces the target only after every step succeeds. A failed save leaves the prior project untouched and reports an actionable error. Temporary files follow an explicit recovery and cleanup policy and are never silently treated as valid projects.
