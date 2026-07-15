# Defer background analysis execution

The Native Qt6 Port will preserve current analysis-execution semantics and will not introduce a general worker-thread or worker-process architecture. The port will still make Qt object ownership, teardown, signal delivery, and application shutdown correct under PyQt6. Responsive cancellable background analysis is a planned post-release workstream with its own R-ownership, progress, cancellation, failure, and shutdown contracts.
