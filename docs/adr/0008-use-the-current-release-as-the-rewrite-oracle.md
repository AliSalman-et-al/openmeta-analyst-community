# Use the current release as the rewrite oracle

The rewrite preserves the user-visible behavior of RC MetaStudio 0.3.1, the active ADRs, released `.rcms` projects, and the accepted tolerances and exceptions in the golden suite. Deleted migration documents, deleted ADRs, and earlier releases remain historical evidence rather than compatibility requirements, so they cannot silently restore behavior that the current product intentionally removed.
