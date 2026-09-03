Hi, I'm Linus Torvalds. You're my agent.

We'll be working together a lot, so here are the rules.

I like building complicated things without making the implementation complicated. Complexity is sometimes unavoidable. Accidental complexity isn't.

If something can be simple, make it simple.

## Coding preferences, general

- Keep it simple. Don't solve problems we don't have. YAGNI isn't a suggestion.
- Prefer obvious code over clever code. Clever code is usually just harder-to-debug code with better marketing.
- Use the type system. If the compiler can catch a mistake for us, let it.
- Don't add abstractions just because abstractions sound nice. An abstraction should remove real complexity, not move it somewhere harder to see.
- Don't add factories, interfaces, wrappers, configuration layers, compatibility layers, or indirection unless there's an actual reason for them.
- Don't design for hypothetical future requirements. We can change the code when the future actually happens.
- If the existing design is bad, fix the design. Don't build another layer of crap around it.
- Be willing to delete code. Less code is often better code.
- Bold changes are fine when they make the system substantially simpler or better. Don't preserve bad decisions just because they're already there.
- Be careful with destructive actions. If I didn't ask you to delete data, rewrite history, or destroy something difficult to recover, don't casually do it.
- Tests are useful when they test behavior that matters. Don't produce test slop.
- Don't add endless smoke tests, duplicate tests, tautological tests, or "regression tests" whose only purpose is to preserve something we intentionally removed.
- Test important behavior, edge cases, and bugs worth preventing. Don't test implementation details just to make coverage numbers go up.
- Comments should explain things that aren't obvious from the code: why something exists, important constraints, weird behavior, or how an API is meant to be used.
- Don't comment every line. If the code needs a paragraph explaining what every statement does, the code probably needs fixing.
- Keep comments accurate. A stale comment is worse than no comment, because now we have two versions of reality.
- When changing behavior, clean up the old assumptions, comments, tests, dead code, and unnecessary compatibility machinery that no longer applies.
- Don't leave cruft behind "just in case." Git already remembers the old code.
- Prefer fixing the root cause over adding another special case.
- Before adding more machinery, ask whether the problem can instead be made smaller.

## Agent skills

### Issue tracker

Issues are tracked in this repository's GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

The default five-role triage vocabulary is used. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses a single-context domain-doc layout. See `docs/agents/domain.md`.
