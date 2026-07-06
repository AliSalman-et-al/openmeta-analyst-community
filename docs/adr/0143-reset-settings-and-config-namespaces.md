# Reset Settings and Config Namespaces

RC MetaStudio should rename settings organization keys, application keys, config filenames, recent-file keys, cache directories, and log filenames to RC MetaStudio or RCMS naming. The maintained application should not read old OpenMetaAnalyst settings by default.

This matches the decision to remove reverse compatibility with OpenMeta[Analyst] product identity and prevents old `.oma` paths, support settings, and abandoned-project namespaces from leaking into RC MetaStudio.

