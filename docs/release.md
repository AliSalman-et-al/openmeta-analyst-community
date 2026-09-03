# Releasing RC MetaStudio

The release pipeline builds Windows x64 and Apple silicon macOS artifacts once, qualifies those exact bytes, and promotes them without rebuilding. Intel macOS is unsupported for future releases; historical assets remain unchanged.

## Prepare the source

1. Bump the version with `uv run python scripts/bump_version.py X.Y.Z`.
2. Complete the matching `CHANGELOG.md` section.
3. Run the fast, full R, Qt, and packaging checks affected by the release.
4. Merge the release commit to protected `master` and record its full commit SHA.
5. Confirm the `Qt6 Integration Verification` workflow succeeds for that SHA.

## Build a candidate

Run the `Build Immutable Candidate` workflow with:

- `version`: the repository version
- `source_sha`: the full commit SHA on `master`
- `trust_profile`: `macos-trusted` for the normal signed macOS release path, or `unsigned-community` for an explicitly unsigned candidate

The workflow builds both supported native targets and uploads a release-set manifest with the artifacts. Record the successful workflow run ID.

## Publish a release candidate

For the normal release path, run `Publish macOS-Trusted Release Candidate` with the candidate run ID, an RC version such as `0.2.4-rc.1`, and the same source SHA. This workflow signs and notarizes both macOS applications, creates DMGs, verifies the mounted applications, checks Gatekeeper acceptance, and publishes an immutable prerelease.

Use `Publish Unsigned Community Release Candidate` only when both artifacts are intentionally unsigned.

Inspect the prerelease assets and checksums. Do not replace assets on an existing RC tag; build a new candidate and RC instead.

## Promote without rebuilding

Run `Promote Release Candidate` with the trusted RC tag and stable version. The workflow downloads the RC assets, verifies their digests, provenance, release-set state, and trust profile, then creates the stable release from the same bytes.

After promotion, confirm that the stable release contains:

- `RCMetaStudio-windows-x64.zip`
- `RCMetaStudio-macos-arm64.dmg`
- `SHA256SUMS`
- one SBOM for each platform
- `release-set-stable.json`

If a published release must be withdrawn, use the `Withdraw Release` workflow. It marks the release as a prerelease and records the superseding tag; it does not rewrite tags or delete historical artifacts.
