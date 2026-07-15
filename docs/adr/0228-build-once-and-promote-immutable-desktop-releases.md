# ADR 0228: Build once and promote immutable desktop releases

## Status

Accepted.

## Context

The former release path rebuilt Windows and macOS artifacts when a version tag
was pushed and could overwrite existing release assets. The platform workflows
also mixed invariant policy with native mechanics, and unsigned ZIPs had no
release-set manifest, packaged-tree SBOM, provenance attestation, or rollback
contract.

## Decision

RC MetaStudio uses the versioned target registry in `delivery/targets.json` and
the state machine exposed by `scripts/delivery.py`. A protected-main commit is
built once into unsigned candidates. Protected platform adapters sign the
candidate bytes, macOS notarizes and staples its app, and both final artifacts
are inventoried, launched, attested, and bound into one release-set manifest.

An RC is immutable. Stable release is promotion of the RC deliverables with
identical checksums; it never runs a builder, dependency resolver, signer,
notary operation, or archiver. Published assets are never clobbered. A bad
release is withdrawn and superseded without moving its tag or deleting its
evidence.

Until platform certificates are affordable, `unsigned-community` is a
first-class trust profile. It omits signing/notarization stages, adds an
explicit unsigned-qualification stage, and requires conspicuous unsigned labels
in the manifest and release. It must never be represented as platform-trusted.
The future `trusted-signed` profile uses the protected signing adapters without
changing the build-once or promotion interfaces.

The shared interface owns target coverage, stage order, digests, inventories,
SBOMs, checksums, and promotion. PowerShell and Bash are adapters only for
assembly, Authenticode, Developer ID signing, notarization, native launch, and
archive mechanics.

## Consequences

- `candidate.yml` has no write or signing authority.
- `community-release-candidate.yml` publishes explicitly unsigned builds
  without signing secrets; `release-candidate.yml` is the future protected
  signed path.
- `promote.yml` requires production approval and verifies RC checksums and
  GitHub attestations before creating a stable release.
- `package-verification.yml` is manual qualification only and cannot publish.
- Python 3.11.9 and R 4.6.1 are explicit delivery inputs.
- Signing identities, Azure federation, Apple credentials, environment
  reviewers, and tag rules must be configured outside the repository before a
  production release can succeed.

## Rejected alternatives

- A platform matrix alone: it deduplicates YAML but does not prevent semantic
  drift or bind artifacts to stages.
- Tag-triggered rebuilds: mutable external inputs can change nominally identical
  releases.
- Signing before establishing manifests: it adds secrets to a pipeline without
  first making inputs and outputs auditable.
- Replacing an RC or stable asset in place: it destroys the meaning of a digest,
  tag, and prior approval.
