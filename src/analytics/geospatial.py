"""Geospatial distance helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def add_nearest_poi_distance(candidates: pd.DataFrame, pois: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    if out.empty or pois.empty:
        out["distance_km"] = np.nan
        out["target_poi"] = None
        return out

    distances = []
    poi_names = []
    for _, row in out.iterrows():
        values = haversine_km(
            row["latitude"],
            row["longitude"],
            pois["latitude"].to_numpy(),
            pois["longitude"].to_numpy(),
        )
        idx = int(np.argmin(values))
        distances.append(float(values[idx]))
        poi_names.append(str(pois.iloc[idx]["poi_name"]))
    out["distance_km"] = distances
    out["target_poi"] = poi_names
    return out
