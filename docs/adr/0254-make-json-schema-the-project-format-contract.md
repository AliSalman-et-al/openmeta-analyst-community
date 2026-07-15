# Make JSON Schema the project format contract

Committed JSON Schema documents are the authoritative contract for every supported Versioned Project Format version. The writer emits only the latest version; the reader selects and validates the exact schema named by `manifest.json`, rejects unsupported versions and unexpected properties, and applies only explicit, pure JSON-to-JSON migrations between supported structured versions. Runtime project loading will not use Python object deserialization, Qt types, SIP types, or implicit best-effort coercion to bridge format versions.
