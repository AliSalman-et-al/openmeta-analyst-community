# Test High-Risk Identity Boundaries First

The RC MetaStudio implementation should add failing verification for high-risk identity boundaries before broad mechanical renames. Initial checks should prove that `.rcms` is the accepted project extension, `.oma` is not supported, active legacy identity tokens are rejected by the audit script, and RCMetaR/`rcmetar.*` names are expected by the Python/R bridge and R package tests.

Full test-first development is not required for every file move, but the behavior-changing identity boundaries should be protected before the large rename and layout changes land.

