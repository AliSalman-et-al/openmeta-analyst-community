# Rename Private OpenMetaR R Helpers

RCMetaR should rename private package-scoped helpers from `.openmetar.*` to `.rcmetar.*` along with the exported `rcmetar.*` facade. The old private helper prefix should not remain in maintained active R source except where historical fixtures or provenance notes require it.

This keeps internal R implementation names aligned with the RCMetaR package identity while preserving statistical and third-party names that are not product branding.

