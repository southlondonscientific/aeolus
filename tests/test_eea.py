"""Tests for EEA data source."""

import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from aeolus.types import DATA_COLUMNS, METADATA_COLUMNS


@pytest.fixture(autouse=True)
def ensure_source_registered():
    """Ensure EEA source is registered."""
    from aeolus.sources import eea  # noqa: F401


MOCK_ESRI_RESPONSE = {
    "features": [
        {
            "attributes": {
                "AirQualityStationEoICode": "IE0131A",
                "AQStationName": "Dublin Blanchardstown",
                "Country": "Ireland",
                "CountryCode": "IE",
                "PopupInfo": (
                    "<p>PM10</a>, ug/m<sup>3</sup>, (2013 - 2024) </p>"
                    "<p>NO2</a>, ug/m<sup>3</sup>, (2013 - 2024) </p>"
                ),
            },
            "geometry": {"x": -709094.02, "y": 7054644.44},
        },
        {
            "attributes": {
                "AirQualityStationEoICode": "IE007CP",
                "AQStationName": "Limerick Peoples Park",
                "Country": "Ireland",
                "CountryCode": "IE",
                "PopupInfo": "<p>O3</a>, ug/m<sup>3</sup>, (2020 - 2024) </p>",
            },
            "geometry": {"x": -960542.49, "y": 6920096.15},
        },
    ]
}


