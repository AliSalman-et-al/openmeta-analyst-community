# Stay on Python 3.11 During Identity and Layout Migration

RC MetaStudio should keep Python 3.11 as the target runtime during the identity, `.rcms`, RCMetaR, and repository layout migration. Python runtime upgrades should be handled in a later dependency/runtime workstream.

This keeps migration failures attributable to the rename and layout work rather than mixing in Python runtime compatibility changes.

