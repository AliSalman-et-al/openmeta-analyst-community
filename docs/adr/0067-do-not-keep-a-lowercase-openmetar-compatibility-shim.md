# Do Not Keep a Lowercase Openmetar Compatibility Shim

The `OpenMetaR` package rename should not preserve `library(openmetar)` or an installed `R/library/openmetar` package identity in the maintained modern path. The Reference Implementation can retain the historical lowercase package name, but the Modern CI Path should load, package, test, and document `OpenMetaR` only.

Keeping both package identities would create a fake compatibility surface around the R Stack and make package discovery, install paths, and artifact verification ambiguous.
