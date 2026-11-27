"""Read-only checks for a national BIG polygon layer and a BPS code master."""
from pathlib import Path

import geopandas as gpd
import pyogrio
from pyproj import CRS


def load_boundaries(path: Path, *, layer: str | None = None) -> gpd.GeoDataFrame:
    layers = [name for name, kind in pyogrio.list_layers(path) if kind is not None]
    if layer is None:
        if len(layers) != 1:
            raise ValueError(f"Pilih satu layer spasial: {layers}")
        layer = layers[0]
    if layer not in layers:
        raise ValueError(f"Layer spasial tidak ditemukan: {layer}")
    return gpd.read_file(path, layer=layer, engine="pyogrio")


def standardize_boundaries(frame, *, district="KDBBPS", province="KDPBPS"):
    """Preserve original attributes. Never infer or pad codes from names."""
    result = frame.copy()
    for source, target in [(province, "bps_provinsi"), (district, "bps_kabkota")]:
        value = frame[source].astype("string").str.strip()
        result[target] = value.mask(value.eq(""))
    return result


def validate_boundaries(frame, master, *, expected_count=514, expected_provinces=38):
    """master maps full four-digit BPS district codes to two-digit parent codes."""
    if (len(master) != expected_count or len(set(master.values())) != expected_provinces
            or any(len(k) != 4 or not k.isascii() or not k.isdigit() or k[:2] != v
                   for k, v in master.items())):
        raise ValueError("Master BPS tidak konsisten dengan cakupan yang diminta.")
    data = frame.reset_index(drop=True)
    codes = data["bps_kabkota"]
    observed = set(codes.dropna())
    geom = data.geometry
    valid = ~geom.is_empty & geom.is_valid & geom.geom_type.isin(["Polygon", "MultiPolygon"])
    report = {
        "features": len(data), "unique_codes": len(observed),
        "blank_code_rows": data.index[codes.isna()].tolist(),
        "duplicate_codes": sorted(set(codes[codes.duplicated(keep=False)].dropna())),
        "missing_codes": sorted(set(master) - observed), "extra_codes": sorted(observed - set(master)),
        "parent_mismatch_rows": data.index[~data["bps_provinsi"].eq(codes.map(master)).fillna(False)].tolist(),
        "invalid_geometry_rows": data.index[~valid].tolist(),
        "crs": str(data.crs) if data.crs else None,
        "extent_wgs84": None, "extent_plausible": False,
        "overlap_m2": [], "overlap_checked": False,
    }
    if data.crs and valid.all() and len(data):
        bounds = geom.to_crs(4326).total_bounds.tolist()
        report["extent_wgs84"] = bounds
        west, south, east, north = bounds
        # Broad Indonesian land envelope; a sanity check, not a coverage proof.
        report["extent_plausible"] = 94 <= west < east <= 142 and -12 <= south < north <= 7
        # Intersect in native CRS first so shared edges do not become slivers after projection.
        left, right = geom.sindex.query(geom, predicate="intersects")
        for i, j in zip(left, right):
            if i >= j:
                continue
            shared = geom.iloc[i].intersection(geom.iloc[j])
            if shared.area > 0:
                area = gpd.GeoSeries([shared], crs=data.crs).to_crs(CRS.from_epsg(6933)).area.iloc[0]
                report["overlap_m2"].append({"rows": [int(i), int(j)], "area": float(area)})
        report["overlap_checked"] = True
    report["passed"] = (report["extent_plausible"] and report["overlap_checked"] and len(data) == expected_count
                        and not any(report[key] for key in ("blank_code_rows", "duplicate_codes",
                            "missing_codes", "extra_codes", "parent_mismatch_rows",
                            "invalid_geometry_rows", "overlap_m2")))
    return report
