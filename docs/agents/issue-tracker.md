# GitHub issue workflow

GitHub Issues is the source of truth for issues and product requirements. Run `gh` from this repository so it resolves the remote automatically.

## Common commands

- Create: `gh issue create --title "..." --body "..."`
- Read with comments: `gh issue view <number> --comments`
- List: `gh issue list --state open --json number,title,body,labels,comments`
- Comment: `gh issue comment <number> --body "..."`
- Add a label: `gh issue edit <number> --add-label "..."`
- Remove a label: `gh issue edit <number> --remove-label "..."`
- Close: `gh issue close <number> --comment "..."`

Use `--body-file <path>` for a multiline issue body. Add `--label` and `--state` filters when listing issues for a specific task.

When an instruction says to publish to the issue tracker, create a GitHub issue. When it says to fetch a ticket, run `gh issue view <number> --comments`.
