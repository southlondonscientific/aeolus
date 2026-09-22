# v0.5.0 EEA Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `aeolus.download("EEA", …)` return data for any year the EEA holds, by querying the verified archive (E1a), the up-to-date feed (E2a) and the historical Airbase set together, preferring verified rows — with each row's timestamp on the right clock and its dataset recorded.

**Architecture:** `fetch_eea_data` issues one request per relevant dataset instead of one, tags each raw frame with its dataset id, and normalises the union. Timestamp conversion becomes dataset- and country-aware (`stamps_to_utc`). Inside the normaliser, before the validity filter, rows are collapsed by **day-level priority**: if the verified archive holds any row for a `(site, measurand, day)`, the up-to-date feed's (and Airbase's) rows for that day are dropped, so an overlap day is served entirely by one dataset. The adapter emits `backend` (`EEA_E1A` / `EEA_E2A` / `EEA_AIRBASE`) so provenance survives the finalising step, which now keeps an adapter-provided `backend`.

**Tech Stack:** Python 3.11+, pandas, pyarrow, pytest with `unittest.mock`, uv.

**Spec:** `docs/dev/v050_design.md` §17.6 (characterisation and design), §17.10 (time), §15 (Airbase `Verification = 0`), §3.1 (`backend` values). Plans 1–2 in `docs/superpowers/plans/`.

## Global Constraints

