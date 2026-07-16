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
used to validate the application adapter. Every committed sample reconstructs to
its exact frozen semantic snapshot. `sample-analysis-evidence.json` then binds
that semantic hash and the tagged legacy Git blob to a successful authoritative
capture with observed numeric output, text output, and a hash-verified PNG. BCG
and meantime have supplemental captures produced from the same tagged Python,
PyQt5, Qt, SIP, R, rpy2, and RCMetaR baseline because the original comprehensive
Golden bundle did not include those two samples. Forward validation reads only
JSON, ZIP members, Git blobs, and the new project format; it imports neither
PyQt5 nor pickle.

The native application lifecycle crosses this boundary through
`project_adapter`: wizard-created and CSV-imported datasets are translated to
portable project JSON, and loaded documents are rebuilt as application dataset
objects only after container, schema, integrity, and semantic validation. Save
and Save As use the atomic writer directly. Recent-project entries are updated
only after a successful open or save. Project files contain durable analysis
data, complete entered-effect metadata, active analysis selections, and the
Confidence Level; partial display caches, window geometry, focus, table
selection, dialog state, and other machine-local or transient UI state are not
serialized. The application workflow neither reads nor writes pickle sidecars.
Opening is transactional across dataset reconstruction, table-model creation,
signal rebinding, and UI initialization: a failure restores the prior model,
connections, selection, path, labels, dirty state, and action availability.
Rollback operations are individually guarded so a secondary UI cleanup failure
is logged and attached to, but never replaces, the original open error. The
actual metric-menu actions and checked/enabled states are restored alongside
their family marker, including late failures while crossing analysis families.
Persisted active selections are installed intentionally and are not replaced by
first-outcome or first-follow-up initialization defaults.

Save has a two-part boundary. Adapter, validation, and atomic-writer failures
occur before the document commit and leave the current path and dirty state
unchanged. Once the atomic writer returns, the document path and clean state are
committed and Save returns success. Failure to persist the machine-local recent
list or rebuild its menu is logged and reported as a nonfatal bookkeeping
warning; it cannot retroactively turn a durable save into a failed save.
`ProjectDurabilityError` is the explicit post-replacement exception: the new
file is already installed, so the application commits its path and clean state,
returns success for destructive-action authorization, and warns that final
directory durability could not be confirmed instead of claiming the save
failed or risking a later discard/retry of the installed work.
Likewise, New, Open, Recent Project, and CSV Import continue after a Yes-to-save
prompt only when Save returns explicit success. A cancelled Save As aborts the
destructive action.

When a structured format version is added, retain its schemas and add one pure
JSON-to-JSON migration step to the dispatch in `project_format.py`. Migration
steps must not import Qt, SIP, pickle, or application models. Pickle-era files
were never publicly released and are not supported by this boundary.
