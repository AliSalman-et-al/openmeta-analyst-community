# Pin the ty verification version

RC MetaStudio will pin the exact `ty` version used by the Native Qt6 Port in `uv.lock` and use that same version in development and CI. Upgrading `ty` or changing its diagnostic contract will be a separate reviewed change with an explicit baseline comparison, so a dependency refresh cannot silently alter the Qt6 release gate.
