# Require OMA Read Compatibility Before Byte Perfect Writes

Supersession note: ADR 0084 and the RC MetaStudio migration PRD supersede this decision for active development. Maintained project-file behavior now uses `.rcms` only and does not preserve `.oma` read or round-trip compatibility.

The first Python 3 and Qt 5 milestone will require existing `.oma` project files to open without user-visible migration steps. The modern application may normalize legacy project data internally while opening a file, but ordinary legacy project open should not require an explicit migration prompt or separate conversion command. Write compatibility will initially be proven through selected project file round trips in the modern application rather than byte-for-byte identical saved files or backward readability by the Python 2 Reference Implementation, because preserving user access to existing analyses is more urgent than preserving incidental serialization details or allowing the legacy release path to reopen files saved by the modern path.

Representative round-trip tests should be expanded as the save path is ported, especially for project features beyond the first standard binary analysis workflow.
