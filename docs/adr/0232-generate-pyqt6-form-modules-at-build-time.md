# Generate PyQt6 form modules at build time

RC MetaStudio will retain its 29 Qt Designer `.ui` files as canonical form sources and remove generated `ui_*.py` modules from version control. The pinned PyQt6 toolchain will run `pyuic6` deterministically during development verification, testing, and packaging to generate importable form modules in an isolated build location; the application will not load loose `.ui` files at runtime. Generation drift and invalid forms will fail before application or package execution.
