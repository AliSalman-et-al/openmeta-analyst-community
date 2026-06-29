# Use Analysis Regression as the First Automated Gate

The first modernization milestone will use automated headless golden analysis tests as the hard compatibility gate, while GUI compatibility slices may initially be verified with manual or lightweight scripted evidence. Full automated GUI testing is deferred because desktop GUI automation would add fragility before the statistical compatibility baseline and first PyQt5 workflows are stable.

GUI automation can be introduced later for workflows that become stable and valuable enough to justify the maintenance cost.
