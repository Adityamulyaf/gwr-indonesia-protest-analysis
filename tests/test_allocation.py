import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from src.protest_analysis.spatial.allocate import allocate


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.master = pd.DataFrame(dict(bps_kabkota=["1101","1102","1103"],
            nama_kabkota=["Kab. A","Kab. B","Kab. C"],bps_provinsi=["11"]*3,nama_provinsi=["Aceh"]*3))
        self.d = gpd.GeoDataFrame(self.master, geometry=[box(0,0,1,1),box(1,0,2,1),box(3,0,4,1)], crs=4326)
        self.exception = gpd.GeoDataFrame({"source_fid":[9]},geometry=[box(.6,.1,.9,.9)],crs=4326)
        self.mask = gpd.GeoDataFrame({"bps_kabkota":["1101"]},geometry=[box(.1,.6,.4,.9)],crs=4326)

    def run_cases(self, cases, before=None):
        rows = [dict(event_id_cnty=str(i), longitude=.3,latitude=.3,geo_precision="1",
                     admin1="Aceh",admin2="A",location="L") | change for i, change in enumerate(cases)]
        return allocate(pd.DataFrame(rows), self.master, self.d, self.d if before is None else before,
                        self.exception, self.mask)

    def test_interior_outside_shared_boundary_and_reconciliation(self):
        ledger, y = self.run_cases([{}, {"longitude":5}, {"longitude":1}, {"geo_precision":"2"}])
        self.assertEqual(ledger.status.tolist(), ["allocated","unallocated","unallocated","review"])
        self.assertEqual(ledger.candidates.iloc[2],"1101|1102")
        self.assertIn("boundary",ledger.reasons.iloc[2])
        self.assertEqual(y.protest_count.tolist(),[1,0,0])
        self.assertEqual(y.candidate_count.sum(),2)
        self.assertEqual(y.protest_count.sum() + ledger.allocated_bps.isna().sum(),4)

    def test_multiple_interiors(self):
        self.d.loc[1,"geometry"] = box(.1,.1,2,1)
        ledger,_ = self.run_cases([{}])
        self.assertEqual(ledger.interior.iloc[0],"1101|1102")
        self.assertTrue(ledger.candidate_bps.isna().all())

    def test_missing_admin2_and_unspecified(self):
        ledger,_ = self.run_cases([{"admin2":""},{"admin2":None,"location":"Jakarta - Unspecified"}])
        self.assertEqual(ledger.status.tolist(),["review","unallocated"])
        self.assertTrue(ledger.allocated_bps.isna().all())
        self.assertTrue(pd.isna(ledger.candidate_bps.iloc[1]))

    def test_exception_mask_and_changed_membership(self):
        before = self.d.copy()
        before.loc[0,"geometry"] = box(.5,0,1,1)
        ledger,_ = self.run_cases([{"longitude":.8},{"latitude":.8},{}],before)
        for reason, flags in zip(["exception","mask","quarantine_change"], ledger.reasons):
            self.assertIn(reason,flags)
        self.assertTrue(ledger.candidate_bps.isna().all())

    def test_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError,"duplikat"):
            self.run_cases([{},{"event_id_cnty":"0"}])

    def test_ambiguous_label_requires_clean_interior_in_provincial_label_set(self):
        self.master.loc[1, "nama_kabkota"] = "Kota A"
        cases = [{}, {"longitude": 1.5}, {"longitude": 3.5}, {"admin1": "Bali"},
                 {"geo_precision": "2"}, {"location": "Jakarta - Unspecified"},
                 {"longitude": 1}, {"longitude": .8}, {"latitude": .8}]
        ledger, table = self.run_cases(cases)
        self.assertTrue(ledger.bps_conservative.isna().all())
        self.assertEqual(ledger.bps_ambiguity_resolved.dropna().to_dict(), {0: "1101", 1: "1102"})
        self.assertEqual(table.promoted_ambiguity.tolist(), [1, 1, 0])
        self.assertEqual(ledger.allocation_rule.iloc[0], "label_set_contains_interior")
        self.assertEqual(ledger.label_codes.iloc[0], "1101|1102")
        self.assertEqual(ledger.bps_permissive.notna().sum(), 5)

    def use_jakarta(self):
        self.master.loc[0, ["bps_kabkota", "nama_kabkota", "bps_provinsi", "nama_provinsi"]] = [
            "3173", "Kota Adm. Jakarta Pusat", "31", "DKI Jakarta"]
        self.d.loc[0, "bps_kabkota"] = "3173"
        return dict(admin1="Jakarta", admin2="Central Jakarta", event_date="2025-03-01")

    def test_alias_exact_scope_and_period(self):
        alias = self.use_jakarta()
        changes = [{"event_date": "2024-10-20"}, {"event_date": "16/11/2025"},
                   {"event_date": "2024-10-19"}, {"event_date": "2025-11-17"},
                   {"event_date": None}, {"admin1": "Aceh"}, {"admin1": "DKI Jakarta"},
                   {"admin2": "Central Jakart"}, {"longitude": 1.5}, {"geo_precision": "3"},
                   {"geo_precision": pd.NA}, {"location": "Jakarta - Unspecified"}]
        ledger, table = self.run_cases([alias | change for change in changes])
        self.assertTrue(ledger.bps_ambiguity_resolved.isna().all())
        self.assertEqual(ledger.bps_enhanced.dropna().to_dict(), {0: "3173", 1: "3173"})
        self.assertEqual(table.promoted_alias.tolist(), [2, 0, 0])
        self.assertEqual(ledger.allocation_rule.iloc[0], "alias_central_jakarta")
        self.assertTrue(pd.isna(ledger.bps_permissive.iloc[-1]))

    def test_quarantine_boundary_mask_exception_and_multiple_veto_promotions(self):
        for rule in ("ambiguity", "alias"):
            with self.subTest(rule=rule):
                self.setUp()
                labels = {}
                if rule == "alias":
                    labels = self.use_jakarta()
                else:
                    self.master.loc[1, "nama_kabkota"] = "Kota A"
                before = self.d.copy()
                before.loc[0, "geometry"] = box(.45, 0, 1, 1)
                self.d.loc[2, "geometry"] = box(.92, .1, .98, .9)
                cases = [{}, {"longitude": 1}, {"longitude": .8}, {"latitude": .8},
                         {"longitude": .95}]
                ledger, _ = self.run_cases([labels | case for case in cases], before)
                self.assertTrue(ledger.bps_permissive.isna().all())
                self.assertTrue(ledger.bps_enhanced.isna().all())
                for reason, flags in zip(("quarantine_change", "boundary", "exception", "mask",
                                          "multiple"), ledger.reasons):
                    self.assertIn(reason, flags)

    def test_outside_and_conflicting_codes_are_distinct(self):
        ledger, _ = self.run_cases([{"longitude": 5}, {"longitude": 1.5}])
        self.assertEqual(ledger.reasons.tolist(), ["outside", "label_disagreement"])
        self.assertEqual(ledger.status_enhanced.tolist(), ["unallocated", "review"])
        self.assertEqual(ledger.bps_permissive.dropna().to_dict(), {1: "1102"})
