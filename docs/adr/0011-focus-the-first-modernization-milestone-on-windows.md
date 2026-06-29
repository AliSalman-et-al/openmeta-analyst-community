# Focus the First Modernization Milestone on Windows

The first Python 3 and Qt 5 modernization milestone will use Windows as the platform acceptance target for the distributable application. Source-level portability should not be blocked intentionally, but macOS and Linux packaging are deferred because Windows is the active binary target in the repository and additional platform work would multiply dependency, packaging, and GUI variables before analysis compatibility is proven.

macOS and Linux support can be revisited after the Windows distributable, headless analysis harness, and first GUI compatibility slice are stable.
