"""Integration tests use synthetic rows and private temporary directories."""
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.protest_analysis.data.audit_acled import COUNTS_FILE, REVIEW_FILE, audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.source = self.folder / "input.csv"
        self.output = self.folder / "out"
        self.base = dict(event_id_cnty="001", event_date="20 October 2024", country="Indonesia",
                         event_type="Protests", admin1="A", admin2="X", location="L",
                         latitude="-5", longitude="110", geo_precision="1")

    def write(self, *overrides, omit=()):
        fields = [name for name in self.base if name not in omit]
        with self.source.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for changes in overrides:
                writer.writerow({**self.base, **changes})

    def results(self, name):
        with (self.output / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_duplicate_and_missing_ids(self):
        self.write({}, {"event_id_cnty": "001 "}, {"event_id_cnty": "1"}, {"event_id_cnty": " "})
        s = audit(self.source, self.output)
        self.assertEqual(s["duplicated_event_id_rows"], 2)
        self.assertEqual(s["missing_event_id_rows"], 1)
        self.assertEqual(s["missing_or_duplicated_event_ids_rows"], 3)
        self.assertEqual(s["records"], 4)

    def test_invalid_coordinates(self):
        self.write({"latitude": "-91"}, {"longitude": "181"}, {"latitude": ""},
                   {"longitude": "abc"}, {"latitude": "inf"}, {"latitude": "-90", "longitude": "180"})
        s = audit(self.source, self.output)
        self.assertEqual(s["invalid_coordinate_rows"], 5)
        self.assertEqual(s["missing_latitude"], 1)
        self.assertEqual(s["missing_longitude"], 0)
        self.assertEqual(len(self.results(REVIEW_FILE)), 5)

    def test_required_columns(self):
        self.write({}, omit=("admin2", "latitude"))
        with self.assertRaisesRegex(ValueError, "admin2, latitude"):
            audit(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_blank_admin_and_overlapping_review_reasons(self):
        self.write({"admin2": "  ", "geo_precision": "2"}, {"geo_precision": ""},
                   {"admin1": " "}, {"event_type": "Riots", "admin2": ""})
        s = audit(self.source, self.output)
        self.assertEqual(s["missing_admin2_all_types"], 2)
        self.assertEqual(s["missing_admin2_protests"], 1)
        self.assertEqual(s["missing_admin1"], 1)
        self.assertEqual(s["protest_counts_mapped_by_labels_provisionally"], 2)
        self.assertEqual(s["protest_location_review_original_rules"], 2)
        review = self.results(REVIEW_FILE)
        self.assertEqual(len(review), 3)
        self.assertEqual(review[0]["missing_admin2"], "True")
        self.assertEqual(review[0]["geo_precision_not_1"], "True")

    def test_categories_and_provisional_counts_reconcile(self):
        self.write({}, {"geo_precision": "2.0"}, {"admin1": "B"},
                   {"admin2": ""}, {"event_type": "Riots"}, {"event_type": " "})
        s = audit(self.source, self.output)
        self.assertEqual(s["event_type_counts"], {"Protests": 4, "Riots": 1, "<MISSING>": 1})
        self.assertEqual(sum(s["event_type_counts"].values()), s["records"])
        self.assertEqual([(r["admin1"], r["admin2"], r["recorded_protests"])
                          for r in self.results(COUNTS_FILE)], [("A", "X", "2"), ("B", "X", "1")])
        self.assertEqual(s["protest_counts_mapped_by_labels_provisionally"] + s["missing_admin2_protests"], 4)
        self.assertEqual(s["protests_geo_precision_2_or_3"], 1)

    def test_dates_and_empty_selection(self):
        self.write(*[{"event_type": "Riots", "event_date": date}
                     for date in ("20 October 2024", "2025-11-16", "01/12/2025", "invalid")])
        s = audit(self.source, self.output)
        self.assertEqual((s["min_date"], s["max_date"]), ("2024-10-20", "2025-12-01"))
        self.assertEqual((s["unparseable_dates"], s["dates_outside_project_period"]), (1, 1))
        self.assertEqual(self.results(REVIEW_FILE), [])
        self.assertEqual(self.results(COUNTS_FILE), [])

    def test_cli_outputs_and_input_integrity(self):
        self.write({})
        original = self.source.read_bytes()
        result = subprocess.run(
            [sys.executable, "-m", "src.protest_analysis.data.audit_acled",
             "--input", str(self.source), "--output", str(self.output)],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.source.read_bytes(), original)
        saved = json.loads((self.output / "audit_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["sha256"], hashlib.sha256(original).hexdigest())
        self.assertIn(saved["sha256"], (self.output / "AUDIT_README.md").read_text(encoding="utf-8"))
        self.assertEqual(saved, audit(self.source, self.output))

    def test_input_output_collision_preserves_raw_bytes(self):
        self.source = self.folder / REVIEW_FILE
        self.write({})
        original = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, "bertabrakan"):
            audit(self.source, self.folder)
        self.assertEqual(self.source.read_bytes(), original)

    def test_reference_checks_counts_and_fingerprint(self):
        self.write({})
        reference = self.folder / "reference.json"
        baseline = audit(self.source, self.output)
        command = [sys.executable, "-m", "src.protest_analysis.data.audit_acled",
                   "--input", str(self.source), "--output", str(self.output), "--reference", str(reference)]
        root = Path(__file__).resolve().parents[1]
        for change, expected_code in [({}, 0), ({"records": 9}, 2), ({"sha256": "different"}, 2)]:
            with self.subTest(change=change):
                reference.write_text(json.dumps({**baseline, **change}), encoding="utf-8")
                proc = subprocess.run(command, capture_output=True, text=True, cwd=root)
                self.assertEqual(proc.returncode, expected_code, proc.stderr)
