# Assign Runtime Geometry Ownership by Window Archetype

RC MetaStudio will compute screen-bounded geometry before first display, then transfer runtime Geometry Ownership of Workspace and Workflow Windows to the user and window manager so content changes do not cause disruptive window jumps. Transactional Dialogs and Transient Windows may continue to refit as their content changes, while screen or DPI transitions may clamp and reposition any window only as needed to keep it reachable.
