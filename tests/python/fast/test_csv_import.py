"""Behavioral contracts for the typed CSV import parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from rc_metastudio.csv_import import CsvImportError, normalize_import_rows, parse_csv


def test_normalize_import_rows_pads_ragged_rows() -> None:
    assert normalize_import_rows([["study", "2024"], ["study-2"]], minimum_width=3) == [
        ["study", "2024", ""],
        ["study-2", "", ""],
    ]


def test_parse_csv_normalizes_headers_and_infers_covariate_types(
    tmp_path: Path,
) -> None:
    path = tmp_path / "import.csv"
    path.write_text(
        "Study,Year,Outcome,Age,Design\n"
        "A,2024,1,42,randomized\n"
        "B,2025,0,37,observational\n",
        encoding="utf-8",
    )

    result = parse_csv(
        path,
        expected_headers=["Study", "Year", "Outcome"],
        has_headers=True,
        from_excel=False,
        year_column=1,
    )

    assert result.headers == ("Study", "Year", "Outcome", "Age", "Design")
    assert result.covariate_names == ("Age", "Design")
    assert result.covariate_types == ("continuous", "factor")
    assert result.rows[0] == ("A", "2024", "1", "42", "randomized")


def test_parse_csv_assigns_names_to_blank_covariates(tmp_path: Path) -> None:
    path = tmp_path / "import.csv"
    path.write_text("Study,Year,,\nA,2024,1,yes\n", encoding="utf-8")

    result = parse_csv(
        path,
        expected_headers=["Study", "Year"],
        has_headers=True,
        from_excel=False,
        year_column=1,
    )

    assert result.covariate_names == ("Covariate 1", "Covariate 2")
    assert result.covariate_types == ("continuous", "factor")


def test_parse_csv_rejects_missing_or_invalid_year(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    missing.write_text("Study,Year\nA\n", encoding="utf-8")
    with pytest.raises(CsvImportError, match="year at row 1 is not an integer"):
        parse_csv(
            missing,
            expected_headers=["Study", "Year"],
            has_headers=True,
            from_excel=False,
            year_column=1,
        )

    invalid = tmp_path / "invalid.csv"
    invalid.write_text("Study,Year\nA,twenty\n", encoding="utf-8")
    with pytest.raises(CsvImportError, match="year at row 1 is not an integer"):
        parse_csv(
            invalid,
            expected_headers=["Study", "Year"],
            has_headers=True,
            from_excel=False,
            year_column=1,
        )


def test_parse_csv_returns_empty_result_for_empty_input(tmp_path: Path) -> None:
    (tmp_path / "empty.csv").write_text("", encoding="utf-8")
    result = parse_csv(
        tmp_path / "empty.csv",
        expected_headers=["Study", "Year"],
        has_headers=True,
        from_excel=False,
        year_column=1,
    )

    assert result.headers == ()
    assert result.rows == ()
    assert result.covariate_names == ()
    assert result.covariate_types == ()
