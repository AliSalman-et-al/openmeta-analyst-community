# Accept native Qt6 visual differences

The Native Qt6 Port preserves user workflows, information hierarchy, control availability, accessibility semantics, and established layout contracts but does not reproduce Qt5 pixels. Normal Qt6 and platform differences in fonts, spacing, widget chrome, and native styling are accepted. Existing Qt5 image baselines may be replaced only after human review of representative rendering; cross-platform release gates will prefer geometry, visibility, and interaction assertions over exact pixel equality.
