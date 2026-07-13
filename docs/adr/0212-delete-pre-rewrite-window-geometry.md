# Delete Pre-Rewrite Window Geometry

When the adaptive-layout rewrite ships, RC MetaStudio will delete saved geometry and layout-state keys created by the previous sizing implementation rather than migrate or validate them. The new versioned placement schema will start clean for every Workspace Window role, fall back to the new archetype defaults without prompting, and leave unrelated application settings untouched.
