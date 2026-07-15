# Versioned Project Format

`.rcms` files are ZIP containers read and written through
`rc_metastudio.project_format`. Version 1 contains exactly three UTF-8 JSON
members:

- `manifest.json` identifies the format version and records the SHA-256 digest
  and uncompressed byte size of each data member.
- `project.json` contains normalized analysis data.
- `state.json` contains only the active outcome, follow-up, groups and effect,
  plus the project Confidence Level. Version 1 has no arbitrary analysis,
  display, or artifact-property bags. Machine-local Qt settings and transient
  widget state do not belong here.

The committed Draft 2020-12 schemas under
`src/rc_metastudio/project_schemas/v1/` are authoritative. The reader checks
archive names and types, duplicate entries, encryption, member counts, archive
and uncompressed sizes, compression ratios, supported compression methods, a
maximum JSON nesting depth of 32, strict UTF-8 JSON, CRC/integrity, and the
manifest-selected schemas before returning data. Stored and deflated members
are supported. ZIP data descriptors are also supported because Python's ZIP
reader resolves their bounded sizes and CRCs before member decoding; encryption
and all other compression methods are rejected fail-closed. It then validates
domain relationships: identifiers are unique, units and
state refer to declared outcomes/follow-ups/groups, data types and metrics match
the analysis family, raw-data arity matches the family, covariate values match
their declarations, and all numeric domain values are finite and valid. Binary
event/total counts, diagnostic TP/FN/FP/TN counts, and continuous sample sizes
must be integer-valued. JSON integers and integral legacy floats such as `6.0`
are accepted; fractional counts and sample sizes are not. Group
names and effect-comparison keys are user/domain identifiers, so JSON Schema
constrains their representation while semantic validation resolves them against
the groups declared by each analysis unit. The reader consumes members directly
and never extracts the archive.

JSON numeric decoding is strict and shared by project data, state, manifests,
and schemas. Integer literals are bounded to 1,024 decimal digits, and every
decoded or writer-supplied numeric scalar must be representable as a finite
Python float. Overflowing exponents, non-finite floats, and integers outside
that portable range are rejected as `ProjectFormatError`; raw Python
`ValueError` and `OverflowError` exceptions do not cross the persistence
boundary. A study-level `sample_size`, when present, must also be a finite,
positive integer.

The writer emits only the latest version. It serializes canonical JSON, writes
and flushes a temporary container beside the destination, reopens it through
the public reader, and atomically replaces the destination only after full
validation. Every failure before replacement removes the temporary file and
preserves an existing project; a cleanup failure is attached to the primary
error instead of masking it. After replacement, supported POSIX filesystems
also flush the parent directory. Windows has no portable directory-fsync API,
so the policy there is file flush plus atomic `os.replace`. A POSIX directory
flush failure is reported explicitly as a durability failure after replacement:
the new file is already installed and the old file cannot be restored safely.
Directory-handle close failures use the same post-replacement durability
boundary. If both directory flush and close fail, the flush error remains the
primary failure and the close error is attached as an additional note.

`project_domain.AnalysisDataset` is the Qt-independent reconstruction contract
for later Analysis Adapter integration. Every committed sample reconstructs to
its exact frozen semantic snapshot. `sample-analysis-evidence.json` then binds
that semantic hash and the tagged legacy Git blob to a successful authoritative
capture with observed numeric output, text output, and a hash-verified PNG. BCG
and meantime have supplemental captures produced from the same tagged Python,
PyQt5, Qt, SIP, R, rpy2, and RCMetaR baseline because the original comprehensive
Golden bundle did not include those two samples. Forward validation reads only
JSON, ZIP members, Git blobs, and the new project format; it imports neither
PyQt5 nor pickle.

When a structured format version is added, retain its schemas and add one pure
JSON-to-JSON migration step to the dispatch in `project_format.py`. Migration
steps must not import Qt, SIP, pickle, or application models. Pickle-era files
were never publicly released and are not supported by this boundary.
