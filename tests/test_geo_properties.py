"""Hypothesis property-based tests for aeolus.geo module."""

import math

import pytest
from hypothesis import given, assume
from hypothesis import strategies as st

from aeolus.geo import EARTH_RADIUS_KM, haversine_distance, near_to_bbox
from conftest_strategies import latitudes, longitudes, positive_radii

pytestmark = pytest.mark.property


class TestHaversineProperties:
    """Property-based tests for haversine_distance."""

    @given(lat=latitudes, lon=longitudes)
    def test_same_point_is_zero(self, lat, lon):
        """d(p, p) = 0 for any point."""
        assert haversine_distance(lat, lon, lat, lon) == 0.0

    @given(lat1=latitudes, lon1=longitudes, lat2=latitudes, lon2=longitudes)
    def test_non_negative(self, lat1, lon1, lat2, lon2):
        """Distance is always >= 0."""
        assert haversine_distance(lat1, lon1, lat2, lon2) >= 0.0

    @given(lat1=latitudes, lon1=longitudes, lat2=latitudes, lon2=longitudes)
    def test_symmetry(self, lat1, lon1, lat2, lon2):
        """d(a, b) = d(b, a)."""
        d_ab = haversine_distance(lat1, lon1, lat2, lon2)
        d_ba = haversine_distance(lat2, lon2, lat1, lon1)
        assert math.isclose(d_ab, d_ba, rel_tol=1e-9, abs_tol=1e-12)

    @given(lat1=latitudes, lon1=longitudes, lat2=latitudes, lon2=longitudes)
    def test_bounded_by_half_circumference(self, lat1, lon1, lat2, lon2):
        """No distance exceeds pi * EARTH_RADIUS_KM (half circumference)."""
        d = haversine_distance(lat1, lon1, lat2, lon2)
        assert d <= math.pi * EARTH_RADIUS_KM + 1e-6

    @given(
        lat1=latitudes, lon1=longitudes,
        lat2=latitudes, lon2=longitudes,
        lat3=latitudes, lon3=longitudes,
    )
    def test_triangle_inequality(self, lat1, lon1, lat2, lon2, lat3, lon3):
        """d(a, c) <= d(a, b) + d(b, c)."""
        d_ac = haversine_distance(lat1, lon1, lat3, lon3)
        d_ab = haversine_distance(lat1, lon1, lat2, lon2)
        d_bc = haversine_distance(lat2, lon2, lat3, lon3)
        assert d_ac <= d_ab + d_bc + 1e-6


class TestNearToBboxProperties:
    """Property-based tests for near_to_bbox."""

    @given(lat=latitudes, lon=longitudes, radius=positive_radii)
    def test_bbox_ordering(self, lat, lon, radius):
        """min < max for both lat and lon axes."""
        assume(abs(lat) < 89.9)
        min_lon, min_lat, max_lon, max_lat = near_to_bbox(lat, lon, radius)
        assert min_lat < max_lat
        assert min_lon < max_lon

    @given(lat=latitudes, lon=longitudes, radius=positive_radii)
    def test_centred_on_input(self, lat, lon, radius):
        """Bbox midpoint equals input point."""
        assume(abs(lat) < 89.9)
        min_lon, min_lat, max_lon, max_lat = near_to_bbox(lat, lon, radius)
        mid_lat = (min_lat + max_lat) / 2
        mid_lon = (min_lon + max_lon) / 2
        assert math.isclose(mid_lat, lat, abs_tol=1e-9)
        assert math.isclose(mid_lon, lon, abs_tol=1e-9)

    @given(lat=latitudes, lon=longitudes, radius=positive_radii)
    def test_edge_midpoints_reach_radius(self, lat, lon, radius):
        """North edge is approximately radius_km from centre."""
        assume(radius > 1.0)
        assume(abs(lat) < 89.0)
        _, min_lat, _, max_lat = near_to_bbox(lat, lon, radius)
        north_edge_dist = haversine_distance(lat, lon, max_lat, lon)
        assert math.isclose(north_edge_dist, radius, rel_tol=0.02)

    @given(lat=latitudes, lon=longitudes, r1=positive_radii, r2=positive_radii)
    def test_larger_radius_gives_larger_bbox(self, lat, lon, r1, r2):
        """Increasing radius never shrinks bbox."""
        assume(abs(lat) < 89.9)
        assume(r1 < r2)
        min_lon1, min_lat1, max_lon1, max_lat1 = near_to_bbox(lat, lon, r1)
        min_lon2, min_lat2, max_lon2, max_lat2 = near_to_bbox(lat, lon, r2)
        assert min_lon2 <= min_lon1
        assert min_lat2 <= min_lat1
        assert max_lon2 >= max_lon1
        assert max_lat2 >= max_lat1

    @given(
        lat=st.floats(min_value=70.0, max_value=89.0, allow_nan=False, allow_infinity=False),
        lon=longitudes,
        radius=positive_radii,
    )
    def test_high_latitude_lon_stretch(self, lat, lon, radius):
        """At high latitudes the longitude span exceeds the latitude span."""
        min_lon, min_lat, max_lon, max_lat = near_to_bbox(lat, lon, radius)
        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        assert lon_span > lat_span

    @given(
        lat=st.floats(min_value=89.0, max_value=89.99, allow_nan=False, allow_infinity=False),
        lon=longitudes,
        radius=positive_radii,
    )
    def test_bbox_does_not_crash_near_poles(self, lat, lon, radius):
        """near_to_bbox returns four finite floats near the poles."""
        result = near_to_bbox(lat, lon, radius)
        assert len(result) == 4
        for component in result:
            assert isinstance(component, float)
            assert math.isfinite(component)
