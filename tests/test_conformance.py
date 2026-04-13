"""Live conformance tests for all aeolus data sources.

These tests hit real APIs and validate that downloaded data conforms to the
aeolus standard schema, has plausible values, and survives normalisation
pipelines.  They are gated behind ``@pytest.mark.conformance`` and should be
run before releases, not on every CI push.

Run with::

    pytest tests/test_conformance.py -m conformance --no-cov -x
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

import aeolus
from conformance_helpers import run_data_conformance, run_metadata_conformance

pytestmark = pytest.mark.conformance

# ---------------------------------------------------------------------------
# Shared time windows
# ---------------------------------------------------------------------------
_END = datetime.now(tz=timezone.utc)
_START = _END - timedelta(hours=48)
_SPARSE_START = _END - timedelta(days=14)
_SPARSE_END = _END


# ============================================================================
# UK Regulatory (free, no API key)
# ============================================================================


@pytest.mark.conformance
class TestAURN:
    def test_metadata(self):
        sites = aeolus.find_sites("AURN")
        assert len(sites) > 100, f"Expected >100 AURN sites, got {len(sites)}"
        run_metadata_conformance(sites, "AURN")

    def test_download(self):
        data = aeolus.download("AURN", ["MY1", "KC1"], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "AURN")

    def test_source_network_label(self):
        data = aeolus.download("AURN", ["MY1"], start_date=_START, end_date=_END)
        if not data.empty:
            assert (data["source_network"] == "AURN").all(), (
                f"Expected source_network='AURN', got {data['source_network'].unique()}"
            )

    def test_get_current(self):
        current = aeolus.get_current("AURN", sites=["MY1"])
        if not current.empty:
            run_data_conformance(current, "AURN-SOS")


@pytest.mark.conformance
class TestSAQN:
    def test_metadata(self):
        sites = aeolus.find_sites("SAQN")
        assert len(sites) > 20, f"Expected >20 SAQN sites, got {len(sites)}"
        run_metadata_conformance(sites, "SAQN")

    def test_download(self):
        data = aeolus.download("SAQN", ["ED3"], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "SAQN")


@pytest.mark.conformance
class TestWAQN:
    def test_metadata(self):
        sites = aeolus.find_sites("WAQN")
        assert len(sites) > 5, f"Expected >5 WAQN sites, got {len(sites)}"
        run_metadata_conformance(sites, "WAQN")

    def test_download(self):
        sites = aeolus.find_sites("WAQN")
        site = sites["site_code"].iloc[0]
        data = aeolus.download("WAQN", [site], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "WAQN")


@pytest.mark.conformance
class TestNI:
    def test_metadata(self):
        sites = aeolus.find_sites("NI")
        assert len(sites) > 5, f"Expected >5 NI sites, got {len(sites)}"
        run_metadata_conformance(sites, "NI")

    def test_download(self):
        sites = aeolus.find_sites("NI")
        site = sites["site_code"].iloc[0]
        data = aeolus.download("NI", [site], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "NI")


@pytest.mark.conformance
class TestAQE:
    def test_metadata(self):
        sites = aeolus.find_sites("AQE")
        assert len(sites) > 30, f"Expected >30 AQE sites, got {len(sites)}"
        run_metadata_conformance(sites, "AQE")

    def test_download(self):
        sites = aeolus.find_sites("AQE")
        site = sites["site_code"].iloc[0]
        data = aeolus.download("AQE", [site], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "AQE")


@pytest.mark.conformance
class TestLAQN:
    def test_metadata(self):
        sites = aeolus.find_sites("LAQN")
        assert len(sites) > 200, f"Expected >200 LAQN sites, got {len(sites)}"
        run_metadata_conformance(sites, "LAQN")

    def test_download(self):
        data = aeolus.download("LAQN", ["MY1", "KC1"], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "LAQN")

    def test_co_units(self):
        """CO should be labelled mg/m3."""
        data = aeolus.download("LAQN", ["KC1"], start_date=_START, end_date=_END)
        co = data[data["measurand"] == "CO"]
        if not co.empty:
            assert (co["units"] == "mg/m3").all(), (
                f"Expected CO units='mg/m3', got {co['units'].unique()}"
            )


# ============================================================================
# International free (no API key)
# ============================================================================


@pytest.mark.conformance
class TestEEA:
    def test_metadata(self):
        sites = aeolus.find_sites("EEA", country="IE")
        assert len(sites) > 10, f"Expected >10 EEA IE sites, got {len(sites)}"
        run_metadata_conformance(sites, "EEA")

    def test_download(self):
        data = aeolus.download(
            "EEA", ["STA-IE0028A"],
            start_date=_SPARSE_START, end_date=_SPARSE_END,
        )
        if not data.empty:
            run_data_conformance(data, "EEA")


@pytest.mark.conformance
class TestSonitus:
    def test_metadata(self):
        sites = aeolus.find_sites("SONITUS")
        assert len(sites) > 5, f"Expected >5 Sonitus sites, got {len(sites)}"
        run_metadata_conformance(sites, "SONITUS")

    def test_download(self):
        sites = aeolus.find_sites("SONITUS")
        site = sites["site_code"].iloc[0]
        data = aeolus.download("SONITUS", [site], start_date=_START, end_date=_END)
        if not data.empty:
            run_data_conformance(data, "SONITUS")


@pytest.mark.conformance
class TestSensorCommunity:
    # Wider bbox — Sensor.Community coverage varies; narrow areas may be empty
    _BBOX = (-0.5, 51.3, 0.2, 51.7)  # Greater London

    def test_metadata(self):
        sites = aeolus.find_sites("SENSOR_COMMUNITY", bbox=self._BBOX)
        if sites.empty:
            pytest.skip("No Sensor.Community sites found in bbox (API may be down)")
        run_metadata_conformance(sites, "SENSOR_COMMUNITY")

    def test_download(self):
        sites = aeolus.find_sites("SENSOR_COMMUNITY", bbox=self._BBOX)
        if sites.empty:
            pytest.skip("No Sensor.Community sites found in bbox")
        site = sites["site_code"].iloc[0]
        data = aeolus.download(
            "SENSOR_COMMUNITY", [site], start_date=_START, end_date=_END,
        )
        if not data.empty:
            run_data_conformance(data, "SENSOR_COMMUNITY")


@pytest.mark.conformance
class TestAirNow:
    def test_metadata(self):
        sites = aeolus.find_sites(
            "AIRNOW", bbox=(-77.1, 38.85, -76.9, 38.95),
        )
        assert len(sites) > 0, "Expected >0 AirNow sites in DC bbox"
        run_metadata_conformance(sites, "AIRNOW")

    def test_download(self):
        sites = aeolus.find_sites(
            "AIRNOW", bbox=(-77.1, 38.85, -76.9, 38.95),
        )
        site = sites["site_code"].iloc[0]
        data = aeolus.download(
            "AIRNOW", [site], start_date=_START, end_date=_END,
        )
        if not data.empty:
            run_data_conformance(data, "AIRNOW")


# ============================================================================
# API key sources (skipped when key is absent)
# ============================================================================


@pytest.mark.conformance
class TestBreatheLondon:
    @pytest.fixture(autouse=True)
    def _require_key(self):
        if not os.environ.get("BL_API_KEY"):
            pytest.skip("BL_API_KEY not set")

    def test_metadata(self):
        sites = aeolus.find_sites("BREATHE_LONDON")
        assert len(sites) > 50, f"Expected >50 BL sites, got {len(sites)}"
        run_metadata_conformance(sites, "BREATHE_LONDON")

    def test_download(self):
        sites = aeolus.find_sites("BREATHE_LONDON")
        site = sites["site_code"].iloc[0]
        data = aeolus.download(
            "BREATHE_LONDON", [site], start_date=_START, end_date=_END,
        )
        if not data.empty:
            run_data_conformance(data, "BREATHE_LONDON")


@pytest.mark.conformance
class TestAirQo:
    @pytest.fixture(autouse=True)
    def _require_key(self):
        if not os.environ.get("AIRQO_API_KEY"):
            pytest.skip("AIRQO_API_KEY not set")

    def test_metadata(self):
        sites = aeolus.find_sites("AIRQO")
        assert len(sites) > 50, f"Expected >50 AirQo sites, got {len(sites)}"
        run_metadata_conformance(sites, "AIRQO")

    def test_download(self):
        sites = aeolus.find_sites("AIRQO")
        site = sites["site_code"].iloc[0]
        data = aeolus.download(
            "AIRQO", [site],
            start_date=_SPARSE_START, end_date=_SPARSE_END,
        )
        if not data.empty:
            run_data_conformance(data, "AIRQO")


@pytest.mark.conformance
class TestOpenAQ:
    @pytest.fixture(autouse=True)
    def _require_key(self):
        if not os.environ.get("OPENAQ_API_KEY"):
            pytest.skip("OPENAQ_API_KEY not set")

    def test_metadata(self):
        try:
            sites = aeolus.find_sites(
                "OPENAQ", bbox=(-0.3, 51.4, 0.1, 51.6),
            )
        except Exception as e:
            pytest.skip(f"OpenAQ API unreachable: {e}")
        if sites.empty:
            pytest.skip("No OpenAQ sites found in bbox (API may be down)")
        run_metadata_conformance(sites, "OPENAQ")

    def test_download(self):
        try:
            sites = aeolus.find_sites(
                "OPENAQ", bbox=(-0.3, 51.4, 0.1, 51.6),
            )
        except Exception as e:
            pytest.skip(f"OpenAQ API unreachable: {e}")
        if sites.empty:
            pytest.skip("No OpenAQ sites found in bbox")
        site = sites["site_code"].iloc[0]
        data = aeolus.download(
            "OPENAQ", [site],
            start_date=_SPARSE_START, end_date=_SPARSE_END,
        )
        if not data.empty:
            run_data_conformance(data, "OPENAQ")


@pytest.mark.conformance
class TestPurpleAir:
    @pytest.fixture(autouse=True)
    def _require_key(self):
        if not os.environ.get("PURPLEAIR_API_KEY"):
            pytest.skip("PURPLEAIR_API_KEY not set")

    def test_metadata(self):
        sites = aeolus.find_sites(
            "PURPLEAIR", bbox=(-0.15, 51.49, -0.05, 51.53),
        )
        assert len(sites) > 0, "Expected >0 PurpleAir sites in London bbox"
        run_metadata_conformance(sites, "PURPLEAIR")

    def test_download(self):
        sites = aeolus.find_sites(
            "PURPLEAIR", bbox=(-0.15, 51.49, -0.05, 51.53),
        )
        site = sites["site_code"].iloc[0]
        data = aeolus.download(
            "PURPLEAIR", [site],
            start_date=_SPARSE_START, end_date=_SPARSE_END,
        )
        if not data.empty:
            run_data_conformance(data, "PURPLEAIR")


# ============================================================================
# Cross-source tests
# ============================================================================


@pytest.mark.conformance
class TestCrossSource:
    def test_find_sites_all_free(self):
        sites = aeolus.find_sites(near=(51.5074, -0.1278), radius_km=10)
        assert len(sites) > 0, "Expected >0 sites from find_sites(near=London)"
        run_metadata_conformance(sites, "multi-source")
        networks = sites["source_network"].nunique()
        assert networks >= 2, (
            f"Expected >=2 unique networks near London, got {networks}"
        )

    def test_multi_source_download(self):
        data = aeolus.download(
            {"AURN": ["MY1"], "SAQN": ["ED3"]},
            start_date=_START, end_date=_END,
        )
        if not data.empty:
            run_data_conformance(data, "multi-source")

    def test_summarise_multi_source(self):
        data = aeolus.download(
            {"AURN": ["MY1"], "SAQN": ["ED3"]},
            start_date=_START, end_date=_END,
        )
        if not data.empty:
            summary = aeolus.summarise(data)
            assert (summary["data_capture"] >= 0).all(), (
                "Negative data_capture in summarise output"
            )
