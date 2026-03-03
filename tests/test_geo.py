"""Tests for geospatial utilities (geo.py).

Pure math tests — no mocking or external dependencies required.
"""

import math

import pytest

from aeolus.geo import haversine_distance, near_to_bbox


# ============================================================================
# haversine_distance tests
# ============================================================================


def test_same_point_returns_zero():
    """Distance from a point to itself is 0 km."""
    assert haversine_distance(51.5, -0.1, 51.5, -0.1) == 0.0


def test_london_to_paris():
    """London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 340 km."""
    dist = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
    assert abs(dist - 340) < 5


def test_equator_symmetry():
    """Points equidistant east and west of origin give same distance."""
    d1 = haversine_distance(0.0, 0.0, 0.0, 1.0)
    d2 = haversine_distance(0.0, 0.0, 0.0, -1.0)
    assert abs(d1 - d2) < 0.01


def test_antipodal_points():
    """Points on opposite sides of the Earth ≈ 20015 km."""
    dist = haversine_distance(0.0, 0.0, 0.0, 180.0)
    assert abs(dist - 20015) < 10


def test_north_south_distance():
    """One degree of latitude ≈ 111 km."""
    dist = haversine_distance(0.0, 0.0, 1.0, 0.0)
    assert abs(dist - 111) < 1


# ============================================================================
# near_to_bbox tests
# ============================================================================


def test_equator_bbox_roughly_equal_deltas():
    """At the equator, lat and lon deltas should be roughly equal."""
    min_lon, min_lat, max_lon, max_lat = near_to_bbox(0.0, 0.0, 100.0)
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    assert abs(lat_span - lon_span) < 0.1


def test_high_latitude_wider_longitude():
    """At 60°N, the longitude delta should be roughly double the latitude delta."""
    min_lon, min_lat, max_lon, max_lat = near_to_bbox(60.0, 0.0, 100.0)
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    # cos(60°) = 0.5, so lon_delta ≈ 2 × lat_delta
    assert lon_span > lat_span * 1.8


def test_bbox_centred_on_point():
    """The bbox should be centred on the input point."""
    lat, lon, radius = 51.5, -0.1, 50.0
    min_lon, min_lat, max_lon, max_lat = near_to_bbox(lat, lon, radius)
    centre_lat = (min_lat + max_lat) / 2
    centre_lon = (min_lon + max_lon) / 2
    assert abs(centre_lat - lat) < 0.001
    assert abs(centre_lon - lon) < 0.001


def test_bbox_contains_radius():
    """All corners of the bbox should be at least radius_km from the centre."""
    lat, lon, radius = 51.5, -0.1, 50.0
    min_lon, min_lat, max_lon, max_lat = near_to_bbox(lat, lon, radius)
    # The edge midpoints should be close to radius_km
    north_dist = haversine_distance(lat, lon, max_lat, lon)
    east_dist = haversine_distance(lat, lon, lat, max_lon)
    assert north_dist >= radius * 0.95
    assert east_dist >= radius * 0.95


def test_bbox_ordering():
    """min values should be less than max values."""
    min_lon, min_lat, max_lon, max_lat = near_to_bbox(51.5, -0.1, 50.0)
    assert min_lon < max_lon
    assert min_lat < max_lat
