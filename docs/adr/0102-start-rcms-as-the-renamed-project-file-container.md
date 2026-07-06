# Start RCMS as the Renamed Project File Container

The first RC MetaStudio project-file migration should make `.rcms` the supported project-file extension while initially preserving the current serialized project content shape. A file-format version marker should be added as soon as practical, but a full structured storage redesign should be handled in a later workstream after the identity and layout migration is stable.

This allows sample projects, file dialogs, packaging checks, and tests to move off `.oma` without combining the rename with a risky persistence rewrite.