class TestFetchMetadata:
    @patch("aeolus.sources.eea._call_esri_api")
    def test_returns_standard_metadata_columns(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = MOCK_ESRI_RESPONSE
        df = fetch_eea_metadata(country="IE")

        for col in METADATA_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) == 2
        assert df.iloc[0]["site_code"] == "IE0131A"
        assert df.iloc[0]["source_network"] == "EEA"

    @patch("aeolus.sources.eea._call_esri_api")
    def test_converts_web_mercator_to_wgs84(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = MOCK_ESRI_RESPONSE
        df = fetch_eea_metadata(country="IE")

        assert -7.0 < df.iloc[0]["longitude"] < -6.0
        assert 53.0 < df.iloc[0]["latitude"] < 54.0

    @patch("aeolus.sources.eea._call_esri_api")
    def test_country_filter_passed_to_api(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = {"features": []}
        fetch_eea_metadata(country="DE")

        call_kwargs = mock_api.call_args
        assert "DE" in str(call_kwargs)

    @patch("aeolus.sources.eea._call_esri_api")
    def test_bbox_filter_uses_spatial_query(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = {"features": []}
        fetch_eea_metadata(bbox=(-7.0, 51.0, -6.0, 54.0))

        assert mock_api.called

    @patch("aeolus.sources.eea._call_esri_api")
    def test_no_filters_fetches_all_with_pagination(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        page1 = {"features": [MOCK_ESRI_RESPONSE["features"][0]] * 2000, "exceededTransferLimit": True}
        page2 = {"features": [MOCK_ESRI_RESPONSE["features"][1]] * 500}
        mock_api.side_effect = [page1, page2]

        df = fetch_eea_metadata()
        assert len(df) == 2500
        assert mock_api.call_count == 2

    @patch("aeolus.sources.eea._call_esri_api")
    def test_empty_response_returns_empty_metadata_frame(self, mock_api):
        from aeolus.sources.eea import fetch_eea_metadata

        mock_api.return_value = {"features": []}
        df = fetch_eea_metadata(country="XX")

        assert len(df) == 0
        for col in METADATA_COLUMNS:
            assert col in df.columns


# ============================================================================
# DATA FETCHER AND NORMALISATION TESTS
# ============================================================================


def _make_parquet_zip(records: list[dict], filename: str = "data.parquet") -> bytes:
    """Create a ZIP file containing a Parquet file from the given records."""
    table = pa.table({
        "Samplingpoint": pa.array([r["Samplingpoint"] for r in records], type=pa.string()),
        "Pollutant": pa.array([r["Pollutant"] for r in records], type=pa.int32()),
        "Start": pa.array(
            [pd.Timestamp(r["Start"], tz="UTC") for r in records],
            type=pa.timestamp("us", tz="UTC"),
        ),
        "End": pa.array(
            [pd.Timestamp(r["End"], tz="UTC") for r in records],
            type=pa.timestamp("us", tz="UTC"),
        ),
        "Value": pa.array([r["Value"] for r in records], type=pa.string()),
        "Unit": pa.array([r["Unit"] for r in records], type=pa.string()),
        "AggType": pa.array([r.get("AggType", "hour") for r in records], type=pa.string()),
        "Validity": pa.array([r["Validity"] for r in records], type=pa.int32()),
        "Verification": pa.array([r["Verification"] for r in records], type=pa.int32()),
        "ResultTime": pa.array(
            [pd.Timestamp(r.get("ResultTime", r["End"]), tz="UTC") for r in records],
            type=pa.timestamp("us", tz="UTC"),
        ),
        "DataCapture": pa.array([r.get("DataCapture", 100.0) for r in records], type=pa.float64()),
        "FkObservationLog": pa.array([r.get("FkObservationLog", "") for r in records], type=pa.string()),
    })

    buf = io.BytesIO()
    with ZipFile(buf, "w") as zf:
        parquet_buf = io.BytesIO()
        pq.write_table(table, parquet_buf)
        zf.writestr(filename, parquet_buf.getvalue())
    return buf.getvalue()


MOCK_PARQUET_RECORDS = [
    {
        "Samplingpoint": "IE/SPO.IE.IE0131ASample1_8",
        "Pollutant": 8,
        "Start": "2024-01-01T00:00:00+00:00",
        "End": "2024-01-01T01:00:00+00:00",
        "Value": "25.3",
        "Unit": "ug.m-3",
        "Validity": 1,
        "Verification": 2,
    },
    {
        "Samplingpoint": "IE/SPO.IE.IE0131ASample1_5",
        "Pollutant": 5,
        "Start": "2024-01-01T00:00:00+00:00",
        "End": "2024-01-01T01:00:00+00:00",
        "Value": "42.0",
        "Unit": "ug.m-3",
        "Validity": 1,
        "Verification": 1,
    },
    {
        "Samplingpoint": "IE/SPO.IE.IE0131ASample1_8",
        "Pollutant": 8,
        "Start": "2024-01-01T01:00:00+00:00",
        "End": "2024-01-01T02:00:00+00:00",
        "Value": "10.0",
        "Unit": "ug.m-3",
        "Validity": -1,
        "Verification": 2,
    },
]


MOCK_SPO_MAPPING = {
    "SPO.IE.IE0131ASample1_8": "IE0131A",
    "SPO.IE.IE0131ASample1_5": "IE0131A",
    "SPO.IE.IE007CPSample1_7": "IE007CP",
}


class TestNormaliseEeaData:
    """Test the normalisation pipeline with a mocked SPO mapping."""

    def _raw_df(self, records=None):
        """Build a raw DataFrame from Parquet records via ZIP round-trip."""
        zip_bytes = _make_parquet_zip(records or MOCK_PARQUET_RECORDS)
        buf = io.BytesIO(zip_bytes)
        with ZipFile(buf) as zf:
            dfs = []
            for name in zf.namelist():
                if name.endswith(".parquet"):
                    dfs.append(pd.read_parquet(io.BytesIO(zf.read(name))))
        return pd.concat(dfs, ignore_index=True)

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    def test_standard_columns(self, _mock_mapping):
        from aeolus.sources.eea import normalise_eea_data

        df = normalise_eea_data()(self._raw_df())
        for col in DATA_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df.columns) == len(DATA_COLUMNS)

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    def test_site_code_extraction(self, _mock_mapping):
        from aeolus.sources.eea import normalise_eea_data

        df = normalise_eea_data()(self._raw_df())
        assert all(df["site_code"] == "IE0131A")

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    def test_pollutant_mapping(self, _mock_mapping):
        from aeolus.sources.eea import normalise_eea_data

        df = normalise_eea_data()(self._raw_df())
        assert set(df["measurand"].unique()) == {"NO2", "PM10"}

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    def test_invalid_rows_filtered(self, _mock_mapping):
        from aeolus.sources.eea import normalise_eea_data

        df = normalise_eea_data()(self._raw_df())
        assert len(df) == 2  # Third record has Validity=-1

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    def test_unit_normalisation(self, _mock_mapping):
        from aeolus.sources.eea import normalise_eea_data

        df = normalise_eea_data()(self._raw_df())
        assert all(df["units"] == "ug/m3")

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    def test_verification_to_ratification(self, _mock_mapping):
        from aeolus.sources.eea import normalise_eea_data

        df = normalise_eea_data()(self._raw_df())
        verified = df[df["measurand"] == "NO2"]
        provisional = df[df["measurand"] == "PM10"]
        assert all(verified["ratification"] == "Verified")
        assert all(provisional["ratification"] == "Provisional")


class TestFetchEeaData:
    """Test the data fetcher with mocked airbase client."""

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    @patch("aeolus.sources.eea._get_client")
    def test_standard_columns(self, mock_client, _mock_mapping):
        from aeolus.sources.eea import fetch_eea_data

        # Mock the airbase client to write parquet files to the temp dir
        mock_request = MagicMock()

        def fake_download(dir):
            zip_bytes = _make_parquet_zip(MOCK_PARQUET_RECORDS)
            buf = io.BytesIO(zip_bytes)
            with ZipFile(buf) as zf:
                zf.extractall(dir)

        mock_request.download = fake_download
        mock_client.return_value.request.return_value = mock_request

        df = fetch_eea_data(
            sites=["IE0131A"],
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            country="IE",
        )
        for col in DATA_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) > 0

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    @patch("aeolus.sources.eea._get_client")
    def test_site_filtering(self, mock_client, _mock_mapping):
        from aeolus.sources.eea import fetch_eea_data

        extra_records = MOCK_PARQUET_RECORDS + [
            {
                "Samplingpoint": "IE/SPO.IE.IE007CPSample1_7",
                "Pollutant": 7,
                "Start": "2024-01-01T00:00:00+00:00",
                "End": "2024-01-01T01:00:00+00:00",
                "Value": "60.0",
                "Unit": "ug.m-3",
                "Validity": 1,
                "Verification": 3,
            },
        ]

        mock_request = MagicMock()

        def fake_download(dir):
            zip_bytes = _make_parquet_zip(extra_records)
            buf = io.BytesIO(zip_bytes)
            with ZipFile(buf) as zf:
                zf.extractall(dir)

        mock_request.download = fake_download
        mock_client.return_value.request.return_value = mock_request

        df = fetch_eea_data(
            sites=["IE0131A"],
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            country="IE",
        )
        assert all(df["site_code"] == "IE0131A")

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    @patch("aeolus.sources.eea._get_client")
    def test_empty_download_returns_empty_frame(self, mock_client, _mock_mapping):
        from aeolus.sources.eea import fetch_eea_data

        mock_request = MagicMock()
        mock_request.download = lambda dir: None  # no files written
        mock_client.return_value.request.return_value = mock_request

        df = fetch_eea_data(
            sites=["IE0131A"],
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            country="IE",
        )
        assert len(df) == 0
        for col in DATA_COLUMNS:
            assert col in df.columns


class TestSourceRegistration:
    def test_eea_registered(self):
        from aeolus.registry import get_source
        spec = get_source("EEA")
        assert spec is not None
        assert spec["name"] == "EEA"
        assert spec["type"] == "network"
        assert spec["requires_api_key"] is False

    def test_eea_in_list_sources(self):
        from aeolus.registry import list_sources
        sources = list_sources()
        assert "EEA" in sources

    def test_eea_fetch_metadata_accepts_bbox(self):
        from aeolus.registry import get_source
        import inspect
        spec = get_source("EEA")
        sig = inspect.signature(spec["fetch_metadata"])
        assert "bbox" in sig.parameters


@pytest.mark.integration
class TestLiveIntegration:
    """Live API integration tests — skipped in CI."""

    def test_fetch_metadata_ireland(self):
        from aeolus.sources.eea import fetch_eea_metadata

        df = fetch_eea_metadata(country="IE")
        assert len(df) > 0
        assert "site_code" in df.columns
        assert all(df["source_network"] == "EEA")

    def test_fetch_metadata_all_countries(self):
        from aeolus.sources.eea import fetch_eea_metadata

        df = fetch_eea_metadata()
        assert len(df) > 5000  # ~7000 stations across Europe

    def test_download_via_aeolus(self):
        import aeolus

        sources = aeolus.list_sources()
        assert "EEA" in sources

    def test_ratification_from_live_data(self):
        from aeolus.sources.eea import fetch_eea_data

        # Use 2024 date — airbase "Verified" dataset covers 2023-2024 for Ireland
        df = fetch_eea_data(
            ["IE0131A"],
            datetime(2024, 6, 1, tzinfo=timezone.utc),
            datetime(2024, 6, 2, tzinfo=timezone.utc),
            country="IE",
        )
        assert len(df) > 0
        assert all(df["ratification"].isin(["Provisional", "Verified"]))
