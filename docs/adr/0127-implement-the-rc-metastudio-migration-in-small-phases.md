# Implement the RC MetaStudio Migration in Small Phases

The RC MetaStudio identity and layout migration should be implemented as a sequence of small, reviewable phases rather than one broad change. Suggested phases are: legal/provenance docs and README rewrite; Python, R, project, and environment-variable identity renames; `.rcms` project-file extension and sample conversion; repository layout moves with import/path updates; CI, script, test, and documentation lane renames; packaging, executable, and artifact renames; removal of bundled help and callbacks; and cleanup of generated/cache artifacts.

Each phase should compile and run its relevant verification before the next phase begins so regressions remain diagnosable.

