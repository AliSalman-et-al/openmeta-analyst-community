# Split cross-platform source and package cadence

Qt-affecting pull requests will run source-level Smoke and Fast Verification on Windows x64, macOS Intel x64, and macOS ARM64. Full R-bundled packaged qualification will run for scheduled or manually requested candidates and is mandatory on all three targets before the Qt6 hard cutover and every release; package signing and immutable promotion remain candidate-only operations rather than per-commit work.
