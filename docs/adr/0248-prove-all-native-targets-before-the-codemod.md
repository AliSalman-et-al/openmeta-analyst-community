# Prove all native targets before the codemod

Before the broad PyQt6 codemod runs, RC MetaStudio will complete a minimal feasibility spike on Windows x64, macOS Intel x64, and macOS ARM64. Each target must prove the locked PyQt6 runtime, `pyuic6` generation, official Qt6 binary-resource compilation and registration, SVG rendering, R/rpy2 initialization, PyInstaller assembly, platform-plugin loading, and native packaged smoke execution. Broad source conversion will not begin around a toolchain that has not demonstrated all required release architectures.
