# Include Windows Packaging in the First Modernization Milestone

The first Python 3 and Qt 5 modernization milestone is not complete until a Windows distributable can be built, because Windows is the repository's active binary target and a desktop GUI application needs a runnable artifact for users who are not source developers. Packaging should come after the headless analysis harness and first GUI compatibility slice so PyInstaller and dependency bundling issues do not obscure core porting problems.

The existing Windows binary workflow is the reference shape for distribution, but its internals can change as needed for Python 3 and PyQt5.
