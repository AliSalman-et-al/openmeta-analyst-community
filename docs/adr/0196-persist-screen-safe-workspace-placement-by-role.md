# Persist Screen-Safe Workspace Placement by Role

Main, Results, Edit Dataset, and Network View will each persist independent Remembered Workspace Placement across application sessions, including outer geometry, window state, and meaningful user-controlled splitter proportions. Restoration must validate the placement against the current screen configuration and clamp stale geometry after monitor, resolution, or DPI changes; content-derived minimum sizes are layout facts and must never be stored as user preferences.
