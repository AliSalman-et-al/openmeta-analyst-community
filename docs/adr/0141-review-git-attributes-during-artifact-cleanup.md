# Review Git Attributes During Artifact Cleanup

The RC MetaStudio cleanup phase should review `.gitattributes` for the new repository layout. Source and documentation files should use appropriate text normalization, `.rcms` sample project fixtures should be marked binary if their serialized format requires it, images and icons should remain binary, and generated artifacts should be ignored rather than normalized.

This should be handled as part of generated-artifact cleanup rather than as a separate design project.

