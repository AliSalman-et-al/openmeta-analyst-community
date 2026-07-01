# Serialize In-Process R Backend Calls

The maintained Modern CI Path keeps the in-process rpy2 backend from ADR 0052, but every Python-to-R backend entry is now guarded by one process-wide reentrant serializer. This prevents rapid GUI edits, automation, or worker callbacks from overlapping calls into the embedded R interpreter while preserving existing synchronous Analysis Behavior; debouncing remains a possible UI improvement, but it is not the safety boundary for rpy2 re-entry.
