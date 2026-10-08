"""CSV helpers for selecting and updating prospect research rows."""

import csv
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias

CSVValue: TypeAlias = str | int | float | None
CSVRow: TypeAlias = dict[str, str]

AGENT_OWNED_COLUMNS = (
    "business_name",
    "owner_or_manager",
    "website",
    "phone",
    "email",
    "contact_name",
    "industry",
    "est_employees",
    "needs_profile",
    "fit_score",
    "source_urls",
    "confidence",
    "status",
    "notes",
)


def _read_csv_with_headers(path: str | Path) -> tuple[list[str], list[CSVRow]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames
        if headers is None:
            raise ValueError("CSV must include a header row")
        if any(not header for header in headers):
            raise ValueError("CSV headers must not be empty")
        if len(headers) != len(set(headers)):
            raise ValueError("CSV headers must be unique")

        rows: list[CSVRow] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {row_number} does not match the header")
            rows.append({header: row[header] for header in headers})

    return headers, rows


def read_csv(path: str | Path) -> list[CSVRow]:
    """Read a UTF-8 CSV into rows of string values."""
    _, rows = _read_csv_with_headers(path)
    return rows


def select_pending_rows(
    rows: list[CSVRow], limit: int | None = None
) -> list[int]:
    """Return zero-based row indexes whose status is not ``done``."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be zero or greater")

    pending_indexes = [
        index
        for index, row in enumerate(rows)
        if row.get("status", "").strip().lower() != "done"
    ]
    return pending_indexes if limit is None else pending_indexes[:limit]


def write_results(
    csv_path: str | Path,
    updates: Mapping[int, Mapping[str, CSVValue]],
    output_path: str | Path | None = None,
) -> None:
    """Write updates to agent-owned columns, preserving all other field values.

    Row indexes are zero-based and refer to data rows, not the CSV header.
    When ``output_path`` is omitted, the input CSV is updated atomically.
    """
    source_path = Path(csv_path)
    destination_path = Path(output_path) if output_path is not None else source_path
    headers, rows = _read_csv_with_headers(source_path)

    for row_index, update in updates.items():
        if not isinstance(row_index, int) or not 0 <= row_index < len(rows):
            raise IndexError(f"row index out of range: {row_index}")
        unexpected_columns = set(update) - set(AGENT_OWNED_COLUMNS)
        if unexpected_columns:
            names = ", ".join(sorted(unexpected_columns))
            raise ValueError(f"updates may only set agent-owned columns: {names}")
        if "status" not in update or not str(update["status"] or "").strip():
            raise ValueError("each row update must include a non-empty status")
        if any(
            not isinstance(value, (str, int, float)) and value is not None
            for value in update.values()
        ):
            raise TypeError("CSV update values must be strings, numbers, or None")

    output_headers = list(headers)
    output_headers.extend(
        column for column in AGENT_OWNED_COLUMNS if column not in output_headers
    )
    for row_index, update in updates.items():
        rows[row_index].update(
            {key: "" if value is None else str(value) for key, value in update.items()}
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=destination_path.parent,
            delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(csv_file, fieldnames=output_headers)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, destination_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
