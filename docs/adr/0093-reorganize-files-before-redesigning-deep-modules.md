# Reorganize Files Before Redesigning Deep Modules

After the RC MetaStudio identity migration, the next restructuring step should update filenames, package paths, repository layout, and generated/runtime artifact names to modern RC MetaStudio conventions before moving implementation code into new deep modules. Deep-module redesign remains a later workstream.

This keeps the first reorganization mechanical and reviewable: imports, package metadata, tests, scripts, docs, and packaging can be updated around the new file layout without simultaneously changing module interfaces or analysis behavior.

