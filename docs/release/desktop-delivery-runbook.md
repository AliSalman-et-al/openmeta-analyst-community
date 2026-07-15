# Desktop delivery runbook

## Current unsigned community releases

No paid certificate is required. Select `unsigned-community` in **Build
Immutable Candidate**, then dispatch **Publish Unsigned Community Release
Candidate**. The release manifest and GitHub release title explicitly disclose
that Windows Authenticode, Apple Developer ID, and notarization are absent.
SmartScreen and Gatekeeper warnings are therefore expected and must not be
documented as security failures or bypassed invisibly.

The `release-candidate` and `production-release` environments should still use
reviewers because publishing and promotion mutate repository release state.

## Future signed-release configuration

Create three protected GitHub environments:

| Environment | Required protection | Configuration |
| --- | --- | --- |
| `windows-signing` | production reviewer; protected `master` and `v*` tags; prevent self-review | Variables `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `ARTIFACT_SIGNING_ENDPOINT`, `ARTIFACT_SIGNING_ACCOUNT`, `ARTIFACT_SIGNING_PROFILE`; Azure federated credential restricted to this environment |
| `macos-signing` | production reviewer; protected `master` and `v*` tags; prevent self-review | Secrets `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_KEYCHAIN_PASSWORD`, `APPLE_NOTARY_KEY_BASE64`; variables `APPLE_SIGNING_IDENTITY`, `APPLE_NOTARY_KEY_ID`, `APPLE_NOTARY_ISSUER` |
| `release-candidate` | release reviewer; protected `master` | no long-lived secret |
| `production-release` | distinct production reviewer; protected `master`; prevent self-review | no long-lived secret |

Azure Artifact Signing must trust GitHub OIDC for the repository and
`windows-signing` environment. Apple credentials must be Developer ID
Application and App Store Connect notary credentials. Never configure signing
secrets at repository scope.

Add rulesets that prevent deletion or movement of `v*` tags, require pull
requests for `master`, and restrict tag/release creation to maintainers and the
release workflows. Keep third-party Actions restricted to the SHA-pinned set in
the workflows.

## Candidate

1. Merge all release changes and version metadata to protected `master`.
2. Record the full 40-character `master` SHA.
3. Dispatch **Build Immutable Candidate** with an RC version such as
   `0.1.2-rc.1` and that SHA.
4. Confirm both unsigned target artifacts and their assembled stage records are
   present. A failed target invalidates the candidate run.
5. For the current profile, dispatch **Publish Unsigned Community Release
   Candidate**. When certificates become available and the candidate was built
   with `trusted-signed`, dispatch **Sign and Publish Release Candidate**.
6. Confirm final-byte packaged smoke, packaged-tree SBOM generation, provenance
   attestation, and release-set verification. For `trusted-signed`, also confirm
   Authenticode verification and Developer ID/notarization/stapling.
7. Review the immutable prerelease, `SHA256SUMS`, both SBOMs, and
   `release-set-rc.json`. Never rerun into the same RC tag; increment `rc.N`.

For layout-system, Qt, supported-OS, font, or icon changes, run the controlled
adaptive-layout commands in `docs/verification/adaptive-layout-native-evidence.md`
against the final RC ZIPs. Record the package digest and human verdict. If a
controlled platform is unavailable, record that evidence as not run; do not
substitute hosted-runner screenshots.

## Stable promotion

1. Complete human native-layout review and release acceptance against the RC.
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

Twice yearly, rehearse a rejected notarization, invalid Windows signature,
missing target, checksum mismatch, and post-release withdrawal.

## Local policy checks

```powershell
uv run pytest tests/packaging/contract -q
uv run python scripts/validate_test_taxonomy.py --strict
actionlint .github/workflows/*.yml
```

Signing and notarization cannot be simulated as passing. Local tests validate
the state machine and workflow policy; production trust checks run only in the
protected native environments.
