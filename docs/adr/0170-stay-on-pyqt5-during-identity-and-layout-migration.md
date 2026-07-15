# Stay on PyQt5 During Identity and Layout Migration

Status: superseded by ADR-0231

RC MetaStudio should stay on PyQt5 during the identity, `.rcms`, RCMetaR, and repository layout migration. Moving to PyQt6 or PySide6 is a separate high-risk workstream and should not be combined with the product rename, file-format break, package rename, and layout changes.

The new layout may make a later Qt binding migration easier, but it should not change the Qt binding target during this migration.
