"""Quality checks adapted from the team's original audit_acled.py."""
import pandas as pd


REQUIRED = (
    "event_id_cnty", "event_date", "country", "event_type", "admin1",
    "admin2", "location", "latitude", "longitude", "geo_precision",
)


def clean_fields(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan: {', '.join(missing)}")
    fields = list(REQUIRED) + [c for c in ("time_precision", "sub_event_type") if c in frame]
    data = frame[fields].copy()
    for column in fields:
        data[column] = data[column].str.strip().replace("", pd.NA)
    return data


def counts(series: pd.Series) -> dict[str, int]:
    return series.fillna("<MISSING>").value_counts().sort_index().to_dict()


def precision_labels(series: pd.Series) -> pd.Series:
    # Keep malformed precision codes visible and comparable across CSV dtypes.
    return series.str.replace(r"^([123])\.0+$", r"\1", regex=True)


def inspect_records(data: pd.DataFrame) -> tuple[dict, pd.Series]:
    # ISO dates stay year-first. Numeric non-ISO dates use day/month/year.
    dates = data["event_date"]
    iso = dates.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
    parsed = pd.to_datetime(dates.where(iso), format="%Y-%m-%d", errors="coerce")
    parsed = parsed.fillna(pd.to_datetime(dates.mask(iso), format="mixed",
                                          dayfirst=True, errors="coerce"))
    ids = data["event_id_cnty"]
    duplicates = ids.notna() & ids.duplicated(keep=False)
    lat = pd.to_numeric(data["latitude"], errors="coerce")
    lon = pd.to_numeric(data["longitude"], errors="coerce")
    valid = (lat.between(-90, 90) & lon.between(-180, 180)).fillna(False)
    return {
        "records": len(data),
        "min_date": parsed.min().date().isoformat() if parsed.notna().any() else None,
        "max_date": parsed.max().date().isoformat() if parsed.notna().any() else None,
        "unparseable_dates": int(parsed.isna().sum()),
        "dates_outside_project_period": int((parsed.notna() &
            ~parsed.between("2024-10-20", "2025-11-16")).sum()),
        "country_counts": counts(data["country"]),
        "event_type_counts": counts(data["event_type"]),
        "sub_event_type_counts": counts(data["sub_event_type"]) if "sub_event_type" in data else {},
        "missing_event_id_rows": int(ids.isna().sum()),
        "duplicated_event_id_rows": int(duplicates.sum()),
        "missing_or_duplicated_event_ids_rows": int((ids.isna() | duplicates).sum()),
        "missing_latitude": int(data["latitude"].isna().sum()),
        "missing_longitude": int(data["longitude"].isna().sum()),
        "invalid_coordinate_rows": int((~valid).sum()),
        "missing_admin1": int(data["admin1"].isna().sum()),
        "missing_admin2_all_types": int(data["admin2"].isna().sum()),
        "geo_precision_all": counts(precision_labels(data["geo_precision"])),
        "time_precision_all": counts(precision_labels(data["time_precision"])) if "time_precision" in data else {},
        "distinct_admin1_labels": int(data["admin1"].nunique()),
    }, ~valid
