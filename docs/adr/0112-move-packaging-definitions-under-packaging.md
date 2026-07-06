# Move Packaging Definitions Under Packaging

RC MetaStudio should move PyInstaller specs, platform bundle metadata, packaging icons, installer/archive configuration, and platform-specific packaging helpers under a top-level `packaging` directory. Reusable developer automation should remain under `scripts`, while application source stays under `src/rc_metastudio`.

This removes loose packaging files from the importable source tree and makes release artifact configuration easier to audit.

