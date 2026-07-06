# Add an Identity Migration Audit Script

The RC MetaStudio migration should add a verification script that scans active source, docs, tests, scripts, manifests, packaging metadata, generated outputs, and resources for forbidden legacy identity tokens. The script should use an explicit allowlist for historical ADRs, `NOTICE.md` provenance, scholarly/statistical references, and original copyright notices where old names are historically accurate.

This makes identity cleanup enforceable in CI and avoids relying on manual grep review after broad file moves.

