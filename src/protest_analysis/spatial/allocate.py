"""Allocation of audited ACLED records to validated BIG polygons."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas as gpd
import pandas as pd

from ..data.load import load_acled
from ..data.validate import clean_fields, precision_labels
from .boundaries import load_boundaries

ROOT = Path(__file__).resolve().parents[3]
BIG = ROOT / "data/spatial/big_sep2023"
BPS = ROOT / "data/spatial/bps_2025_1"
VERSION = "v2"
POLICIES = ("conservative", "ambiguity_resolved", "enhanced", "permissive")
PRIMARY = "enhanced"
# Period of application in this study. The BPS publication verifies the name.
CENTRAL_JAKARTA = {
    "admin1": "Jakarta",
    "admin2": "Central Jakarta",
    "bps": "3173",
    "valid_from": "2024-10-20",
    "valid_through": "2025-11-16",
    "reference": "https://jakpuskota.bps.go.id/en/publication/2025/02/28/"
                 "edbb1544aceef3f640647768/kota-jakarta-pusat-dalam-angka-2025.html",
}
DIRECTIONS = {"central": "tengah", "west": "barat", "east": "timur", "north": "utara",
              "south": "selatan", "southeast": "tenggara", "southwest": "barat daya"}
ALIASES = {"jakarta": "dki jakarta", "yogyakarta": "di yogyakarta", "bangka-belitung": "kepulauan bangka belitung",
           "highland papua": "papua pegunungan"}


def label(name, province=False):
    value = str(name).strip().lower()
    if province:
        value = ALIASES.get(value, value)
    value = re.sub(r"^(kab\.?(?:upaten)?|kota)\s+(adm\.?\s+)?", "", value)
    first, _, rest = value.partition(" ")
    if first in DIRECTIONS:
        value = rest + " " + DIRECTIONS[first]
    if value.endswith(" islands"):
        value = "kepulauan " + value.removesuffix(" islands")
    value = re.sub(r"\bjava\b", "jawa", value)
    value = re.sub(r"\bsumatra\b", "sumatera", value)
    return re.sub(r"[^a-z0-9]", "", value)


def hits(polygons, points, key, predicate):
    joined = gpd.sjoin(polygons[[key, "geometry"]].to_crs(points.crs), points,
                       how="inner", predicate=predicate)
    return joined.groupby("event_id_cnty")[key].agg(lambda s: "|".join(sorted(set(s.astype(str)))))


def matches_central_jakarta(row):
    alias = CENTRAL_JAKARTA
    if (str(row.admin1).strip().casefold() != alias["admin1"].casefold()
            or str(row.admin2).strip().casefold() != alias["admin2"].casefold()
            or row.interior != alias["bps"]):
        return False
    value = str(getattr(row, "event_date", "")).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        date = pd.to_datetime(value, format="%Y-%m-%d", errors="coerce")
    else:
        date = pd.to_datetime(value, format="mixed", dayfirst=True, errors="coerce")
    return pd.notna(date) and alias["valid_from"] <= date.date().isoformat() <= alias["valid_through"]


def allocate(events, master, districts, before, exceptions, masks):
    events = events.copy().set_index("event_id_cnty")
    if not events.index.is_unique:
        raise ValueError("ID duplikat")
    if events.index.isna().any() or (events.index.astype(str).str.strip() == "").any():
        raise ValueError("ID kosong")
    x = pd.to_numeric(events.longitude, errors="coerce")
    y = pd.to_numeric(events.latitude, errors="coerce")
    if not (x.between(-180, 180) & y.between(-90, 90)).fillna(False).all():
        raise ValueError("Koordinat berbeda dari kondisi audit")
    points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), index=events.index, crs=4326)
    for field, polygons, key, predicate in [
        ("candidates", districts, "bps_kabkota", "intersects"),
        ("interior", districts, "bps_kabkota", "contains"),
        ("before_candidates", before, "bps_kabkota", "intersects"),
        ("before_interior", before, "bps_kabkota", "contains"),
        ("exception_ids", exceptions, "source_fid", "intersects"),
        ("mask_codes", masks, "bps_kabkota", "intersects")]:
        events[field] = hits(polygons, points, key, predicate).astype("string").reindex(events.index).fillna("")
    lookup = {}
    for r in master.itertuples():
        lookup.setdefault((label(r.nama_provinsi, True), label(r.nama_kabkota)), []).append(r.bps_kabkota)
    decisions = []
    for r in events.itertuples():
        reasons = []
        if "|" in r.candidates:
            reasons.append("multiple")
        if not r.candidates:
            reasons.append("outside")
        if set(r.candidates.split("|")) - set(r.interior.split("|")):
            reasons.append("boundary")
        if r.exception_ids:
            reasons.append("exception")
        if r.mask_codes:
            reasons.append("mask")
        if (r.before_candidates, r.before_interior) != (r.candidates, r.interior):
            reasons.append("quarantine_change")
        spatial_ok = not reasons
        if pd.isna(r.admin2) or not str(r.admin2).strip():
            reasons.append("missing_admin2")
        unspecified = str(r.location).strip().casefold() == "jakarta - unspecified"
        if unspecified:
            reasons.append("jakarta_unspecified")
        if str(r.geo_precision) != "1":
            reasons.append("precision")
        codes = lookup.get((label(r.admin1, True), label(r.admin2)), [])
        if not codes:
            reasons.append("unverified_label")
        elif len(codes) > 1:
            reasons.append("ambiguous_label")
        elif r.interior and "|" not in r.interior and codes[0] != r.interior:
            reasons.append("label_disagreement")
        # Only a solitary label flag may be resolved. All independent vetoes survive.
        if not reasons:
            rule = "unique_label"
        elif reasons == ["ambiguous_label"] and r.interior in codes:
            rule = "label_set_contains_interior"
        elif reasons == ["unverified_label"] and matches_central_jakarta(r):
            rule = "alias_central_jakarta"
        elif spatial_ok and not unspecified:
            rule = "spatial_candidate_only"
        else:
            rule = "excluded"
        decisions.append((rule, "|".join(reasons), "|".join(sorted(codes))))
    fields = ["allocation_rule", "reasons", "label_codes"]
    events[fields] = pd.DataFrame(decisions, index=events.index, columns=fields)
    events["policy_version"] = VERSION
    result = master.copy().set_index("bps_kabkota")
    if not result.index.is_unique:
        raise ValueError("Kode master duplikat")
    accepted = events.allocation_rule.eq("unique_label")
    additions = {"ambiguity_resolved": "label_set_contains_interior",
                 "enhanced": "alias_central_jakarta", "permissive": "spatial_candidate_only"}
    for policy in POLICIES:
        if policy in additions:
            accepted = accepted | events.allocation_rule.eq(additions[policy])
        events[f"bps_{policy}"] = events.interior.where(accepted)
        status = pd.Series("review", index=events.index)
        status.loc[events.allocation_rule.eq("excluded")] = "unallocated"
        status.loc[accepted] = "allocated"
        events[f"status_{policy}"] = status
        counts = events[f"bps_{policy}"].value_counts()
        if not counts.index.isin(result.index).all():
            raise ValueError("Kode hasil tidak ada di master")
        result[f"y_{policy}"] = counts.reindex(result.index, fill_value=0)
        if result[f"y_{policy}"].sum() != accepted.sum():
            raise ValueError("Rekonsiliasi gagal")
    events["status"] = events[f"status_{PRIMARY}"]
    events["allocated_bps"] = events[f"bps_{PRIMARY}"]
    events["candidate_bps"] = events.bps_permissive
    result["protest_count"] = result[f"y_{PRIMARY}"]
    result["candidate_count"] = result.y_permissive
    result["promoted_ambiguity"] = result.y_ambiguity_resolved - result.y_conservative
    result["promoted_alias"] = result.y_enhanced - result.y_ambiguity_resolved
    result["candidate_only"] = result.y_permissive - result.y_enhanced
    return events.reset_index(), result.reset_index()


def checked(path, expected):
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream,"sha256").hexdigest()
    if expected != actual:
        raise ValueError(f"SHA-256 berbeda: {path.name}")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--event-type", action="append")
    args = parser.parse_args()
    categories = sorted(set(args.event_type or ["Protests"]))
    raw, digest = load_acled(args.input)
    baseline = json.loads((ROOT/"data/interim/acled_audit/audit_summary.json").read_text())
    if digest != baseline["sha256"]:
        raise ValueError("Ekstrak berbeda dari audit ACLED")
    events = clean_fields(raw)
    events = events.loc[events.event_type.isin(categories)].copy()
    expected = sum(baseline["event_type_counts"][c] for c in categories)
    if len(events) != expected:
        raise ValueError("Jumlah kejadian berbeda dari audit")
    events["geo_precision"] = precision_labels(events.geo_precision)
    analysis = BIG/"kabkota_analysis.gpkg"
    pre = BIG/"kabkota_bps.gpkg"
    report = json.loads((BIG/"analysis_validation.json").read_text())
    if not report["passed"]:
        raise ValueError("Batas belum lolos validasi")
    provenance = json.loads((BPS/"provenance.json").read_text())
    hashes = {"acled":digest, "boundaries":checked(analysis,report["sha256"]),
              "before":checked(pre,json.loads((BIG/"validation.json").read_text())["gpkg_sha256"]),
              "master":checked(BPS/"master.csv",provenance["master_sha256"]),
              "provinces":checked(BPS/"provinces.json",provenance["raw"]["provinces.json"]["sha256"])}
    master = pd.read_csv(BPS/"master.csv",dtype=str).rename(columns={"kode_bps":"bps_kabkota","nama_bps":"nama_kabkota"})
    provinces = {r["kode_bps"]:r["nama_bps"] for r in json.loads((BPS/"provinces.json").read_text())}
    master["nama_provinsi"] = master.bps_provinsi.map(provinces)
    if len(master)!=514 or master.nama_provinsi.isna().any() or master.bps_provinsi.nunique()!=38:
        raise ValueError("Master tidak lengkap")
    ledger, table = allocate(events,master[["bps_kabkota","bps_provinsi","nama_kabkota","nama_provinsi"]],
                             load_boundaries(analysis,layer="kabkota"),load_boundaries(pre,layer="kabkota"),
                             load_boundaries(analysis,layer="unresolved_features"),load_boundaries(analysis,layer="sliver_review"))
    if categories != ["Protests"]:
        table = table.rename(columns={"protest_count":"event_count"})
    counts = table[f"y_{PRIMARY}"]
    scenarios = {}
    for policy in POLICIES:
        y = table[f"y_{policy}"]
        scenarios[policy] = dict(total=int(y.sum()), zeros=int(y.eq(0).sum()),
                                 status=ledger[f"status_{policy}"].value_counts().to_dict(),
                                 mean=y.mean(), variance_population=y.var(ddof=0))
    summary = dict(version=VERSION, primary_policy=PRIMARY, policies=scenarios, alias=CENTRAL_JAKARTA,
                   allocation_rules=ledger.allocation_rule.value_counts().to_dict(),
                   hashes=hashes,categories=categories,events=len(ledger),regions=len(table),
                   status=ledger.status.value_counts().to_dict(),allocated=int(counts.sum()),
                   outstanding=int(len(ledger)-counts.sum()),candidate_total=int(table.candidate_count.sum()),
                   reasons=ledger.reasons.str.split("|",regex=False).explode().replace("",pd.NA).value_counts().to_dict(),
                   mean=counts.mean(),variance_population=counts.var(ddof=0),median=counts.median(),
                   minimum=int(counts.min()),maximum=int(counts.max()),zeros=int(counts.eq(0).sum()))
    out = ROOT/"data/processed/spatial_allocation"/VERSION/"_".join(categories)
    out.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / "outputs"
        stage.mkdir()
        table.to_csv(stage/"regional_counts.csv",index=False)
        ledger.to_csv(stage/"allocations.csv",index=False)
        ledger.loc[ledger.status!="allocated"].to_csv(stage/"review.csv",index=False)
        (stage/"reconciliation.json").write_text(json.dumps(summary,indent=2),encoding="utf8")
        if out.exists():
            if ({p.name for p in stage.iterdir()} != {p.name for p in out.iterdir()}
                    or any(p.read_bytes() != (out/p.name).read_bytes() for p in stage.iterdir())):
                raise ValueError(f"Hasil {VERSION} berbeda dari arsip {out}. Gunakan versi baru.")
        else:
            stage.rename(out)
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
