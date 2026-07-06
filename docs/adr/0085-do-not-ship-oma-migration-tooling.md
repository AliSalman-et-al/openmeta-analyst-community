# Do Not Ship OMA Migration Tooling

RC MetaStudio will not include, document, or package a built-in `.oma` importer, converter, or migration workflow. Existing repository sample data may be converted to `.rcms` as a maintenance action, and any temporary conversion script used for that work should remain unshipped development tooling or be removed after use.

This keeps the product boundary clear after the rebrand: RC MetaStudio supports RC MetaStudio Project Files, not legacy OpenMeta[Analyst] `.oma` files.

