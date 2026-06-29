# Defer Project File Format Evolution

The first Python 3 and Qt 5 milestone will preserve read compatibility for existing `.oma` project files and will not introduce a new project file format. A future versioned project format is allowed after the port is stable, but it must come with explicit migration tooling and compatibility tests so existing user analyses remain accessible.

Changing the file format during the runtime and GUI port would add risk to the migration and weaken confidence in project-file compatibility.