- Plan 1's Global Constraints apply (British English; `uv run`; exact offline pytest command; live conformance before merging; enums frozen; `qa_code` verbatim).
- **Ground facts, all verified live (2026-09-20/22):** dataset ids are **1 = E2a up-to-date, 2 = E1a verified, 3 = Airbase (≤ 2012)** — the API's own zip folders are named `E2a`/`E1a`/`Airbase`. E2a begins 2024-01 (DE, IT, NL, PL), 2025-01 (ES) or 2026-01 (IE, FR, NO) and overlaps E1a for up to two years; E1a is incomplete for its latest year; overlapping values differ (rounding, corrections). `Verification` is 100 % `1` in E1a, `0` in Airbase.
- **Clocks (the messy part):** EEA states hourly stamps are "converted to the UTC+1 timezone". Verified true for E2a in DE, NL, IE, ES, PL (Italy's E2a is local civil time) and for E1a in DE, NL, PL, IT (lag 0 against their E2a on overlap). **Ireland's E1a is plain UTC** (lag 0 against Sonitus, r = 0.9999, both January and September 2025) — the documented convention does not hold there. FR, NO, ES E1a and all Airbase: unverified, assumed UTC+1. EEA therefore **stays `experimental`**; the status note must say exactly what is verified.
- Deduplication is by **day**, not hour, and runs **before** the `Validity >= 1` filter. Reasons (plan review, 2026-09-22): hour-level keys merge co-located instruments (two PM10 sampling points at one station); an hour the archive rejected as invalid would otherwise be resurrected from the up-to-date feed; and Italy's up-to-date stamps follow the DST model for only ~88 % of sampling points (§17.6: 340/390 shifted in September, ~13 % in winter), so after conversion the residual points would sit an hour off the archive and double up. With day-level priority none of these can happen on overlap days; the residual Italian E2a points remain a caveat for non-overlap periods and are documented as such.
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

- [ ] **Step 3: Implement** — in `finalise_data_frame` (NOT `finalise_metadata_frame`, which has the same line), replace `out["backend"] = backend` with:

```python
    # An adapter that serves one network from several upstream datasets (EEA)
    # says which served each row; everything else gets the route's backend.
    if "backend" in out.columns:
        out["backend"] = out["backend"].fillna(backend)  # fillna keeps the dtype: finalising twice must be a no-op
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
    def test_stamps_depend_on_dataset_and_country(self, samplingpoint, dataset, start, expected_utc):
        from aeolus.sources.eea import normalise_eea_data

        raw = self._raw_df([{**MOCK_PARQUET_RECORDS[0], "Samplingpoint": samplingpoint, "Start": start, "End": start}])
        raw["dataset"] = dataset
        # Patch the mapping, not the per-row function: Series.apply treats a
        # MagicMock as dict-like and the pipeline then has nothing to concatenate.
        with patch("aeolus.sources.eea._get_spo_mapping", return_value={samplingpoint.split("/", 1)[1]: "X0001A"}):
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
        country = df["Samplingpoint"].astype(str).str.split("/").str[0]  # "IE/SPO.IE…" -> "IE"
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

Update the `stamps_to_utc` docstring and the module docstring (which still says "We use E1a (dataset=1)") to say what the comment says. Replace every remaining `DATASET_E1A` reference (`grep -n DATASET_E1A src tests`) with `DATASET_UTD` for now — Task 3 changes the fetch.

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

        # A German fixture: Germany is on the documented UTC+1 clock in both
        # datasets, so no country override interferes with the assertions.
        # (An Irish fixture would read E1a as UTC and E2a as UTC+1 and the
        # hours would no longer line up.)
        sp = "DE/SPO.DE_DEBB021_NO2_dataGroup1"
        _mock_mapping.return_value = {**MOCK_SPO_MAPPING, "SPO.DE_DEBB021_NO2_dataGroup1": "DEBB021"}
        rec = {**MOCK_PARQUET_RECORDS[0], "Samplingpoint": sp}
        day1 = lambda h, v, ver: {**rec, "Start": f"2024-01-01T{h:02d}:00:00", "End": f"2024-01-01T{h + 1:02d}:00:00", "Value": v, "Verification": ver}
        day2 = lambda h, v, ver: {**rec, "Start": f"2024-01-02T{h:02d}:00:00", "End": f"2024-01-02T{h + 1:02d}:00:00", "Value": v, "Verification": ver}
        verified = _make_parquet_zip([day1(1, "10.0", 1)])                                   # archive holds day 1 only
        utd = _make_parquet_zip([day1(1, "11.5", 2), day1(2, "11.9", 2), day2(1, "12.0", 2)])  # feed holds both days
        mock_download.side_effect = lambda body: {DATASET_VERIFIED: verified, DATASET_UTD: utd}.get(body["dataset"])

        out = fetch_eea_data(["DEBB021"], datetime(2024, 1, 1), datetime(2024, 1, 3)).sort_values("date_time")
        datasets_asked = sorted(c.args[0]["dataset"] for c in mock_download.call_args_list)
        assert datasets_asked == [DATASET_UTD, DATASET_VERIFIED]           # no Airbase for a 2024 window
        # Day 1 is served entirely by the archive (its 02:00 feed row is dropped
        # too — day-level priority); day 2 only the feed has.
        assert out["value"].tolist() == [10.0, 12.0]
        assert out["backend"].tolist() == ["EEA_E1A", "EEA_E2A"]
        assert out["qa_code"].tolist() == ["1", "2"]

    @patch("aeolus.sources.eea._get_spo_mapping", return_value=MOCK_SPO_MAPPING)
    @patch("aeolus.sources.eea._download_parquet", return_value=None)
    def test_airbase_is_asked_for_only_before_2013(self, mock_download, _mock_mapping):
        from aeolus.sources.eea import DATASET_AIRBASE, fetch_eea_data

        fetch_eea_data(["IE0131A"], datetime(2012, 3, 1), datetime(2012, 3, 8))
        assert DATASET_AIRBASE in {c.args[0]["dataset"] for c in mock_download.call_args_list}
        mock_download.reset_mock()
        fetch_eea_data(["IE0131A"], datetime(2013, 1, 1), datetime(2013, 1, 8))
        assert DATASET_AIRBASE not in {c.args[0]["dataset"] for c in mock_download.call_args_list}
```

Add a third test, `test_invalid_archive_hour_is_not_resurrected_from_the_feed`: archive row for day 1 hour 1 with `Validity: -1`, feed rows for day 1 hours 1 and 2 valid → the result has **no** rows for day 1 (the archive claims the day; its only row is then dropped as invalid). And a fourth, `test_two_sampling_points_at_one_station_both_survive`: two archive rows, same station/hour, different `Samplingpoint` → two rows out.

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

The deduplication lives in the **normaliser**, as a step straight after `stamps_to_utc` and **before** the `Validity >= 1` filter (move that `filter_rows` down the pipeline to just after this step):

```python
    def prefer_verified_days(df: pd.DataFrame) -> pd.DataFrame:
        """Serve each (site, measurand, day) from the highest-priority dataset that
        holds any row for it — verified beats up-to-date beats Airbase.

        Day-level, not hour-level, and before the validity filter, so that:
        co-located instruments at one station are not merged; an hour the
        archive rejected is not resurrected from the feed; and Italian
        up-to-date points whose stamps do not follow the DST model cannot
        double up beside archive rows on overlap days.
        """
        if "dataset" not in df.columns or df.empty:
            return df
        priority = df["dataset"].map({d: i for i, d in enumerate(DATASET_PRIORITY)})
        day = df["date_time"].dt.floor("D")
        best = priority.groupby([df["site_code"], df["measurand"], day], observed=True).transform("min")
        return df[priority == best]
```

Pipeline order after the change: `extract_site_codes`, `map_pollutants`, `rename_columns`, `stamps_to_utc`, `prefer_verified_days`, `filter_rows(Validity >= 1)`, `convert_value`, … Then add `add_column("backend", lambda df: df["dataset"].map(DATASET_BACKEND) if "dataset" in df.columns else "EEA")` before `select_columns`, and select `*ADAPTER_DATA_COLUMNS_QA, "backend"` (still `require_all=True`). `fetch_eea_data` itself does no deduplication. The `dataset` column survives to these steps because nothing drops it before the terminal select.

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

- [ ] **Step 2: Conformance** — in `tests/test_conformance.py::TestEEA`, fix `test_download`: it requests `"STA-IE0028A"`, which `_infer_country_from_sites` reads as country `ST`, so it has always passed on an empty frame. Use `"IE0028A"` and assert `not data.empty`. Then add two tests (the Sonitus twin pair `DCC-AQ1 ↔ IE0098A` is from the 2026-09-21 time audit, r ≈ 0.98):

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

## Plan review (2026-09-22, before execution)

Reviewed by a read-only agent against the post-#16 code with the plan applied to a scratch copy. Three blockers fixed
in the text above: the Task 3 fixture was Irish (the Ireland override then shifts its hours) and used a site absent
from `MOCK_SPO_MAPPING`; the Task 2 test patched the per-row function with a MagicMock, which `Series.apply` treats as
dict-like; `astype(object).where(...)` for `backend` broke the finalise-twice idempotency test under pandas 3. Three
design findings — hour-level dedup merges co-located instruments, resurrects archive-rejected hours from the feed, and
doubles Italy's ~12 % non-model sampling points — are all answered by the day-level priority step now specified in
Task 3, placed before the validity filter. Two nits (the conformance test's `STA-` site code that had always yielded
empty data; the stale `DATASET_E1A` docstrings) folded in.
