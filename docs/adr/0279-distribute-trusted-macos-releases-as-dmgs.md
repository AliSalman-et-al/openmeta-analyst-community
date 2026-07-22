# Distribute trusted macOS releases as DMGs

The macOS-Trusted Release Profile will publish separate Intel x64 and Apple Silicon ARM64 read-only UDZO disk images instead of ZIP archives containing the application. The unsigned native candidate ZIP remains an internal build-once transport. The protected trust stage signs the complete application, places it with an Applications shortcut in the disk image, Developer ID-signs the DMG, submits those exact bytes to Apple, staples the accepted ticket to the preserved DMG, then mounts, copies, and smoke-tests the application before checksum, SBOM attestation, RC publication, and no-rebuild stable promotion.

The application and disk image are independently signed. Qualification evidence remains outside the user-facing disk image and is bound to the final DMG through the release-set records. Windows remains an explicitly unsigned ZIP, and changing the container does not combine the two native macOS architectures into a universal application.
