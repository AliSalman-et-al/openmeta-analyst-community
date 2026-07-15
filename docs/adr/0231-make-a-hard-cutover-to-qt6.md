# Make a hard cutover to Qt6

RC MetaStudio will make a one-way Qt6 Hard Cutover rather than keep parallel PyQt5 and PyQt6 development or release lines. Once the dependency transition begins, Qt6/PyQt6 becomes the only supported GUI runtime for source execution, verification, packaging, and release; the project will not maintain a PyQt5 fallback, dual-binding facade, or second releasable Qt line. This supersedes ADR-0170 now that the identity and layout migrations it protected are complete.
