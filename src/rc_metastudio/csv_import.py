"""Parse CSV files into the workspace import contract."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import tabular_data


class CsvImportError(ValueError):
    """A CSV file cannot satisfy the workspace import contract."""


class CsvImportPayload(TypedDict):
    """Mutable representation retained by the wizard and undo command."""

    headers: list[str]
    data: list[list[str]]
    expected_headers: list[str]
    covariate_names: list[str]
    covariate_types: list[str]


@dataclass(frozen=True, slots=True)
class CsvImportResult:
    """Normalized, validated rows ready for preview and workspace import."""

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    expected_headers: tuple[str, ...]
    covariate_names: tuple[str, ...]
    covariate_types: tuple[str, ...]

    def to_payload(self) -> CsvImportPayload:
        return {
            "headers": list(self.headers),
            "data": [list(row) for row in self.rows],
            "expected_headers": list(self.expected_headers),
            "covariate_names": list(self.covariate_names),
            "covariate_types": list(self.covariate_types),
        }


def parse_csv(
    path: str | Path,
    *,
    expected_headers: list[str] | tuple[str, ...],
    has_headers: bool,
    from_excel: bool,
    delimiter: str = ",",
    quotechar: str = '"',
    year_column: int = 1,
) -> CsvImportResult:
    """Read, normalize, and validate one CSV file."""

    with Path(path).open(newline="") as stream:
        reader = (
            csv.reader(stream, dialect="excel")
            if from_excel
            else csv.reader(stream, delimiter=delimiter, quotechar=quotechar)
        )
        headers = next(reader, []) if has_headers else []
        rows = list(reader)

    normalized_rows = normalize_import_rows(rows, minimum_width=len(headers))
    if headers:
        width = len(normalized_rows[0]) if normalized_rows else len(headers)
        headers = headers + [""] * (width - len(headers))

    _validate_years(normalized_rows, year_column)
    covariate_names, covariate_types = _infer_covariates(
        normalized_rows,
        headers=headers,
        expected_headers=expected_headers,
        has_headers=has_headers,
    )
    return CsvImportResult(
        headers=tuple(headers),
        rows=tuple(tuple(row) for row in normalized_rows),
        expected_headers=tuple(expected_headers),
        covariate_names=tuple(covariate_names),
        covariate_types=tuple(covariate_types),
    )


def normalize_import_rows(
    rows: list[list[str]] | tuple[tuple[str, ...], ...], *, minimum_width: int = 0
) -> list[list[str]]:
    """Return mutable, rectangular rows for insertion into the Qt model."""

    return tabular_data.normalize_rows(
        [list(row) for row in rows], minimum_width=minimum_width
    )


def _validate_years(rows: list[list[str]], year_column: int) -> None:
    for row_number, row in enumerate(rows, start=1):
        if year_column >= len(row):
            raise CsvImportError(f"The year at row {row_number} is missing.")
        try:
            int(row[year_column])
        except ValueError as exc:
            raise CsvImportError(
                f"The year at row {row_number} is not an integer number."
            ) from exc


def _infer_covariates(
    rows: list[list[str]],
    *,
    headers: list[str],
    expected_headers: list[str] | tuple[str, ...],
    has_headers: bool,
) -> tuple[list[str], list[str]]:
    width = len(rows[0]) if rows else len(headers)
    covariate_count = max(0, width - len(expected_headers))
    if covariate_count == 0:
        return [], []

    names = headers[len(expected_headers) :] if has_headers else []
    names += [""] * (covariate_count - len(names))
    normalized_names = [
        name if name.strip() else f"Covariate {index + 1}"
        for index, name in enumerate(names[:covariate_count])
    ]
    offset = len(expected_headers)
    types = [
        _covariate_type(row[offset + index] for row in rows)
        for index in range(covariate_count)
    ]
    return normalized_names, types


def _covariate_type(values: Iterable[str]) -> str:
    for value in values:
        try:
            float(value)
        except ValueError:
            return "factor"
    return "continuous"
