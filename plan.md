# Plan: Per-site measurand metadata

## Goal
Add a `measurands` column to the metadata schema so `find_sites()` and `get_metadata()` return which pollutants each site measures.

## Current state
- Metadata schema is 5 columns: `site_code`, `site_name`, `latitude`, `longitude`, `source_network`
- No per-site pollutant info exposed anywhere in the public API
- `_sos_mapping.json` already contains per-site measurand lists for AURN (199), SAQN (23), WAQN (12), NI (7), AQE (15)
- 37 sites appear in multiple SOS networks (e.g. CARD in both AURN and WAQN) — measurand lists are always identical across networks, so no conflict

## Edge cases to handle

### 1. SOS covers only 8 pollutants; RData has 41
SOS reports: CO, NO, NO2, NOXasNO2, O3, PM10, PM2.5, SO2.
RData files also contain 30+ VOCs (BENZENE, TOLUENE, ETHANE, etc.) from hydrocarbon monitoring sites.
**Risk:** A site like Marylebone Road measures VOCs via RData but SOS won't list them → we'd under-report.
**Approach:** Treat SOS measurands as a known floor. Accept the gap for now — VOC sites are rare (~5 AURN sites) and this is still far better than nothing. Document the limitation. A future enhancement could scan RData column headers for a single year to fill the gap.

### 2. LOCAL and LMAM have no SOS mapping
These networks are not in `_SOS_NETWORKS` so `_sos_mapping.json` has zero entries for them.
**Approach:** Return `measurands=None` (not empty list) for LOCAL/LMAM sites, signalling "unknown" rather than "measures nothing". Document that these networks don't yet have per-site measurand info.

### 3. Historical/closed sites in RData metadata but not in SOS
SOS only tracks currently-active stations. A site decommissioned in 2020 will appear in regulatory metadata but not in SOS mapping.
**Approach:** Same as LOCAL/LMAM — return `measurands=None` for unmatched sites. This is honest: we don't know what a closed site measured without downloading its data.

### 4. Cross-network duplicates (37 sites)
Sites like BEL2 appear in both AURN and NI with identical measurand lists.
**No problem** — each network's metadata is independent, and since the lists match, users get consistent info regardless of which network they query.

### 5. SAQD (Scottish diffusion tubes)
SAQD shares the same RData metadata URL as SAQN but has zero SOS entries.
**Approach:** `measurands=None` for SAQD sites.

### 6. Non-regulatory sources
- **OpenAQ:** Already has `parameters` per location from API. Normalise to same `measurands` format.
- **Sensor.Community:** Infer from `sensor_type` via existing `SENSOR_TYPE_MAP` (e.g. SDS011 → [PM2.5, PM10]).
- **PurpleAir:** All sensors nominally measure PM1/PM2.5/PM10/T/RH/P, some have VOC/O3. The metadata API doesn't distinguish per-sensor. Return the common set or `None`.
- **Breathe London, AirQo, AirNow:** No per-site info from API. Return `None`.

## Implementation steps

### Step 1: Extend metadata schema
- Add `measurands` to `METADATA_COLUMNS` in `types.py` (making it a 6-column schema)
- Type: `object` column containing Python `list[str]` or `None`
- Update `empty_metadata_frame()` to include the column

### Step 2: Regulatory source — wire up SOS mapping
In `regulatory.py`, in `fetch_*_metadata()` or `normalise_regulatory_metadata()`:
- Load `_sos_mapping.json` (already shipped, small file, fast)
- For each site, look up its measurands from the mapping for the appropriate network key
- Deduplicate and sort the measurand list
- Sites not found in mapping get `measurands=None`

### Step 3: OpenAQ source
In `openaq.py`, in `fetch_openaq_metadata()`:
- The API response already includes `parameters` per location
- Map to a sorted `list[str]` in the `measurands` column
- Drop the raw `parameters` column (or keep as extra — TBD)

### Step 4: Sensor.Community source
In `sensor_community.py`:
- Use existing `SENSOR_TYPE_MAP` to derive measurands from `sensor_type`
- Return as `measurands` column

### Step 5: Other sources
- PurpleAir, Breathe London, AirQo, AirNow: add `measurands=None` column in their metadata normalisation (the schema change in step 1 may handle this via `empty_metadata_frame`, but explicit is safer)

### Step 6: find_sites() — optional measurand filter
Add an optional `measurand=` parameter to `find_sites()`:
```python
# Find NO2 monitors near Birmingham
sites = aeolus.find_sites("AURN", near=(52.48, -1.89), radius_km=20, measurand="NO2")
```
- Filter: keep rows where `measurands is not None and measurand in measurands`
- Sites with `measurands=None` are excluded when filtering (can't confirm they measure it)
- Accept a single string or list of strings (any-match semantics)

### Step 7: Tests
- Test regulatory metadata returns `measurands` column with correct lists
- Test sites not in SOS mapping get `measurands=None`
- Test `find_sites(measurand="NO2")` filters correctly
- Test that `measurands=None` sites are excluded by measurand filter
- Test OpenAQ and Sensor.Community measurand extraction
- Test cross-network duplicate consistency (BEL2 in AURN vs NI)

### Step 8: Update CLAUDE.md
- Update metadata schema docs to mention `measurands`
- Note the limitation for LOCAL/LMAM and VOCs
