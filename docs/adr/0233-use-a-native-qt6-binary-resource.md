# Use a native Qt6 binary resource

RC MetaStudio will compile the canonical `src/rc_metastudio/images/icons.qrc` with the matching official Qt6 `rcc` tool into a binary `.rcc` artifact and register it through `QResource.registerResource()`. The generated Python byte-array resource module will be removed; if build-generated form modules require an `icons_rc` import, that name will resolve to a small application-owned registration module. The build will not depend on `pyqt6rc`, `pyside6-rcc`, a mixed binding toolchain, or the stale `pyqt6-tools` package for resource compilation.
