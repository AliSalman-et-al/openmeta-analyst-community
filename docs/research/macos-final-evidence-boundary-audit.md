# macOS final evidence boundary audit

**Audit point:** `928fa0083420cfed675b770f6382fbc5c641d7d4`; Actions run [29748971591](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29748971591), ARM64 job [88374291201](https://github.com/AliSalman-et-al/rc-metastudio/actions/runs/29748971591/job/88374291201).  
**Question:** does `write_qualification_evidence()` add independent assurance, and which predicate rejected the retained ARM64 evidence?  
**Sources:** repository source/history, job log, and retained `RCMetaStudio-macos-arm64-evidence` artifact only.

## Finding

The final aggregator mixes two different jobs:

1. useful **boundary authentication** (archive digest, embedded-file digests, target/source identity, and extracted-runtime identity); and
2. redundant **semantic revalidation** of evidence already finalized by the same program in the same job.

The first is valuable. The second is not independent assurance: it uses the same validator, constants, checkout, process, and trust boundary as the producer. It has repeatedly converted already-successful application qualification into CI failures caused by evidence lifecycle/schema mechanics.

Run 29748971591 is decisive. Before the final assertion, ARM64 successfully:

- signed and strictly verified 230 Mach-O files and 9 nested bundles;
- ran the frozen runtime probe;
- ran the real packaged workflow;
- ran Cocoa surface checks at 1.25, 1.50, and 1.75;
- opened through LaunchServices;
- passed coherent deployment inspection and provenance generation;
- created and inspected the ZIP; and
- extracted that exact ZIP and repeated runtime, workflow, surface, LaunchServices, and deployment inspection.

Only `write_qualification_evidence()` then failed with `macOS packaged qualification evidence is incomplete`. This is an evidence-aggregation failure, not evidence of a broken app.

## Producer/finalizer call graph

```text
packaged app automation
  -> writes packaged-smoke.json + workflow log
  -> finalize-smoke (semantic validation + execution fields; persists)
  -> deployment inspect (validates app/runtime/signing graph)
  -> copy app + qualification evidence into staging
  -> create ZIP
  -> archive inspect (validates ZIP and records archive/embedded SHA-256)

extract exact ZIP
  -> packaged app automation writes extracted-packaged-smoke.json
  -> finalize-smoke (semantic validation + execution fields; persists)
  -> deployment inspect on extracted app

write_qualification_evidence
  -> finalize extracted smoke AGAIN (same validator; persists again in the run)
  -> validate extracted deployment/runtime identity
  -> validate R profile AGAIN
  -> finalize pre-archive smoke AGAIN (same validator; read-only since 928fa008)
  -> validate direct-R manifest AGAIN
  -> compare archive + embedded hashes
  -> write summary JSON
```

The relevant calls are in [`build-macos-package.sh`](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/scripts/build-macos-package.sh) and [`inspect_macos_deployment.py`](https://github.com/AliSalman-et-al/rc-metastudio/blob/928fa0083420cfed675b770f6382fbc5c641d7d4/scripts/inspect_macos_deployment.py). Commit [`928fa008`](https://github.com/AliSalman-et-al/rc-metastudio/commit/928fa0083420cfed675b770f6382fbc5c641d7d4) made only the pre-archive repeat read-only; the extracted repeat still persisted in run 29748971591. The subsequent working-tree correction now passes `persist=False` for both calls, but that change was not part of the audited run.

## Exact proven failure

The committed code executed by the run required whole-dictionary equality:

```python
archive_report.get("embedded_sha256") == expected_embedded
```

`expected_embedded` contains 11 records. The retained `archive-inspection.json` contains 13 valid records: those same 11 plus `qualification/runtime-probe.stdout.log` and `qualification/runtime-probe.stderr.log`. All 13 recorded digests match their retained files. Consequently the dictionaries are unequal solely because the archive inspector correctly retained two additional runtime logs. This predicate is definitively false and is the proven cause of the generic final failure.

The remaining effective checks reconstruct as follows:

| Predicate | Retained result |
|---|---:|
| deployment target is `macos-arm64` | true |
| stack exactly equals locked versions | true |
| architecture is `arm64` | true |
| Qt collector is PyInstaller | true |
| signing-inventory path is canonical | true |
| signing-inventory SHA-256 matches the retained file | true |
| finalized smoke says clean exit | true |
| finalized smoke says LaunchServices completed | true |
| archive report target is `macos-arm64` | true |
| all 11 expected embedded-file SHA-256 values match the archive report | true |
| archive report has exactly the 11 expected keys | **false: it has 13 valid keys** |
| archive-report SHA-256 equals the final ZIP SHA-256 | unobservable because the failed job did not upload the ZIP |

The archive ZIP hash remains unobservable and could also have failed, but it is not needed to explain the run: whole-dictionary equality is already proven false. The correct invariant is subset authentication—every required path must have the expected digest—while allowing the archive inspector to retain additional authenticated diagnostics. The current working-tree `_contains_expected_hashes()` change implements that invariant; it was added after the run and must not be used retroactively when auditing the failure.

## What assurance is independent?

Within this same job, none of the semantic validation is independent in the assurance sense. Re-running `finalize_smoke_evidence()` can catch accidental mutation between calls, but hash comparison catches that more directly and without reinterpreting the schema. It cannot detect a forged `passed: true` if the producer and validator are compromised together; both are code from the same checkout.

The genuinely different observations are:

- execution of the packaged application before and after ZIP extraction;
- inspection of the extracted native dependency graph;
- SHA-256 authentication of the ZIP and embedded evidence bytes;
- identity linkage across source commit, target, architecture, runtime probe, and archive.

Those are the boundaries worth preserving. Re-validating BCG result fields, scale records, teardown log order, R profile schema, and direct-build schema in the summary writer merely repeats decisions already made before the ZIP boundary.

## Are we overengineering?

Yes, specifically at the summary boundary. The application qualification itself is appropriately thorough for a Qt/R desktop artifact. The overengineering is treating a report composer as another authoritative validator and finalizer. A summary should not mutate inputs, rerun producers, or own domain semantics.

The compound boolean also destroys diagnostic value. A harmless superset of authenticated evidence collapses into “evidence is incomplete,” causing another full native rebuild instead of reporting `embedded_sha256 keys: expected required subset, found two additional runtime logs`.

## Smallest durable design

1. **Seal each evidence document once.** `finalize-smoke` remains the sole semantic authority for a smoke run. It validates, writes `execution`, and persists exactly once. No later stage calls it.
2. **Make the aggregator a pure composer.** Read the sealed pre-archive and extracted smoke JSON; require their schema version, `passed`, `execution.clean_exit`, and LaunchServices flag, but do not re-run semantic finalizers or mutate files.
3. **Keep only cross-boundary checks in the aggregator:**
   - final ZIP SHA-256;
   - archive inspector's embedded SHA-256 map against the sealed source files;
   - extracted target/architecture/source commit;
   - extracted runtime-probe canonical digest;
   - hashes of extracted evidence/logs in the output summary.
4. **Report named invariant failures.** Replace the compound boolean with individual `require(name, condition, expected, actual)` checks. At minimum, print both archive digests on mismatch.
5. **For real independence, move verification to the consumer job.** The candidate qualification job should download the immutable ZIP by run/artifact identity and run a small read-only verifier from protected source. Repeating the same validator before upload is not an independent trust boundary.

The smallest immediate recovery is therefore not another schema patch. Remove both calls to `finalize_smoke_evidence()` from `write_qualification_evidence()`, consume the already-sealed JSON, retain the hash/identity comparisons, and split those comparisons into named errors. This reduces code and preserves all assurance that crosses an actual artifact boundary.
