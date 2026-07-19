# Separate project state from machine settings

`state.json` contains only durable project-scoped state that should travel with an `.rcms` file, including the active outcome, analysis selections, project-level display choices, and artifact metadata. Window geometry, screen placement, recent paths, theme, and other machine-local preferences remain in versioned `QSettings`. Ephemeral widget focus, transient selection highlighting, open-dialog state, and raw Qt objects or byte blobs are not persisted in either project data member.
