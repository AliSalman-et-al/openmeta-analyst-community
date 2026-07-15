# Retain PyInstaller for the Qt6 port

RC MetaStudio will retain PyInstaller 6.21 as its packaging engine while rebuilding the specification, Qt hooks, binary and data collection, resource registration, plugin assertions, and packaged smoke coverage for PyQt6. A focused feasibility spike must prove Windows x64, macOS Intel x64, and macOS ARM64 before the port depends on the rewritten pipeline; PyInstaller will be reconsidered only if that spike demonstrates a release requirement it cannot satisfy.
