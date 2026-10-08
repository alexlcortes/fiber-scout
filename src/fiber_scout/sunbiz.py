"""Search downloaded Florida Division of Corporations data files."""

import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import BinaryIO, TypedDict

CORPORATE_RECORD_LENGTH = 1_440
CORPORATE_NAME_SLICE = slice(12, 204)
CORPORATE_STATUS_SLICE = slice(204, 205)
CORPORATE_FILING_TYPE_SLICE = slice(205, 220)
CORPORATE_ADDRESS_1_SLICE = slice(220, 262)
CORPORATE_ADDRESS_2_SLICE = slice(262, 304)
CORPORATE_CITY_SLICE = slice(304, 332)
CORPORATE_STATE_SLICE = slice(332, 334)
CORPORATE_ZIP_SLICE = slice(334, 344)
CORPORATE_NUMBER_SLICE = slice(0, 12)

SUNBIZ_CORPORATE_DATA_DEFINITIONS = (
    "https://dos.sunbiz.org/data-definitions/cor.html"
)
SUNBIZ_SEARCH_GUIDE = (
    "https://dos.fl.gov/sunbiz/search/guides/corporation-records/"
)


class SunbizEntity(TypedDict):
    """Fields returned from a matching corporate data-file record."""

    document_number: str
    legal_name: str
    status: str
    filing_type: str
    address: str
    city: str
    state: str
    zip_code: str
    data_file: str
    source_url: str


class SunbizSearchResult(TypedDict):
    """Matches and scan metadata for a local Sunbiz data-file search."""

    query: str
    matches: list[SunbizEntity]
    truncated: bool
    records_scanned: int
    malformed_records: int


class SunbizDataError(RuntimeError):
    """Raised when downloaded Sunbiz data cannot be searched."""


def _read_field(record: bytes, field: slice) -> str:
    return record[field].decode("ascii", errors="replace").strip()


def _open_records(path: Path) -> Iterator[tuple[str, BinaryIO]]:
    """Yield text records from a fixed-width text file or a ZIP archive."""
    if path.suffix.lower() != ".zip":
        with path.open("rb") as source_file:
            yield path.name, source_file
        return

    try:
        with zipfile.ZipFile(path) as archive:
            text_files = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and name.lower().endswith(".txt")
            ]
            if not text_files:
                raise SunbizDataError(f"ZIP contains no .txt records: {path}")
            for name in text_files:
                with archive.open(name) as source_file:
                    yield f"{path.name}:{name}", source_file
    except zipfile.BadZipFile as error:
        raise SunbizDataError(f"invalid Sunbiz ZIP archive: {path}") from error


def _iter_data_files(paths: Sequence[str | Path]) -> Iterator[Path]:
    if isinstance(paths, (str, bytes, Path)):
        raise ValueError("data_files must be a sequence of file paths")
    if not paths:
        raise ValueError("provide at least one Sunbiz data file")
    for path in paths:
        if not isinstance(path, (str, Path)):
            raise TypeError("each data file must be a string path or Path")
        yield Path(path)


def search_sunbiz(
    name: str,
    data_files: Sequence[str | Path],
    *,
    limit: int = 20,
    active_only: bool = False,
) -> SunbizSearchResult:
    """Search local corporate data files for a case-insensitive name substring.

    Pass a quarterly ZIP file or one or more extracted fixed-width text files.
    The function does not download data or call the Sunbiz website. A match is
    a corporate-record lead, not proof that a business occupies an address.
    """
    query = " ".join(name.split())
    if not query:
        raise ValueError("name must contain non-whitespace characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")
    query_folded = query.casefold()

    matches: list[SunbizEntity] = []
    records_scanned = 0
    malformed_records = 0
    truncated = False

    for path in _iter_data_files(data_files):
        for file_name, source_file in _open_records(path):
            for raw_record in source_file:
                record = raw_record.rstrip(b"\r\n")
                if not record:
                    continue
                records_scanned += 1
                if len(record) != CORPORATE_RECORD_LENGTH:
                    malformed_records += 1
                    continue

                legal_name = _read_field(record, CORPORATE_NAME_SLICE)
                if query_folded not in legal_name.casefold():
                    continue
                status = _read_field(record, CORPORATE_STATUS_SLICE)
                if active_only and status.upper() != "A":
                    continue
                if len(matches) == limit:
                    truncated = True
                    return {
                        "query": query,
                        "matches": matches,
                        "truncated": truncated,
                        "records_scanned": records_scanned,
                        "malformed_records": malformed_records,
                    }

                address = " ".join(
                    part
                    for part in (
                        _read_field(record, CORPORATE_ADDRESS_1_SLICE),
                        _read_field(record, CORPORATE_ADDRESS_2_SLICE),
                    )
                    if part
                )
                matches.append(
                    {
                        "document_number": _read_field(
                            record, CORPORATE_NUMBER_SLICE
                        ),
                        "legal_name": legal_name,
                        "status": status,
                        "filing_type": _read_field(
                            record, CORPORATE_FILING_TYPE_SLICE
                        ),
                        "address": address,
                        "city": _read_field(record, CORPORATE_CITY_SLICE),
                        "state": _read_field(record, CORPORATE_STATE_SLICE),
                        "zip_code": _read_field(record, CORPORATE_ZIP_SLICE),
                        "data_file": file_name,
                        "source_url": SUNBIZ_CORPORATE_DATA_DEFINITIONS,
                    }
                )

    return {
        "query": query,
        "matches": matches,
        "truncated": truncated,
        "records_scanned": records_scanned,
        "malformed_records": malformed_records,
    }
