# v0.5.0 EEA Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `aeolus.download("EEA", …)` return data for any year the EEA holds, by querying the verified archive (E1a), the up-to-date feed (E2a) and the historical Airbase set together, preferring verified rows — with each row's timestamp on the right clock and its dataset recorded.

**Architecture:** `fetch_eea_data` issues one request per relevant dataset instead of one, tags each raw frame with its dataset id, and normalises the union. Timestamp conversion becomes dataset- and country-aware (`stamps_to_utc`). After normalisation, duplicate `(site_code, measurand, date_time)` rows are collapsed by priority verified → up-to-date → Airbase. The adapter emits `backend` (`EEA_E1A` / `EEA_E2A` / `EEA_AIRBASE`) so provenance survives the finalising step, which now keeps an adapter-provided `backend`.

**Tech Stack:** Python 3.11+, pandas, pyarrow, pytest with `unittest.mock`, uv.

**Spec:** `docs/dev/v050_design.md` §17.6 (characterisation and design), §17.10 (time), §15 (Airbase `Verification = 0`), §3.1 (`backend` values). Plans 1–2 in `docs/superpowers/plans/`.

## Global Constraints

- Plan 1's Global Constraints apply (British English; `uv run`; exact offline pytest command; live conformance before merging; enums frozen; `qa_code` verbatim).
- **Ground facts, all verified live (2026-09-20/22):** dataset ids are **1 = E2a up-to-date, 2 = E1a verified, 3 = Airbase (≤ 2012)** — the API's own zip folders are named `E2a`/`E1a`/`Airbase`. E2a begins 2024-01 (DE, IT, NL, PL), 2025-01 (ES) or 2026-01 (IE, FR, NO) and overlaps E1a for up to two years; E1a is incomplete for its latest year; overlapping values differ (rounding, corrections). `Verification` is 100 % `1` in E1a, `0` in Airbase.
- **Clocks (the messy part):** EEA states hourly stamps are "converted to the UTC+1 timezone". Verified true for E2a in DE, NL, IE, ES, PL (Italy's E2a is local civil time) and for E1a in DE, NL, PL, IT (lag 0 against their E2a on overlap). **Ireland's E1a is plain UTC** (lag 0 against Sonitus, r = 0.9999, both January and September 2025) — the documented convention does not hold there. FR, NO, ES E1a and all Airbase: unverified, assumed UTC+1. EEA therefore **stays `experimental`**; the status note must say exactly what is verified.
- Do not deduplicate Italy across datasets by raw stamp: convert both to UTC first (E2a as Europe/Rome, E1a as UTC+1), then deduplicate.
- Branch `feat/v050-eea-datasets` off `main` after PR #16 (QA wiring) has merged.

## File structure

| File | Change |
|---|---|
| `src/aeolus/schema.py` | `finalise_data_frame` keeps an adapter-provided `backend` |
| `src/aeolus/sources/eea.py` | dataset constants; `_E1A_CLOCK_OVERRIDES`; dataset-aware `stamps_to_utc`; `_fetch_dataset()`; multi-dataset `fetch_eea_data` with priority dedup and `backend`; status note |
| `src/aeolus/data/qa_vocabularies/EEA.yaml` | `"0"` (Airbase) entry |
| `tests/test_schema.py`, `tests/test_eea.py`, `tests/test_conformance.py`, `tests/test_source_consistency.py` | tests |
| `docs/sources/eea.md`, `CHANGELOG.md`, `docs/dev/v050_design.md` | docs |

---

### Task 1: The finaliser keeps an adapter's `backend`

**Files:** Modify `src/aeolus/schema.py`; test `tests/test_schema.py`.

**Interfaces:** `finalise_data_frame` — if the adapter frame already has a non-null `backend` column, those values are kept; rows with a null `backend` get the route's backend.

- [ ] **Step 1: Failing test** (append to `tests/test_schema.py`)

```python
def test_adapter_provided_backend_is_kept():
    frame = pd.concat([adapter_frame("EEA", backend="EEA_E1A"), adapter_frame("EEA", backend=None)], ignore_index=True)
    out = finalise_data_frame(frame, "EEA")
    assert out["backend"].tolist() == ["EEA_E1A", "EEA"]
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_schema.py --no-cov -p no:cacheprovider -q -k adapter_provided_backend` → `['EEA', 'EEA'] != ['EEA_E1A', 'EEA']`.

- [ ] **Step 3: Implement** — in `finalise_data_frame`, replace `out["backend"] = backend` with:

```python
    # An adapter that serves one network from several upstream datasets (EEA)
    # says which served each row; everything else gets the route's backend.
    if "backend" in out.columns:
        out["backend"] = out["backend"].astype(object).where(out["backend"].notna(), backend)
    else:
        out["backend"] = backend
```

- [ ] **Step 4: Run** `tests/test_schema.py`. **Step 5: Commit** — `feat(schema): keep an adapter-provided backend`.

---

### Task 2: Dataset-aware clocks

**Files:** Modify `src/aeolus/sources/eea.py`; test `tests/test_eea.py`.

**Interfaces:** `DATASET_UTD = 1`, `DATASET_VERIFIED = 2`, `DATASET_AIRBASE = 3` (replacing the misnamed `DATASET_E1A`); `_E1A_CLOCK_OVERRIDES: dict[str, str]`; `stamps_to_utc` reads a `dataset` column (int; absent → treated as `DATASET_UTD`).

- [ ] **Step 1: Failing tests** (append to `TestNormaliseEeaData`; the `_raw_df` helper builds a raw frame from records — add a `dataset` key to the records it is given, or assign the column after building)

```python
    @pytest.mark.parametrize(
        "samplingpoint, dataset, start, expected_utc",
        [
            ("DE/SPO.DE_DEBB021_NO2_dataGroup1", 2, "2024-07-01 01:00", "2024-07-01 00:00"),  # E1a, UTC+1
            ("IT/SPO.IT1168A_8_chemi_1998-01-30_00:00:00", 2, "2024-07-01 01:00", "2024-07-01 00:00"),  # Italy E1a is fixed UTC+1
            ("IT/SPO.IT1168A_8_chemi_1998-01-30_00:00:00", 1, "2024-07-01 02:00", "2024-07-01 00:00"),  # Italy E2a is local (CEST)
            ("IE/SPO.IE.IE0098ASample1_8", 2, "2024-07-01 00:00", "2024-07-01 00:00"),  # Ireland E1a is plain UTC (verified vs Sonitus)
            ("IE/SPO.IE.IE0098ASample1_8", 1, "2024-07-01 01:00", "2024-07-01 00:00"),  # Ireland E2a is UTC+1
        ],
    )
    @patch("aeolus.sources.eea._get_spo_mapping", return_value={})
    def test_stamps_depend_on_dataset_and_country(self, _mock, samplingpoint, dataset, start, expected_utc):
        from aeolus.sources.eea import normalise_eea_data

        raw = self._raw_df([{**MOCK_PARQUET_RECORDS[0], "Samplingpoint": samplingpoint, "Start": start, "End": start}])
        raw["dataset"] = dataset
        with patch("aeolus.sources.eea._samplingpoint_to_eoi", return_value="X0001A"):
            out = normalise_eea_data()(raw)
        assert out["date_time"].iloc[0] == pd.Timestamp(expected_utc, tz="UTC")
```

(If `_raw_df` cannot take a `Start` string in that form, build the frame with `pd.DataFrame([...])` directly, matching the column names of `MOCK_PARQUET_RECORDS`.)

- [ ] **Step 2: Run to verify** — the two Ireland-E1a and Italy-E1a cases fail today (no `dataset` awareness).

- [ ] **Step 3: Implement** — replace the `DATASET_E1A` block with:

```python
# Dataset ids of the EEA download API. NB: the API's own zip folders confirm
# these — 1 is the *up-to-date* feed, not the verified one (the constant was
# misnamed DATASET_E1A = 1 until v0.5.0, so earlier years came back empty).
DATASET_UTD = 1        # E2a: recent data, continuously transmitted
DATASET_VERIFIED = 2   # E1a: reported annually after national QA/QC
DATASET_AIRBASE = 3    # historical Airbase, 2002–2012
DATASET_PRIORITY = (DATASET_VERIFIED, DATASET_UTD, DATASET_AIRBASE)  # who wins a duplicate hour
DATASET_BACKEND = {DATASET_VERIFIED: "EEA_E1A", DATASET_UTD: "EEA_E2A", DATASET_AIRBASE: "EEA_AIRBASE"}

# EEA states hourly Start/End are "converted to the UTC+1 timezone". Verified
# true for the up-to-date feed in DE/NL/IE/ES/PL and the verified archive in
# DE/NL/PL/IT. Two exceptions found by measurement:
#   - Italy's up-to-date feed is local civil time (Europe/Rome);
#   - Ireland's verified archive is plain UTC (lag 0 vs Sonitus, r=0.9999).
# Everything else is assumed UTC+1 — which is why EEA stays `experimental`.
_UTD_LOCAL_CLOCK = {"IT": "Europe/Rome"}
_E1A_CLOCK_OVERRIDES = {"IE": "UTC"}
```

and in `stamps_to_utc`, replace the body after `naive = ...` with:

```python
        country = df["Samplingpoint"].astype(str).str[:2]
        dataset = df["dataset"] if "dataset" in df.columns else pd.Series(DATASET_UTD, index=df.index)
        utc = naive.dt.tz_localize("Etc/GMT-1").dt.tz_convert("UTC")  # POSIX sign: GMT-1 is UTC+1
        for code, zone in _UTD_LOCAL_CLOCK.items():
            rows = (country == code) & (dataset == DATASET_UTD)
            if rows.any():
                utc[rows] = naive[rows].dt.tz_localize(zone, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
        for code, zone in _E1A_CLOCK_OVERRIDES.items():
            rows = (country == code) & (dataset == DATASET_VERIFIED)
            if rows.any():
                utc[rows] = naive[rows].dt.tz_localize(zone).dt.tz_convert("UTC")
        df["date_time"] = utc
        return df[df["date_time"].notna()]
```

Update the docstring to say what the comment says. Replace every remaining `DATASET_E1A` reference (`grep -n DATASET_E1A src tests`) with `DATASET_UTD` for now — Task 3 changes the fetch.

- [ ] **Step 4: Run** `tests/test_eea.py tests/test_time_conventions.py`. **Step 5: Commit** — `feat(eea): dataset- and country-aware timestamp clocks`.

---

### Task 3: Query all relevant datasets, prefer verified rows, record provenance

**Files:** Modify `src/aeolus/sources/eea.py`; test `tests/test_eea.py`.

**Interfaces:** `_fetch_dataset(body_base: dict, dataset: int) -> pd.DataFrame | None` (raw frame tagged with `dataset`, or `None` when the response held no data); `fetch_eea_data` unchanged signature; output has `backend` per row.

- [ ] **Step 1: Failing tests** (append to `TestFetchEeaData`; `_make_parquet_zip` builds a response)

```python
    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    @patch("aeolus.sources.eea._download_parquet")
    def test_queries_verified_and_utd_and_prefers_verified(self, mock_download, _mock_mapping):
        from aeolus.sources.eea import DATASET_UTD, DATASET_VERIFIED, fetch_eea_data

        rec = dict(MOCK_PARQUET_RECORDS[0])  # IE record, Start 2024-01-01T00:00
        verified = _make_parquet_zip([{**rec, "Value": "10.0", "Verification": 1}])
        utd = _make_parquet_zip([{**rec, "Value": "11.5", "Verification": 2},
                                 {**rec, "Start": "2024-01-01T01:00:00", "End": "2024-01-01T02:00:00", "Value": "12.0", "Verification": 2}])
        mock_download.side_effect = lambda body: {DATASET_VERIFIED: verified, DATASET_UTD: utd}.get(body["dataset"])

        out = fetch_eea_data(["IE0028A"], datetime(2024, 1, 1), datetime(2024, 1, 2)).sort_values("date_time")
        datasets_asked = sorted(c.args[0]["dataset"] for c in mock_download.call_args_list)
        assert datasets_asked == [DATASET_UTD, DATASET_VERIFIED]           # no Airbase for a 2024 window
        assert out["value"].tolist() == [10.0, 12.0]                        # verified wins the shared hour
        assert out["backend"].tolist() == ["EEA_E1A", "EEA_E2A"]
        assert out["qa_code"].tolist() == ["1", "2"]

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    @patch("aeolus.sources.eea._download_parquet", return_value=None)
    def test_airbase_is_asked_for_only_before_2013(self, mock_download, _mock_mapping):
        from aeolus.sources.eea import DATASET_AIRBASE, fetch_eea_data

        fetch_eea_data(["IE0028A"], datetime(2012, 3, 1), datetime(2012, 3, 8))
        assert DATASET_AIRBASE in {c.args[0]["dataset"] for c in mock_download.call_args_list}
        mock_download.reset_mock()
        fetch_eea_data(["IE0028A"], datetime(2013, 1, 1), datetime(2013, 1, 8))
        assert DATASET_AIRBASE not in {c.args[0]["dataset"] for c in mock_download.call_args_list}
```

Adjust the site code and `Start` strings to whatever `MOCK_PARQUET_RECORDS[0]` and `MOCK_SPO_MAPPING` actually use (read them; the mapping must resolve the record's `Samplingpoint` to the site you request).

- [ ] **Step 2: Run to verify they fail** — today only one request is made (`datasets_asked == [1]`) and there is no `backend` column.

- [ ] **Step 3: Implement** — extract the zip-parsing into a helper and loop over datasets:

```python
def _parse_parquet_zip(zip_bytes: bytes) -> pd.DataFrame | None:
    dfs: list[pd.DataFrame] = []
    with ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith(".parquet"):
                with zf.open(name) as f:
                    df = pd.read_parquet(BytesIO(f.read()))
                    if not df.empty:
                        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None


def _fetch_dataset(body_base: dict, dataset: int) -> pd.DataFrame | None:
    """One dataset's raw rows for the window, tagged with the dataset id."""
    zip_bytes = _download_parquet({**body_base, "dataset": dataset})
    if not zip_bytes:
        return None
    try:
        raw = _parse_parquet_zip(zip_bytes)
    except Exception as e:  # noqa: BLE001 - a bad zip from one dataset must not sink the others
        warnings.warn(f"Failed to parse EEA Parquet response (dataset {dataset}): {e}", AeolusDataWarning, stacklevel=3)
        return None
    return None if raw is None else raw.assign(dataset=dataset)
```

In `fetch_eea_data`, replace everything from `body: dict = {` to the `# Normalise` comment with:

```python
    body_base: dict = {
        "countries": [country.upper()],
        "cities": [],
        "pollutants": notation_list if notation_list else [],
        "dateTimeStart": to_utc(start_date).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dateTimeEnd": to_utc(end_date).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compress": True,
    }
    # The verified archive and the up-to-date feed overlap by up to two years
    # (which years depends on the country), so both are always asked for;
    # Airbase only holds 2002–2012.
    datasets = [DATASET_VERIFIED, DATASET_UTD]
    if to_utc(start_date).year <= 2012:
        datasets.append(DATASET_AIRBASE)
    frames = [f for f in (_fetch_dataset(body_base, d) for d in datasets) if f is not None]
    if not frames:
        return empty_data_frame()
    raw_df = pd.concat(frames, ignore_index=True)
```

and after normalisation, before the site filter:

```python
    # One row per (site, measurand, hour): verified beats up-to-date beats Airbase
    df = df.assign(_priority=df["backend"].map({DATASET_BACKEND[d]: i for i, d in enumerate(DATASET_PRIORITY)}))
    df = (df.sort_values(["site_code", "measurand", "date_time", "_priority"], kind="stable")
            .drop_duplicates(subset=["site_code", "measurand", "date_time"], keep="first")
            .drop(columns="_priority"))
```

In `normalise_eea_data`, add `add_column("backend", lambda df: df["dataset"].map(DATASET_BACKEND) if "dataset" in df.columns else "EEA")` before `select_columns`, and select `*ADAPTER_DATA_COLUMNS_QA, "backend"` (still `require_all=True`). The `dataset` column must survive until `stamps_to_utc` — it does, because nothing drops it before the terminal select.

- [ ] **Step 4: Run** `tests/test_eea.py tests/test_eea_properties.py tests/test_schema.py`; fix column-list assertions to include `backend`. **Step 5: Commit** — `feat(eea): query verified, up-to-date and Airbase datasets; prefer verified rows`.

---

### Task 4: Airbase vocabulary, live guards, status, docs

**Files:** `src/aeolus/data/qa_vocabularies/EEA.yaml`, `src/aeolus/sources/eea.py` (status note), `tests/test_conformance.py`, `tests/test_source_consistency.py`, `docs/sources/eea.md`, `CHANGELOG.md`, `docs/dev/v050_design.md`.

- [ ] **Step 1: Vocabulary** — add to `EEA.yaml`'s `qa_code_vocabulary`:

```yaml
  "0":
    description: Airbase legacy record (2002–2012); verification status not recorded
    qa_tier: unknown
    ratification_stage: null
    source_url: https://dd.eionet.europa.eu/vocabulary/aq/observationverification
```

(`tests/test_network_registry.py` validates it loads.)

- [ ] **Step 2: Conformance** — in `tests/test_conformance.py::TestEEA` replace `test_download` with two tests: the existing recent-window download, and

```python
    def test_past_year_is_served_from_the_verified_archive(self):
        """The bug that made EEA experimental: earlier years came back empty."""
        data = aeolus.download("EEA", ["IE0028A"], start_date=datetime(2023, 3, 6, tzinfo=timezone.utc), end_date=datetime(2023, 3, 13, tzinfo=timezone.utc))
        assert len(data) > 100, "March 2023 must come from the verified archive"
        assert set(data["backend"]) == {"EEA_E1A"}
        assert set(data["qa_code"]) == {"1"}
        run_data_conformance(data, "EEA")

    def test_irish_archive_clock_matches_sonitus(self):
        """Guards the _E1A_CLOCK_OVERRIDES entry: Ireland's E1a is plain UTC."""
        start, end = datetime(2025, 9, 9, tzinfo=timezone.utc), datetime(2025, 9, 12, tzinfo=timezone.utc)
        eea = aeolus.download("EEA", ["IE0098A"], start_date=start, end_date=end)
        son = aeolus.download("SONITUS", ["DCC-AQ1"], start_date=start, end_date=end)
        e = eea[eea["measurand"] == "NO2"].set_index("date_time")["value"]
        s = son[son["measurand"] == "NO2"].set_index("date_time")["value"].resample("h").mean()
        lags = {k: s.shift(k, freq="h").corr(e) for k in (-1, 0, 1)}
        assert max(lags, key=lags.get) == 0 and lags[0] > 0.99, lags
```

- [ ] **Step 3: Status note** — replace the EEA `status_note` with:

```python
    "status_note": (
        "timestamps are converted from the EEA's UTC+1 convention, which is verified only for "
        "the up-to-date feed in DE/NL/IE/ES/PL (Italy: local time) and the verified archive in "
        "DE/NL/PL/IT (Ireland: plain UTC); other countries and the Airbase archive are assumed."
    ),
```

and update `tests/test_source_consistency.py::test_eea_is_experimental_and_says_why` to assert `"UTC+1" in info["status_note"]`.

- [ ] **Step 4: Docs** — `docs/sources/eea.md`: rewrite the experimental box (history now available; which clocks are verified), the `History` overview line, and the Data quality section (`backend` says which dataset; `"0"` for Airbase). `CHANGELOG.md` under the breaking section: EEA now serves every year the EEA holds; `backend` distinguishes `EEA_E1A`/`EEA_E2A`/`EEA_AIRBASE`; verified rows win overlaps; Ireland's archive clock. `docs/dev/v050_design.md` §17.6: status DONE with the clock table; §3.1: the three EEA backend values.

- [ ] **Step 5: Verification ladder** — offline; isolated 3.13 no keys; mirrors-off on `tests/test_eea.py tests/test_schema.py`; **live conformance** (the two new EEA tests must pass; AirQo's two failures remain).

- [ ] **Step 6: Commit and open the PR** — `git push -u origin feat/v050-eea-datasets && gh pr create --base main --title "v0.5.0 EEA datasets: verified archive, up-to-date feed and Airbase, on the right clocks"`.

## Self-review

- §17.6 proposal covered: window-based dataset selection (Task 3), verified-wins dedup (Task 3), provenance (Tasks 1, 3), Italy handled by converting before dedup (Task 2), `Verification = 0` (Task 4), past-year conformance (Task 4). §17.10's Ireland hazard → Task 2 override + Task 4 guard.
- Not done, deliberately: per-country E1a clock verification beyond DE/NL/PL/IT/IE — no reference source; recorded in the status note. Deduplication of EEA against national sources (Sonitus) is v0.6.0 cross-backend dedup.
- Cost: two requests per download instead of one (three for pre-2013 windows); an empty dataset response returns in ~1.5 s.
