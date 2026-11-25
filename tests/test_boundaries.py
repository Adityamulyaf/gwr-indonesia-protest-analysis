import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
from shapely import Polygon, box

from src.protest_analysis.spatial.boundaries import load_boundaries, standardize_boundaries, validate_boundaries


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.master = {"3101": "31", "3171": "31"}
        self.source = gpd.GeoDataFrame({"KDBBPS": ["3101", "3171"], "KDPBPS": ["31", "31"]},
                                       geometry=[box(106, -6, 107, -5), box(107, -6, 108, -5)], crs=4326)

    def audit(self, frame):
        return validate_boundaries(standardize_boundaries(frame), self.master,
                                   expected_count=2, expected_provinces=1)

    def test_roundtrip_and_shared_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.gpkg"
            self.source.to_file(path, layer="kab", driver="GPKG", engine="pyogrio")
            self.assertTrue(self.audit(load_boundaries(path))["passed"])
            self.source.to_file(path, layer="kab2", driver="GPKG", engine="pyogrio")
            with self.assertRaises(ValueError):
                load_boundaries(path)
            self.assertTrue(self.audit(load_boundaries(path, layer="kab"))["passed"])

    def test_containment_overlap(self):
        self.source.loc[1, "geometry"] = box(106.1, -5.9, 106.2, -5.8)
        report = self.audit(self.source)
        self.assertFalse(report["passed"])
        self.assertGreater(report["overlap_m2"][0]["area"], 0)

    def test_missing_duplicate_wrong_parent(self):
        self.source["KDBBPS"] = ["3101", "3101"]
        self.source["KDPBPS"] = ["31", "99"]
        report = self.audit(self.source)
        self.assertEqual(report["duplicate_codes"], ["3101"])
        self.assertEqual(report["missing_codes"], ["3171"])
        self.assertEqual(report["parent_mismatch_rows"], [1])
        self.source.loc[0, "KDBBPS"] = " "
        self.assertEqual(self.audit(self.source)["blank_code_rows"], [0])

    def test_invalid_empty_and_unknown_crs(self):
        self.source.geometry = [Polygon(), Polygon([(0,0), (1,1), (0,1), (1,0), (0,0)])]
        report = self.audit(self.source.set_crs(None, allow_override=True))
        self.assertEqual(report["invalid_geometry_rows"], [0, 1])
        self.assertIsNone(report["crs"])
        self.assertFalse(report["overlap_checked"])
