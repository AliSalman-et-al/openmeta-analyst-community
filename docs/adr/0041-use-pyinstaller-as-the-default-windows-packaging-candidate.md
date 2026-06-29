# Use PyInstaller as the Default Windows Packaging Candidate

The first Python 3 and Qt 5 Windows distributable should start with PyInstaller as the default packaging candidate. The repository already has PyInstaller packaging knowledge, Windows artifact layout checks, and release expectations around a zipped application bundle, so changing packaging tools during the runtime and GUI port would add another major variable.

Packaging can be reconsidered if the dependency feasibility spike or modern R bridge shape proves PyInstaller unsuitable.
