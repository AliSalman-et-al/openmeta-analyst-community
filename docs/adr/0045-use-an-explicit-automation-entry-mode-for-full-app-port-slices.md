# Use an Explicit Automation Entry Mode for Full App Port Slices

Early Full Legacy App Port slices may bypass modal startup behavior such as the welcome wizard and R-library splash loading only through an explicit automation entry mode. The user-facing startup workflow remains a preservation target, but CI needs a deterministic way to instantiate the real `MetaForm` shell while launcher, wizard, and R Stack compatibility are being ported.
