# Isolate legacy pickle conversion

Status: superseded by ADR-0257

Legacy pickle `.rcms` conversion will run only in a separate, non-Qt migration utility and never inside the RC MetaStudio application process. The utility will disable network access where the platform permits, apply resource limits, allow only audited neutral reconstruction targets, fail closed on unknown pickle globals or malformed data, and emit only Project Format Schema-validated JSON containers. It will preserve the source file, write the converted project to a distinct destination atomically, and produce a conversion report that records input identity, detected legacy variant, transformations, warnings, and output identity.
