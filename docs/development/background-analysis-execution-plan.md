# Background analysis execution plan

## Timing

Begin after the first public Qt6 release is stable. Do not mix this work into the Native Qt6 Port.

## Goal

Run long analyses without blocking the GUI while preserving Analysis Behavior, deterministic project state, actionable failures, and safe application shutdown.

## Required design work

1. Inventory every analysis entry point, R/rpy2 call, progress surface, mutable project dependency, and generated artifact.
2. Prototype the execution boundary on every supported platform. Compare a dedicated worker process with a Qt-owned worker object, giving priority to isolation from rpy2 and R global state.
3. Define immutable request and result messages at the Analysis Adapter boundary. Qt widgets and models must not cross the boundary.
4. Define progress, cancellation, timeout, worker-crash, R-error, and application-shutdown state transitions before wiring the interface.
5. Implement one representative binary analysis vertically and prove numerical and artifact equivalence against synchronous execution.
6. Expand through the workflow inventory only after the representative slice passes stress, repeated-run, cancellation, and shutdown tests.

## Required invariants

- All widget and Qt model mutation occurs on the GUI thread.
- A run consumes a stable input snapshot and cannot observe later interface edits.
- Cancellation never publishes partial results as successful output.
- Worker failure leaves the project usable and produces an actionable diagnostic.
- Closing the application cannot orphan a worker or corrupt a project save.
- Golden Analysis Test outputs remain equivalent within their existing tolerances.

## Completion evidence

- State-machine unit tests and cross-process message-contract tests.
- Real R integration tests for success, error, timeout, cancellation, and repeated runs.
- GUI tests proving responsiveness, progress, cancellation, and close-during-run behavior.
- Packaged smoke evidence on Windows x64, macOS Intel x64, and macOS ARM64.
- Updated architecture and user documentation before release.
