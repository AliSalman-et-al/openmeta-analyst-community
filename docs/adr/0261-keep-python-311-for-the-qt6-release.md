# Keep Python 3.11 for the Qt6 release

Python 3.11 remains the sole supported runtime for the first public Qt6 release, with the same pinned Python patch level used to build Windows x64, macOS Intel x64, and macOS ARM64 artifacts. The project retains `requires-python = ">=3.11,<3.12"`; CI and packaging install from the frozen dependency lock. Adoption of Python 3.12 or later is a separate post-release change rather than part of the Qt, packaging, R, and project-format cutover.
