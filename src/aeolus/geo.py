"""Geospatial utilities for Aeolus.

Pure-math helpers for distance calculation and bounding-box conversion.
No external dependencies beyond the standard library.
"""

import math

EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres.

    Args:
        lat1: Latitude of point 1 (decimal degrees).
        lon1: Longitude of point 1 (decimal degrees).
        lat2: Latitude of point 2 (decimal degrees).
        lon2: Longitude of point 2 (decimal degrees).

    Returns:
        Distance in kilometres.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def near_to_bbox(
    lat: float, lon: float, radius_km: float
) -> tuple[float, float, float, float]:
    """Convert a point + radius to a bounding box.

    The result intentionally over-estimates the area so it can be used as a
    pre-filter for portal APIs; precise haversine filtering is applied
    afterwards.

    Args:
        lat: Centre latitude (decimal degrees).
        lon: Centre longitude (decimal degrees).
        radius_km: Radius in kilometres.

    Returns:
        ``(min_lon, min_lat, max_lon, max_lat)`` — GeoJSON/shapely convention.
    """
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return (lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta)
