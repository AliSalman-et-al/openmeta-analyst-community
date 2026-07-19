# Ship separate native macOS artifacts

RC MetaStudio will build and release separate macOS Intel x64 and Apple Silicon ARM64 application artifacts rather than a universal2 bundle. Each artifact will contain an architecture-matched Python runtime, PyQt6/Qt6 stack, bundled R runtime, compiled R packages, rpy2 bridge, and application bootloader, and each will pass its own signing, smoke, native GUI, and promotion gates under one shared release contract.
