"""Prepare the September 2023 BIG catalog snapshot for academic review."""
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely

from src.protest_analysis.spatial.boundaries import validate_boundaries

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/spatial"
D = DATA / "big_sep2023"


def polygon_parts(geometry):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def repair(geometry):
    if geometry is None or geometry.is_empty or geometry.is_valid:
        return geometry
    return shapely.union_all(list(polygon_parts(shapely.make_valid(geometry))))


def main():
    manifest = json.loads((D / "manifest.json").read_text())
    chunks = []
    for name, digest in manifest["sha256"].items():
        path = D / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Hash mismatch: {name}")
        if name.endswith(".geojson"):
            # ArcGIS also exports Z and null M ordinates. Use horizontal boundaries only.
            chunk = pyogrio.read_dataframe(path, force_2d=True)
            if chunk.crs.to_epsg() != manifest["outSR"]:
                raise ValueError(f"Unexpected CRS: {name}")
            chunks.append(chunk)
    raw = pd.concat(chunks, ignore_index=True).sort_values("FID").reset_index(drop=True)
    ids = json.loads((D / "ids.json").read_bytes())["objectIds"]
    if sorted(raw.FID) != sorted(ids) or not raw.FID.is_unique:
        raise ValueError("Incomplete or repeated features")
    if set(raw.METADATA) != {manifest["identifier"]}:
        raise ValueError("Unexpected source edition")
    master = pd.read_csv(DATA / "bps_2025_1/master.csv", dtype=str)
    # The SIG BPS extract abbreviates .10 and .20 as .1 and .2. The 23
    # expansions are corroborated by exact PUM names in the 2025 comparison.
    master["join_pum"] = master.kode_pum.str.replace(r"^(\d{2}\.\d)$", r"\g<1>0", regex=True)
    raw["join_pum"] = raw.KDPKAB.astype("string").str.strip()
    raw = raw.merge(master, on="join_pum", how="left", validate="many_to_one")
    raw = raw.rename(columns={"kode_bps": "bps_kabkota"})
    known = raw.loc[raw.bps_kabkota.notna()].copy()
    unknown = raw.loc[raw.bps_kabkota.isna()].copy()
    unknown["source_fid"] = unknown.FID
    expanded = known.loc[known.kode_pum.ne(known.join_pum)]
    if not ("KABUPATEN " + expanded.WADMKK.str.strip().str.upper()).eq(expanded.nama_pum).all():
        raise ValueError("Expanded PUM codes require exact confirmation of official names")
    repeated = known.loc[known.bps_kabkota.duplicated(keep=False)]
    for _, group in repeated.groupby("bps_kabkota"):
        if any(group[col].nunique(dropna=False) != 1 for col in ["NAMOBJ", "WADMKK", "WADMPR", "join_pum"]):
            raise ValueError("Conflicting identities on multipart rows")
    keys = dict(zip(master.kode_bps, master.bps_provinsi))
    raw_validation = validate_boundaries(raw, keys)
    bad_before = raw.loc[~raw.geometry.is_valid, "FID"].tolist()
    known.geometry = known.geometry.map(repair)
    known["source_fids"] = known.FID.astype(str)
    fields = ["bps_kabkota", "bps_provinsi", "nama_bps", "join_pum", "source_fids", "geometry"]
    multiparts = known.bps_kabkota.duplicated(keep=False)
    combined = known.loc[multiparts, fields].dissolve(by="bps_kabkota", as_index=False,
        aggfunc={"bps_provinsi":"first", "nama_bps":"first", "join_pum":"first", "source_fids":",".join})
    districts = pd.concat([known.loc[~multiparts, fields], combined]).sort_values("bps_kabkota").reset_index(drop=True)
    districts["geometry"] = districts.geometry.map(repair)
    audit = validate_boundaries(districts, keys)
    gpkg = D / "kabkota_bps.gpkg"
    districts.to_file(gpkg, layer="kabkota", driver="GPKG")
    unknown.to_file(gpkg, layer="unresolved_features", driver="GPKG")
    overlaps = []
    for match in audit["overlap_m2"]:
        i,j = match["rows"]
        overlaps.append({"code_a":districts.bps_kabkota.iloc[i],"code_b":districts.bps_kabkota.iloc[j],
                         "area_m2":match["area"], "geometry":districts.geometry.iloc[i].intersection(districts.geometry.iloc[j])})
    if overlaps:
        gpd.GeoDataFrame(overlaps,crs=districts.crs).to_file(gpkg,layer="overlaps",driver="GPKG")
    with gpkg.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"raw":raw_validation,"standardized":audit,"invalid_source_fids":bad_before,
              "mapped_rows":len(known),"unresolved_fids":unknown.FID.tolist(),
              "provinces":districts.bps_provinsi.value_counts().sort_index().to_dict(),
              "jakarta":districts.loc[districts.bps_provinsi.eq("31"),"bps_kabkota"].tolist(),
              "overlap_sum_m2":sum(r["area_m2"] for r in overlaps),
              "gpkg_sha256":digest}
    (D/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print({k:report[k] for k in ("mapped_rows","invalid_source_fids","overlap_sum_m2","gpkg_sha256")})
    print("unresolved",len(unknown),"features",len(districts),"overlaps",len(overlaps),"passed",audit["passed"])


if __name__ == "__main__":
    main()
