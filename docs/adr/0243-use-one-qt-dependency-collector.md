# Use one Qt dependency collector

PyInstaller will be the sole collector of Qt6 libraries, plugins, and application dependencies for RC MetaStudio packages. The pipeline will not overlay `windeployqt` or `macdeployqt` onto PyInstaller output; instead, a checked deployment manifest and packaged runtime probes will fail closed on missing, unexpected, duplicated, or mismatched platform, image-format, SVG, style, accessibility, and other required plugin families before signing and promotion.
