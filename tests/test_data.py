import csv
import tempfile
import unittest
from pathlib import Path

from fiber_scout.data import read_csv, select_pending_rows, write_results


class CSVDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.csv_path = Path(self.temp_dir.name) / "prospects.csv"
        with self.csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=["address", "city", "status"])
            writer.writeheader()
            writer.writerows(
                [
                    {"address": "12 Main St", "city": "Tampa", "status": ""},
                    {"address": "34 Oak St", "city": "Miami", "status": "done"},
                    {"address": "56 Pine St", "city": "Orlando", "status": "in_progress"},
                ]
            )

    def test_read_csv_preserves_input_values(self) -> None:
        rows = read_csv(self.csv_path)

        self.assertEqual(rows[0]["address"], "12 Main St")
        self.assertEqual(rows[1]["city"], "Miami")

    def test_select_pending_rows_skips_done_and_applies_limit(self) -> None:
        rows = read_csv(self.csv_path)

        self.assertEqual(select_pending_rows(rows), [0, 2])
        self.assertEqual(select_pending_rows(rows, limit=1), [0])
        self.assertEqual(select_pending_rows(rows, limit=0), [])

    def test_write_results_only_updates_agent_owned_columns(self) -> None:
        original_rows = read_csv(self.csv_path)
        output_path = Path(self.temp_dir.name) / "results.csv"

        write_results(
            self.csv_path,
            {0: {"business_name": "Example Co", "status": "done"}},
            output_path,
        )

        result_rows = read_csv(output_path)
        self.assertEqual(result_rows[0]["address"], original_rows[0]["address"])
        self.assertEqual(result_rows[0]["city"], original_rows[0]["city"])
        self.assertEqual(result_rows[0]["business_name"], "Example Co")
        self.assertEqual(result_rows[0]["status"], "done")
        self.assertEqual(read_csv(self.csv_path), original_rows)

    def test_write_results_can_update_input_file(self) -> None:
        write_results(self.csv_path, {2: {"phone": "555-0100", "status": "done"}})

        rows = read_csv(self.csv_path)
        self.assertEqual(rows[2]["phone"], "555-0100")
        self.assertEqual(rows[2]["address"], "56 Pine St")

    def test_write_results_rejects_changes_to_input_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "agent-owned"):
            write_results(self.csv_path, {0: {"address": "Changed", "status": "done"}})

        self.assertEqual(read_csv(self.csv_path)[0]["address"], "12 Main St")

    def test_write_results_requires_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "status"):
            write_results(self.csv_path, {0: {"business_name": "Example Co"}})


if __name__ == "__main__":
    unittest.main()
