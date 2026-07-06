# Sequence RC MetaStudio Phase Issues with Limited Parallelism

RC MetaStudio migration phase issues should be mostly sequential. Legal/provenance and README work should land first, followed by the core identity rename work for Python, R, project files, and environment variables. Layout, CI, packaging, docs, and cleanup work should build on those foundations.

After the identity foundations are stable, docs restructuring, bundled-help removal, and generated-artifact cleanup may proceed in parallel when they do not conflict with active path renames. Packaging should wait until package entry points and repository layout are stable.

