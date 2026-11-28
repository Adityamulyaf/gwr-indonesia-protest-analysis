"""Provisional frequencies and the protest location review queue."""
import pandas as pd

from .validate import counts, precision_labels


def protest_tables(data: pd.DataFrame, invalid_coords: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protests = data.loc[data["event_type"].eq("Protests")]
    missing_admin2 = protests["admin2"].isna()
    precision = precision_labels(protests["geo_precision"])
    provisional = (protests.loc[~missing_admin2]
                   .groupby(["admin1", "admin2"], dropna=False)
                   .size().reset_index(name="recorded_protests"))
    # Preserve the two original review rules; also catch broken coordinates/admin1.
    flags = pd.DataFrame({
        "missing_admin2": missing_admin2,
        "geo_precision_not_1": precision.fillna("").ne("1"),
        "invalid_coordinates": invalid_coords.loc[protests.index],
        "missing_admin1": protests["admin1"].isna(),
    })
    review_columns = ["event_id_cnty", "event_date", "admin1", "admin2",
                      "location", "latitude", "longitude", "geo_precision"]
    review = protests[review_columns].join(flags).loc[flags.any(axis=1)]
    return provisional, review, {
        "missing_admin2_protests": int(missing_admin2.sum()),
        "geo_precision_protests": counts(precision),
        "protests_geo_precision_2_or_3": int(precision.isin(["2", "3"]).sum()),
        "distinct_protest_admin1_admin2_pairs_with_admin2": len(provisional),
        "protest_counts_mapped_by_labels_provisionally": int(provisional["recorded_protests"].sum()),
        "protest_location_review_rows": len(review),
        "protest_location_review_original_rules": int((flags["missing_admin2"] | flags["geo_precision_not_1"]).sum()),
        "protest_missing_admin2_location_counts": counts(protests.loc[missing_admin2, "location"]),
    }
