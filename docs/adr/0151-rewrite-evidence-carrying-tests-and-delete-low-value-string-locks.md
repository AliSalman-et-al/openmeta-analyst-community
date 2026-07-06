# Rewrite Evidence-Carrying Tests and Delete Low-Value String Locks

During the RC MetaStudio migration, tests should be rewritten when they carry real evidence about project behavior, analysis behavior, GUI compatibility, packaging contracts, or R Stack integration. Tests that only preserve old implementation strings, obsolete filenames, or modernization-era labels should be deleted or replaced with stronger structured contract tests.

This keeps verification focused on maintained behavior rather than preserving abandoned product text.

