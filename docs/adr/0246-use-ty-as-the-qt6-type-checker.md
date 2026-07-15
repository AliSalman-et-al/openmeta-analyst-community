# Use ty as the Qt6 type checker

RC MetaStudio will use Astral's `ty` as the authoritative static type checker for the Native Qt6 Port. Configuration will live in `pyproject.toml`, target the repository's Python 3.11 contract, treat the selected strict rule set as errors, check every handwritten Qt-bearing module, and exclude build-generated form modules. Suppressions must use a rule-specific `# ty: ignore[rule]` form with an explanatory reference and may cover only demonstrated PyQt6 stub defects; blanket file or unresolved-import allowances will not substitute for typing application code.
