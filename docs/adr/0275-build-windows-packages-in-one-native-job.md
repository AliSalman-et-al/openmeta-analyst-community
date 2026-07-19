# Build Windows packages in one native job

Windows x64 packaging is one linear, target-native operation. The public
`scripts/package-windows.ps1` command authenticates and privately stages the
official R installer, synchronizes the locked Python environment, rebuilds
rpy2 in API mode against that staged R, installs the locked R library, generates
resources, builds the PyInstaller onedir application, inspects it, runs the
frozen user-entry workflow, writes the versioned ZIP, then extracts those exact
bytes into a clean directory and repeats deployment inspection and the normal
user-entry workflow before writing evidence. The ZIP name and its sole root are
both derived once from the project version: `RCMetaStudio-{version}-windows-x64`.

GitHub Actions invokes that same command on `windows-2025`; it does not produce,
promote, download, or consume an R Integration Kit. Caches may contain immutable
downloads only (for example the authenticated R installer and uv downloads).
Installed R trees, compiled rpy2 bridges, PyInstaller work/output, final
applications, and qualification results are never cache inputs.

PyInstaller remains the sole Qt collector and rpy2 API mode is mandatory:
`R_HOME` selects the staged private runtime, `RPY2_CFFI_MODE=API` is set before
the bridge build and freeze, and inspection records the direct embedded-R/API
bridge hashes rather than a retired kit identity; it rejects an ABI fallback. The detailed
rationale and target-wide follow-on work live in the durable packaging research
note.
