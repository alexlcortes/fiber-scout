import tempfile
import unittest
import zipfile
from pathlib import Path

from fiber_scout.sunbiz import (
    CORPORATE_RECORD_LENGTH,
    SUNBIZ_CORPORATE_DATA_DEFINITIONS,
    SunbizDataError,
    search_sunbiz,
)


def corporate_record(
    number: str,
    name: str,
    *,
    status: str = "A",
    filing_type: str = "FLAL",
    address: str = "100 Main St",
    city: str = "Tampa",
    state: str = "FL",
    zip_code: str = "33602",
) -> bytes:
    fields = [
        (0, 12, number),
        (12, 204, name),
        (204, 205, status),
        (205, 220, filing_type),
        (220, 262, address),
        (304, 332, city),
        (332, 334, state),
        (334, 344, zip_code),
    ]
    record = bytearray(b" " * CORPORATE_RECORD_LENGTH)
    for start, end, value in fields:
        encoded = value.encode("ascii")
        if len(encoded) > end - start:
            raise ValueError(f"{value!r} exceeds field width")
        record[start : start + len(encoded)] = encoded
    return bytes(record)


class SunbizSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.data_file = Path(self.temp_dir.name) / "corporate.txt"
        records = [
            corporate_record("P12345678901", "Example Fiber LLC"),
            corporate_record(
                "P98765432109",
                "Example Fiber Holdings, Inc.",
                status="I",
                filing_type="DOMP",
                address="200 Oak Ave",
                city="Miami",
                state="FL",
                zip_code="33101",
            ),
            corporate_record("P44444444444", "Unrelated Company Inc."),
        ]
        self.data_file.write_bytes(b"\n".join(records) + b"\n")

    def test_searches_case_insensitive_substrings_and_returns_fields(self) -> None:
        result = search_sunbiz("  EXAMPLE fiber  ", [self.data_file])

        self.assertEqual(result["query"], "EXAMPLE fiber")
        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(result["records_scanned"], 3)
        self.assertEqual(result["malformed_records"], 0)
        self.assertFalse(result["truncated"])
        match = result["matches"][0]
        self.assertEqual(match["document_number"], "P12345678901")
        self.assertEqual(match["legal_name"], "Example Fiber LLC")
        self.assertEqual(match["status"], "A")
        self.assertEqual(match["filing_type"], "FLAL")
        self.assertEqual(match["address"], "100 Main St")
        self.assertEqual(match["city"], "Tampa")
        self.assertEqual(match["state"], "FL")
        self.assertEqual(match["zip_code"], "33602")
        self.assertEqual(match["data_file"], "corporate.txt")
        self.assertEqual(match["source_url"], SUNBIZ_CORPORATE_DATA_DEFINITIONS)

    def test_can_filter_to_active_entities(self) -> None:
        result = search_sunbiz("Example Fiber", [self.data_file], active_only=True)

        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["status"], "A")

    def test_reads_text_members_in_zip_archive(self) -> None:
        zip_path = Path(self.temp_dir.name) / "corporate.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr(
                "corporate/part-0.txt",
                corporate_record("P12345678901", "Example Fiber LLC") + b"\n",
            )
            archive.writestr("README.md", "not a corporate data file")

        result = search_sunbiz("Example Fiber", [zip_path])

        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(
            result["matches"][0]["data_file"],
            "corporate.zip:corporate/part-0.txt",
        )

    def test_records_malformed_lines_without_silent_loss(self) -> None:
        self.data_file.write_bytes(b"too short\n")

        result = search_sunbiz("Example", [self.data_file])

        self.assertEqual(result["matches"], [])
        self.assertEqual(result["malformed_records"], 1)

    def test_limit_marks_results_as_truncated(self) -> None:
        result = search_sunbiz("Example Fiber", [self.data_file], limit=1)

        self.assertEqual(len(result["matches"]), 1)
        self.assertTrue(result["truncated"])

    def test_rejects_invalid_arguments(self) -> None:
        invalid_cases = [
            ("  ", [self.data_file], {}, "name"),
            ("Example", [], {}, "at least one"),
            ("Example", [self.data_file], {"limit": 0}, "limit"),
            ("Example", self.data_file, {}, "sequence"),
        ]
        for name, paths, options, message in invalid_cases:
            with self.subTest(name=name, paths=paths), self.assertRaisesRegex(
                ValueError, message
            ):
                search_sunbiz(name, paths, **options)

    def test_reports_zip_without_text_files(self) -> None:
        zip_path = Path(self.temp_dir.name) / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("README.md", "no data")

        with self.assertRaisesRegex(SunbizDataError, "no .txt records"):
            search_sunbiz("Example", [zip_path])


if __name__ == "__main__":
    unittest.main()
