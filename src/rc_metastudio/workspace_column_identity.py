# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable semantic identities and serialization for workspace columns."""

import json
import uuid
from dataclasses import dataclass

WORKSPACE_COLUMN_IDENTITY_ROLE = 0x0100 + 73
WORKSPACE_COLUMN_WIDTH_STATE_VERSION = 1


def stable_covariate_identity(dataset, covariate):
    """Return a neutral durable ID, migrating legacy domain objects here."""
    existing = getattr(covariate, "stable_id", None)
    if existing:
        return existing

    ordinal = dataset.covariates.index(covariate)
    legacy_schema = {
        "title": dataset.title or "",
        "is_diagnostic": bool(dataset.is_diagnostic),
        "outcomes": [
            {
                "name": name,
                "type": dataset.get_outcome_type(name),
                "subtype": dataset.get_outcome_subtype(name),
            }
            for name in dataset.get_outcome_names()
        ],
        "covariates": [
            {"name": item.name, "type": int(item.data_type)}
            for item in dataset.covariates
        ],
    }
    seed = "rc-metastudio/legacy-covariate/v1/%s/%d" % (
        json.dumps(legacy_schema, sort_keys=True, separators=(",", ":")),
        ordinal,
    )
    covariate.stable_id = uuid.uuid5(uuid.NAMESPACE_URL, seed).hex
    return covariate.stable_id


@dataclass(frozen=True, order=True)
class WorkspaceColumnIdentity:
    kind: str
    components: tuple

    def __post_init__(self):
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "components", tuple(str(x) for x in self.components))

    @classmethod
    def coerce(cls, value, fallback_section=None, model=None):
        if isinstance(value, cls):
            return value
        if isinstance(value, (tuple, list)) and value:
            return cls(value[0], tuple(value[1:]))
        model_name = "unknown"
        if model is not None:
            model_type = type(model)
            model_name = "%s.%s" % (model_type.__module__, model_type.__qualname__)
        return cls("model-column", (model_name, fallback_section))

    def to_record(self):
        return {"kind": self.kind, "components": list(self.components)}

    @classmethod
    def from_record(cls, record):
        return cls(record["kind"], tuple(record.get("components", ())))


class WorkspaceColumnWidthState:
    """A versioned mapping that never encodes identity in display text."""

    def __init__(self, widths=None):
        self._widths = {}
        for identity, width in (widths or {}).items():
            self[identity] = width

    def __eq__(self, other):
        return (
            isinstance(other, WorkspaceColumnWidthState)
            and self._widths == other._widths
        )

    def __getitem__(self, identity):
        return self._widths[WorkspaceColumnIdentity.coerce(identity)]

    def __setitem__(self, identity, width):
        try:
            width = int(width)
        except (TypeError, ValueError):
            return
        if width > 0:
            self._widths[WorkspaceColumnIdentity.coerce(identity)] = width

    def get(self, identity, default=None):
        return self._widths.get(WorkspaceColumnIdentity.coerce(identity), default)

    def copy(self):
        return WorkspaceColumnWidthState(self._widths)

    def to_json(self):
        columns = [
            {"identity": identity.to_record(), "width": width}
            for identity, width in sorted(self._widths.items())
        ]
        return json.dumps(
            {"version": WORKSPACE_COLUMN_WIDTH_STATE_VERSION, "columns": columns},
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw):
        if not raw:
            return cls()
        try:
            payload = json.loads(str(raw))
            if payload.get("version") != WORKSPACE_COLUMN_WIDTH_STATE_VERSION:
                return cls()
            return cls(
                {
                    WorkspaceColumnIdentity.from_record(item["identity"]): item["width"]
                    for item in payload.get("columns", [])
                }
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return cls()
