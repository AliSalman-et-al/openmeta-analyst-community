# Rename the R Facade to RCMetaR

RC MetaStudio will rename the maintained R package facade from `openmetar.*` to `rcmetar.*` everywhere, including exported R functions, internal helpers where they carry product identity, Python bridge calls, tests, scripts, manifests, generated documentation, package metadata, and packaging checks. `OpenMetaR` and `openmetar.*` aliases should not be kept in the maintained runtime surface except where historical fixtures or provenance notes need to describe legacy behavior.

This makes `RCMetaR` the package identity and API identity, rather than only a display-name replacement over an OpenMeta-named internal surface.

