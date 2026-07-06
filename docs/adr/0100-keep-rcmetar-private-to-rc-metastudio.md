# Keep RCMetaR Private to RC MetaStudio

RCMetaR should be treated as a private bundled implementation package for RC MetaStudio, not a public R package with a stable external interface. It must remain independently buildable and testable, but its callable `rcmetar.*` surface is maintained for the Python desktop application and internal verification rather than direct downstream R users.

This allows RCMetaR to be renamed, reshaped, and reorganized during modernization without preserving public R API compatibility promises. A later decision can promote RCMetaR to a public package if direct R-user support becomes a product goal.

