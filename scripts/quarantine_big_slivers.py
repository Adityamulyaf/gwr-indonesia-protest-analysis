"""Quarantine the positive-area slivers on both sides; retain the original layer."""
import hashlib
import json
from collections import defaultdict

import geopandas as gpd
import pandas as pd
import shapely

from scripts.prepare_big_sep2023 import DATA, D, polygon_parts
from src.protest_analysis.spatial.boundaries import validate_boundaries


def main():
    source = D / "kabkota_bps.gpkg"
    districts = gpd.read_file(source, layer="kabkota")
    cuts = defaultdict(list)
    overlaps = gpd.read_file(source, layer="overlaps")
    for row in overlaps.itertuples():
        if row.area_m2 > 0.01:
            raise ValueError("Intersection exceeds reviewed sliver size; review source boundaries.")
        for polygon in polygon_parts(row.geometry):
            # Working guard band of about one millimetre at the equator.
            # Both districts surrender the same uncertain patch.
            mask = polygon.buffer(1e-8, quad_segs=2)
            for code in (row.code_a, row.code_b):
                cuts[code].append(mask)

    masks = []
    areas = districts.to_crs(6933).area
    for i, row in districts.iterrows():
        if row.bps_kabkota in cuts:
            mask = shapely.union_all(cuts[row.bps_kabkota])
            geom = row.geometry.difference(mask)
            if geom.geom_type not in ("Polygon", "MultiPolygon"):
                geom = shapely.union_all(list(polygon_parts(geom)))
            districts.at[i, "geometry"] = geom
            masks.append({"bps_kabkota":row.bps_kabkota,"geometry":mask})
    # Difference can introduce new, non-collinear vertices along shared sides.
    # Retain the comparison layer and use a conservative interior on only the
    # rows where positive-area residuals are actually measured.
    master = pd.read_csv(DATA / "bps_2025_1/master.csv", dtype=str)
    parents = dict(zip(master.kode_bps, master.bps_provinsi))
    intermediate = validate_boundaries(districts, parents)
    residuals = intermediate["overlap_m2"]
    if any(issue["area"] > 0.01 for issue in residuals):
        raise ValueError("Review substantial residual overlap before continuing")
    affected = sorted({i for issue in residuals for i in issue["rows"]})
    for i in affected:
        districts.at[i, "geometry"] = districts.geometry.iloc[i].buffer(-1e-8, quad_segs=1, join_style="mitre")
    output = D / "kabkota_analysis.gpkg"
    districts.to_file(output, layer="kabkota", driver="GPKG")
    unknown = gpd.read_file(source, layer="unresolved_features", fid_as_index=True)
    if "source_fid" not in unknown:
        unknown["source_fid"] = unknown.index
    expected = json.loads((D / "validation.json").read_text())["unresolved_fids"]
    if sorted(unknown.source_fid) != sorted(expected):
        raise ValueError("Source FIDs lost in unresolved features")
    unknown.reset_index(drop=True).to_file(output, layer="unresolved_features", driver="GPKG")
    gpd.GeoDataFrame(masks, crs=districts.crs).to_file(output, layer="sliver_review", driver="GPKG")
    saved = gpd.read_file(output, layer="kabkota")
    assert saved.bps_kabkota.tolist() == districts.bps_kabkota.tolist()
    report = validate_boundaries(saved, parents)
    report["guard_band_degrees"] = 1e-8
    report["interior_codes"] = districts.iloc[affected].bps_kabkota.tolist()
    report["residual_pairs_before_interior"] = len(residuals)
    delta = areas - saved.to_crs(6933).area
    report["area_change_m2_sum"] = float(delta.sum())
    report["largest_absolute_district_area_change_m2"] = float(delta.abs().max())
    with output.open("rb") as stream:
        report["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    (D/"analysis_validation.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print("passed", report["passed"], "overlaps", len(report["overlap_m2"]),
          "invalid", report["invalid_geometry_rows"], "area change", delta.sum(), "sha256", report["sha256"])


if __name__ == "__main__":
    main()
