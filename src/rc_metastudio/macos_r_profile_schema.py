"""Canonical schema for macOS embedded-R product-profile evidence."""

from __future__ import annotations


PROFILE_POLICY = "official-cran-r-with-optional-x11-tcl-surfaces-removed"
DEPENDENCY_FIELDS = ("Depends", "Imports", "LinkingTo")
PROFILE_EXCLUSION_PATHS = (
    "library/tcltk",
    "modules/R_X11.so",
    "modules/R_de.so",
    "library/grDevices/libs/cairo.so",
)


class ProfileSchemaError(RuntimeError):
    pass


def validate_profile_evidence(
    payload: dict, *, expected_r_version: str, expected_architecture: str
) -> None:
    expected_paths = sorted(PROFILE_EXCLUSION_PATHS)
    source = payload.get("source_framework", {})
    canonical = source.get("canonical_macho", {})
    executable = source.get("executable_macho", {})
    launcher = source.get("launcher", {})
    hashes = (
        payload.get("dependency_manifest", {}).get("sha256"),
        source.get("source_tree_identity_sha256"),
        source.get("pre_profile_tree_identity_sha256"),
        launcher.get("sha256"),
    )
    valid_hashes = all(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        for value in hashes
    )
    observed_paths = sorted(
        entry.get("relative_path")
        for entry in payload.get("excluded_surfaces", [])
        if isinstance(entry, dict) and isinstance(entry.get("relative_path"), str)
    )
    if not (
        payload.get("schema_version") == 1
        and payload.get("phase") == "finalize"
        and payload.get("policy") == PROFILE_POLICY
        and payload.get("hard_dependency_fields") == list(DEPENDENCY_FIELDS)
        and "tcltk"
        not in {
            str(name).casefold() for name in payload.get("hard_dependency_closure", [])
        }
        and payload.get("post_profile_exclusions") == expected_paths
        and observed_paths == expected_paths
        and source.get("version") == expected_r_version
        and source.get("expected_architecture") == expected_architecture
        and canonical.get("relative_path") == "lib/libR.dylib"
        and canonical.get("architectures") == [expected_architecture]
        and executable.get("relative_path") == "bin/exec/R"
        and executable.get("architectures") == [expected_architecture]
        and launcher.get("relative_path") == "bin/R"
        and launcher.get("kind") == "script"
        and valid_hashes
    ):
        raise ProfileSchemaError("embedded R profile evidence is incomplete")
