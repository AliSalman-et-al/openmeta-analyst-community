# Desktop delivery runbook

## Release trust profiles

Every current candidate contains Windows x64, macOS Intel x64, and macOS ARM64
artifacts built once from one protected `master` commit. Select
`macos-trusted` for a stable-release candidate: the protected signing workflow
Developer ID signs, notarizes, staples, verifies, and requalifies both macOS
applications while carrying the explicitly unsigned Windows artifact forward
unchanged.

`unsigned-community` remains available for explicitly unsigned prereleases.
Select it in **Build Immutable Candidate**, then dispatch **Publish Unsigned
Community Release Candidate**. It can never be promoted to stable, and a failed
`macos-trusted` run must never fall back to it automatically.

The `release-candidate` and `production-release` environments should still use
reviewers because publishing and promotion mutate repository release state.

## Protected release configuration

Create these protected GitHub environments:

| Environment | Required protection | Configuration |
| --- | --- | --- |
| `macos-signing` | required release reviewer; protected branches; manual approval | Secrets `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `KEYCHAIN_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` |
| `release-candidate` | release reviewer; protected `master` | no long-lived secret |
| `production-release` | distinct production reviewer; protected `master`; prevent self-review | no long-lived secret |

The P12 must contain exactly one valid Developer ID Application identity for
`APPLE_TEAM_ID`. `APPLE_APP_SPECIFIC_PASSWORD` is the app-specific password for
`APPLE_ID`; `KEYCHAIN_PASSWORD` is an independent random password used only for
the ephemeral runner keychain. Store all six values on the `macos-signing`
environment, never at repository scope. The workflow discovers the identity
from the imported certificate and refuses missing, expired, wrong-team, or
ambiguous identities.

Add rulesets that prevent deletion or movement of `v*` tags, require pull
requests for `master`, and restrict tag/release creation to maintainers and the
release workflows. Keep third-party Actions restricted to the SHA-pinned set in
the workflows.

## Candidate

1. Merge all release changes and version metadata to protected `master`.
2. Record the full 40-character `master` SHA.
3. Dispatch **Build Immutable Candidate** with the RC version, full SHA, and
   `macos-trusted` profile.
4. Confirm all three unsigned artifacts and their assembled stage records are
   present. Any failed target invalidates the candidate run.
5. Dispatch **Publish macOS-Trusted Release Candidate** with the exact candidate
   run ID, RC version, and source SHA, then approve `macos-signing`.
6. Confirm both Developer ID identities match the configured team, Apple accepts
   both notarization submissions, both tickets are stapled, Gatekeeper accepts
   each final app, and final-byte packaged smoke passes on both native runners.
7. Confirm the unchanged Windows artifact also passes packaged smoke, then
   review all three SBOMs, attestations, `SHA256SUMS`, and
   `release-set-rc.json`. Never rerun into the same RC tag; increment `rc.N`.

For layout-system, Qt, supported-OS, font, or icon changes, run the controlled
adaptive-layout commands in `docs/verification/adaptive-layout-native-evidence.md`
against the final RC ZIPs. Record the package digest and human verdict. If a
controlled platform is unavailable, record that evidence as not run; do not
substitute hosted-runner screenshots.

## Stable promotion

1. Complete human native-layout review and release acceptance against the
   `macos-trusted` RC. Unsigned-community RCs are ineligible.
2. Dispatch **Promote Release Candidate** with the RC tag and stable base
   version.
3. Approve `production-release`.
4. Confirm the workflow verifies checksums and GitHub attestations, then creates
   the stable release tag at the same source SHA through the GitHub Release API.
5. Compare the RC and stable `SHA256SUMS`; deliverable digests must be identical.

## Withdrawal and rollback

Dispatch **Withdraw Release** with the bad stable tag, the last-known-good or
replacement tag, and a public reason. The workflow retains all assets and
evidence, marks the bad release as withdrawn, and files a tracking issue. Do not
delete the release or move its tag. Build and promote a new patch release for
changed bytes.

Twice yearly, rehearse a rejected notarization, wrong-team Developer ID
certificate, missing target, checksum mismatch, and post-release withdrawal.

## Local policy checks

```powershell
uv run pytest tests/packaging/contract -q
uv run python scripts/validate_test_taxonomy.py --strict
actionlint .github/workflows/*.yml
```

Signing and notarization cannot be simulated as passing. Local tests validate
the state machine and workflow policy; production trust checks run only in the
protected native environments.
