# Adopt RCMS Project Files and Retire OMA Compatibility

RC MetaStudio will replace the legacy `.oma` project-file identity with `.rcms` everywhere, including user-facing file dialogs, sample data, tests, docs, packaging, workflow manifests, and internal compatibility language. This supersedes earlier modernization decisions that preserved `.oma` read and round-trip compatibility: the maintained product will not keep reverse compatibility with `.oma` files, and existing sample data should be converted to the `.rcms` format rather than carried forward under legacy filenames.

The trade-off is intentional. Dropping `.oma` compatibility removes a familiar migration path for existing OpenMeta[Analyst] users, but it avoids presenting RC MetaStudio as a compatibility-preserving continuation of the abandoned product and lets the file format, application identity, and support surface move together under the independently maintained RC MetaStudio name.

