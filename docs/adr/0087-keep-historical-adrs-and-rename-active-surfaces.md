# Keep Historical ADRs and Rename Active Surfaces

Historical ADRs should remain decision records even when later RC MetaStudio decisions supersede their naming or compatibility targets. Active product surfaces, user and developer docs, tests, manifests, comments, scripts, generated artifacts, package metadata, and runtime identifiers should be rewritten to RC MetaStudio, RCMetaR, `rcmetar.*`, and `.rcms`; older ADRs should only receive explicit supersession notes when that is needed to prevent misreading.

This keeps the modernization history auditable while making the maintained codebase and product surface consistently use the RC MetaStudio identity.

