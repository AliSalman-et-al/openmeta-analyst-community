# Context Map

## Contexts

- [Analysis Compatibility](./docs/contexts/analysis-compatibility/CONTEXT.md) - defines the preservation target for statistical analysis behavior during modernization.
- [Project Provenance](./docs/contexts/project-provenance/CONTEXT.md) - defines authorship, branding, affiliation, and licensing language for the maintained project.

## Relationships

- **Analysis Compatibility -> Modernization Decisions**: Migration decisions must preserve the analysis behavior defined by this context unless an explicit compatibility exception is documented.
- **Project Provenance -> Modernization Decisions**: Rename, copyright, attribution, and affiliation changes must preserve accurate provenance for derived work while making the maintained RC MetaStudio identity explicit.
