# Use a fail-closed PyQt6 codemod

RC MetaStudio will automate mechanical PyQt6 source rewrites with an application-owned, idempotent LibCST codemod and an explicit mapping manifest. The codemod may rewrite imports and unambiguous scoped enums, must refuse unknown or ambiguous patterns, must report every transformation, and must produce no changes on a second run. Canonical forms will be regenerated instead of transformed, while coordinate spaces, overloaded signals, model roles, flags, ownership, and other behavioral semantics will be migrated manually behind focused tests.
