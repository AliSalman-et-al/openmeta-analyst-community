# macOS DMG distribution feasibility

**Status:** Research finding, 23 July 2026  
**Scope:** Replacing RC MetaStudio's release ZIPs containing `RCMetaStudio.app`
with architecture-specific disk images, without changing the application bundle
or weakening the existing Developer ID, notarization, immutable-candidate, and
native-smoke guarantees.

## Finding

Yes. RC MetaStudio can distribute its Intel and Apple Silicon macOS builds as
`.dmg` files. A signed, notarized, and stapled DMG is a first-class Apple direct-
distribution format and is a better trust envelope than the current ZIP: Apple
states that a ZIP archive cannot itself be signed, whereas a disk image can be
signed so that its contents and source can be validated. Apple describes signed
disk images (and signed installer packages) as the preferred choices for
distribution outside the Mac App Store; ZIP remains supported but discouraged.
([Apple, *Packaging Mac software for distribution*](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
[Apple TN2206, *macOS Code Signing In Depth*](https://developer.apple.com/library/archive/technotes/tn2206/_index.html))

This is a packaging-pipeline change, not an application-build change. Keep the
two thin native applications and sign each nested code graph and outer `.app`
exactly as today. After that, create and sign one read-only UDIF DMG per
architecture, submit that DMG to Apple's notary service, staple the accepted
ticket to the DMG, and qualify the exact final DMG bytes.

## Apple's supported trust sequence

For direct distribution, Apple says to sign the code, create a distribution
container, and notarize the container. If containers are nested, sign every
level from the inside out but notarize only the outermost container. For this
project the sequence is therefore:

1. Finish the architecture-specific `RCMetaStudio.app`; Developer ID Application
   sign its nested code and app with hardened runtime and a secure timestamp.
2. Stage the signed app (and only intentional presentation files) using a copy
   operation that preserves bundle symlinks. A conventional DMG may also contain
   an `Applications` symlink.
3. Create a read-only UDIF disk image. Apple requires a third-party-produced
   distribution image to be UDIF, read-only, and ZIP-compressed (`UDZO`).
4. Sign the DMG with the Developer ID Application identity, a secure timestamp,
   and a code-signing identifier unique to this distribution product.
5. Submit the signed DMG with `notarytool`; require `Accepted` and retain the
   service log. The notary service supports UDIF disk images directly.
6. Staple the ticket to the DMG with `stapler`, then verify and test the final
   distribution file. Direct stapling is an advantage over ZIP, which cannot
   carry a ticket itself. Stapling avoids depending on network access during a
   user's Gatekeeper check.

Apple gives the relevant commands and container requirements in
[*Packaging Mac software for distribution*](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).
The notary service's supported deliverables and ticket behavior are documented
in [*Notarizing macOS software before distribution*](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
and [*Customizing the notarization workflow*](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
Apple's certificate and hardened-runtime requirements are covered by
[*Resolving common notarization issues*](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)
and [*Preparing your app for distribution*](https://developer.apple.com/documentation/xcode/preparing-your-app-for-distribution).

## Fit with the current release architecture

The current protected workflow already has the difficult parts:

- separate native `macos-x64` and `macos-arm64` applications;
- an inside-out Developer ID Application signer;
- immutable handoff of signed bytes between submission and finalization;
- `notarytool` submission and waiting;
- stapling, `codesign`, `spctl`, and native packaged smoke; and
- checksum, SBOM, attestation, release-set, RC, and no-rebuild stable promotion.

Today `scripts/sign-notarize-macos-artifact.sh` extracts the candidate ZIP,
signs the app, creates a temporary app-only ZIP for notarization, staples the
app, and then recreates a release ZIP containing the app plus qualification
evidence. The release contracts and workflows hard-code
`RCMetaStudio-macos-{x64,arm64}.zip` in `delivery/targets.json`, candidate and
trusted-release workflows, checksums, attestations, release publication, stable
promotion, and the delivery runbook.

The clean seam is after app signing and signed-app smoke. Build the DMG there,
sign it, and submit the DMG rather than the temporary ZIP. On acceptance, staple
the preserved DMG and run final qualification against that exact file. Do not
reconstruct the DMG during stable promotion.

Qualification evidence should remain a separate release asset or workflow
artifact rather than an extra directory on the user-facing disk image. This
keeps the mounted image simple and prevents diagnostic files outside the app's
signature from becoming part of the product surface. The release-set record can
bind the DMG digest to the separate evidence and SBOM just as it currently binds
the ZIP.

## Verification boundary

The final gate should prove both the container and the installed application:

- verify the disk image structure and signature (`hdiutil verify` and
  `codesign --verify`);
- assess the DMG as an opened distribution container with Gatekeeper;
- validate the stapled DMG ticket;
- mount the DMG read-only, copy the app to a fresh location as a user would,
  and run the existing app signature and packaged-runtime checks there; and
- on a clean Mac, test the actual download, mount, drag-to-Applications, and
  first-launch experience.

Apple explicitly recommends testing the product as delivered, preferably on a
different Mac, and instructing users to copy an app out of a disk image before
launch. Launching in place can invoke Gatekeeper's randomized, read-only
translocation behavior and can expose unsafe assumptions about files adjacent
to the app. ([Apple, *Packaging Mac software for distribution*](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
[Apple TN2206](https://developer.apple.com/library/archive/technotes/tn2206/_index.html))

## Risks and decisions

- **Contract breadth:** this is not an extension rename. Target metadata,
  workflow matrices, glob patterns, schema/contract tests, checksums,
  attestations, release publishing, promotion, and documentation all treat ZIP
  as the macOS deliverable.
- **Byte immutability:** signing or stapling changes the DMG. Hash, attest, and
  promote only after stapling; any later layout or metadata change invalidates
  the signature and release digest.
- **Two levels of signing:** signing the DMG does not replace signing the app.
  The app must remain independently valid after the user copies it out.
- **Image format:** use a read-only `UDZO` UDIF release image. Keep any writable
  staging image internal, and ensure the final image is writable only when
  `stapler` needs to attach the ticket. Apple calls out non-writable images as a
  cause of stapling failure.
- **User experience:** choose and test a stable volume name, app placement,
  `Applications` symlink, icon layout, background (if any), and detach behavior.
  These are release-product details, not merely decoration.
- **Architecture clarity:** retain two explicitly named DMGs unless the project
  deliberately undertakes a universal-binary build. Changing containers does
  not combine Intel and ARM64 applications.
- **Rollback:** because stable promotion requires identical RC bytes, conversion
  should begin at the immutable candidate/trusted-finalization boundary for a
  new RC. Do not convert an already-qualified ZIP during promotion.

## Recommendation

Adopt DMG for the two trusted macOS release assets:
`RCMetaStudio-macos-x64.dmg` and `RCMetaStudio-macos-arm64.dmg`. Keep ZIP as an
internal candidate transport only if it remains useful before signing. Treat
the DMG as the notarized, stapled, smoke-tested, checksummed, attested, and
promoted final artifact. Make the transition in one release-contract change
with contract tests, then qualify a fresh release candidate on both native
architectures and a separate clean-Mac installation test.

There is no Apple-platform blocker. The material risk is repository integration:
the current release state machine assumes ZIP at every boundary, so a partial
conversion could notarize one object while publishing or promoting another.
