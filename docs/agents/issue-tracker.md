# GitHub issue workflow

GitHub Issues owns product requirements and work status. Run `gh` from the repository root so it selects the correct remote.

## Common commands

- Create: `gh issue create --title "..." --body "..."`
- Read with comments: `gh issue view <number> --comments`
- List: `gh issue list --state open --json number,title,body,labels,comments`
- Comment: `gh issue comment <number> --body "..."`
- Add a label: `gh issue edit <number> --add-label "..."`
- Remove a label: `gh issue edit <number> --remove-label "..."`
- Close: `gh issue close <number> --comment "..."`

Use `--body-file <path>` for multiline text. Filter issue lists by `--label` or `--state` when the task names either one.

Create an issue only when the task asks you to publish one. To fetch a ticket, include its comments.
