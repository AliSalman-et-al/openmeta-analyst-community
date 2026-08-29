# Agent instructions

Keep the implementation as simple as the product allows. Remove accidental complexity instead of hiding it behind another layer.

## Engineering rules

- Solve the current problem. Do not design for hypothetical requirements.
- Prefer direct, readable code over clever code or speculative abstractions.
- Use types to make invalid states and bad calls visible before runtime.
- Add an abstraction only when it removes repeated, demonstrated complexity.
- Fix a poor design at its source. Do not preserve it with wrappers or compatibility layers.
- Delete dead code, stale comments, obsolete tests, and superseded assumptions in the same change.
- Test behavior that matters, including meaningful edge cases and failures. Do not test implementation details for coverage alone.
- Write comments only for constraints, rationale, or non-obvious behavior that the code cannot express.
- Preserve user data and repository history unless the task explicitly authorizes a destructive operation.

## Repository references

- For GitHub issue work, read `docs/agents/issue-tracker.md`.
- Before assigning issue labels, read `docs/agents/triage-labels.md`.
- Before naming or changing a modeled concept, read `docs/agents/domain.md`.
- For setup and verification commands, read `docs/maintaining.md`.
- Before changing `.rcms` persistence, read `docs/project-format.md`.
- For builds, release candidates, promotion, or withdrawal, read `docs/release.md`.
