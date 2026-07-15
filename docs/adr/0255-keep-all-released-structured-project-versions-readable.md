# Keep all released structured project versions readable

Every officially released Versioned Project Format version remains readable through explicit, tested Project Format Migrations. The application writes only the latest version and upgrades older structured data in memory before use. A structured version may be retired only through a separately reviewed breaking-format decision, after a standalone converter and representative migration evidence are available; ordinary application or dependency releases must not silently shorten project readability.
