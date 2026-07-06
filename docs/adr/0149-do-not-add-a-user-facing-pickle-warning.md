# Do Not Add a User-Facing Pickle Warning

RC MetaStudio should not add a user-facing warning solely because the initial `.rcms` project-file container remains pickle-based. The security and portability limitations of pickle should remain documented for maintainers, and the later structured project-file workstream should address them before long-term format stability is claimed.

This avoids adding noisy warning UI during the identity migration while still preserving the technical rationale for replacing pickle later.

