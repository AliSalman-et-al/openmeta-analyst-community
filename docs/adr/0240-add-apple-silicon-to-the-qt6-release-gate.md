# Add Apple Silicon to the Qt6 release gate

The Native Qt6 Port will be release-gated on Windows x64, macOS Intel x64, and macOS ARM64. Apple Silicon will graduate from experimental packaging to supported native qualification during the port because the Qt6/PyQt6 runtime is available for ARM64, but the gate must also prove the architecture-matched Python runtime, bundled R runtime, R packages, PyInstaller application, signing, smoke coverage, and native GUI evidence. Windows ARM64 remains outside this migration's platform scope.
