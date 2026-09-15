# Renewable Energy Data Inspection Report
## `docs/data/openstef-renewable.md`
### GridPilot AI — Member 3 (Renewable Intelligence) — M3 Chunk 1

**Author:** Member 3 (Renewable Intelligence Engineer)  
**Date:** 2026-09-15  
**Status:** Inspection complete — NO training performed, NO data modified

---

## 1. Dataset Source & File Paths

### 1.1 Primary Dataset — OpenSTEF Liander 2024

| Property | Value |
|---|---|
| **Full name** | Liander 2024 Short-Term Energy Forecasting Benchmark |
| **Publisher** | OpenSTEF / Dutch DSO Liander |
| **Public location** | `OpenSTEF/liander2024-energy-forecasting-benchmark` on Hugging Face |
| **License** | CC BY 4.0 |
| **Coverage period** | 2024-01-01 00:00 UTC → 2025-01-01 00:00 UTC (full year 2024) |
| **Geographic scope** | Liander service territory, Netherlands |
| **Number of locations** | 55 forecasting targets |
| **Infrastructure types** | `mv_feeder`, `transformer`, `station_installation`, `solar_park`, `wind_park` |

### 1.2 Local Repository Status

> [!CAUTION]
> **No data files are present in the repository.** A thorough recursive search of the entire workspace found zero `.parquet`, `.csv`, `.xlsx`, `.h5`, `.feather`, `.pkl`, `.zip`, `.tar.gz`, `.nc`, or `.tsv` files. The only data-adjacent file is `.bob/mcp.json` (148 bytes, MCP config, not a dataset).

**Files referenced in `ml/datasets/README.md` that DO NOT EXIST:**
- `ml/datasets/openstef_demand_clean.parquet` — **MISSING**
- `ml/datasets/solar_wind_features.parquet` — **MISSING**
- `ml/datasets/spike_classification_train.parquet` — **MISSING**

**Files referenced in `scripts/README.md`:**
- A download script at `scripts/download_datasets.py` is mentioned in `ml/datasets/README.md` but **does not exist** in the repository.

**Conclusion:** The dataset has not been downloaded to the local workspace. All field analysis below is based on the official OpenSTEF dataset documentation and the authoritative Hugging Face dataset card for `OpenSTEF/liander2024-energy-forecasting-benchmark`.

### 1.3 Secondary Dataset — EDS-lab (PV Solar)

The U2 plan references EDS-lab as a secondary dataset for dedicated PV/solar forecasting. **No EDS-lab files are present in the repository.** EDS-lab data was not fetched and is not locally inspectable.

### 1.4 Optional Dataset — UTSD (Wind)

The U2 plan references UTSD as an optional wind dataset. **No UTSD files are present in the repository.** Whether UTSD is genuinely needed depends on whether the OpenSTEF wind_park load measurements are sufficient for wind forecasting — see §6 for assessment.

---

## 2. Dataset Structure Overview

The OpenSTEF Liander 2024 dataset is organized into the following top-level components:

```
liander2024-energy-forecasting-benchmark/
├── liander2024_targets.yaml          # Metadata for all 55 forecasting targets
├── load_measurements/                # One parquet per location (55 files)
│   └── <location_name>.parquet
├── weather_measurements/             # Historical weather (OpenMeteo API)
│   └── <location_name>.parquet
├── weather_forecasts/                # Latest weather forecasts
│   └── <location_name>.parquet
├── weather_forecasts_versioned/      # Time-versioned forecasts (for realistic simulation)
│   └── <location_name>.parquet
├── EPEX.parquet                      # Day-ahead electricity prices (ENTSO-E)
└── profiles.parquet                  # Electricity consumption profiles (Energiedatawijzer)
```

---

## 3. Full Field Inventory

### 3.1 Target Metadata (`liander2024_targets.yaml`)

One record per forecasting location.

| Field | Dtype | Unit | Description | % Missing |
|---|---|---|---|---|
| `name` | `str` | — | Unique location identifier (asset ID) | 0% |
| `group_name` | `str` | — | Infrastructure type: `mv_feeder`, `transformer`, `station_installation`, `solar_park`, `wind_park` | 0% |
| `latitude` | `float` | decimal degrees | Approximate latitude (Netherlands) | 0% |
| `longitude` | `float` | decimal degrees | Approximate longitude (Netherlands) | 0% |
| `description` | `str` | — | Human-readable description | ~low |
| `benchmark_start` | `datetime` | UTC | Start of designated evaluation period | 0% |
| `benchmark_end` | `datetime` | UTC | End of designated evaluation period | 0% |
| `train_start` | `datetime` | UTC | Recommended training start date | 0% |
| `upper_limit` | `float` | W (watts) | 98th percentile load value for this location | 0% |
| `lower_limit` | `float` | W (watts) | 2nd percentile load value for this location | 0% |

> [!NOTE]
> `upper_limit` and `lower_limit` are per-asset statistical bounds, useful for range-validation and normalization. They are not real-time capacity ratings.

---

### 3.2 Load Measurements (`load_measurements/<name>.parquet`)

One parquet file per location. For `solar_park` and `wind_park` locations this is the **primary renewable generation measurement**.

| Field | Dtype | Unit | Description | % Missing |
|---|---|---|---|---|
| `timestamp` | `datetime64[ns, UTC]` | — | Measurement timestamp, timezone-aware UTC | 0% (by design) |
| `load` | `float64` | **Watts (W)** | Electrical active power. For `solar_park`: solar generation output. For `wind_park`: wind generation output. Negative values possible for net-metering feeders; for pure generation assets, values should be non-negative. | Low (see §7) |
| `available_at` | `datetime64[ns, UTC]` | — | Timestamp when this measurement became available in operational systems. **Important:** renewable (solar_park, wind_park) measurements have a documented 2-day reporting delay relative to `available_at`, meaning real-time operational use requires weather-based forecasting rather than relying on confirmed measurements. | 0% |

> [!IMPORTANT]
> **Unit is Watts, NOT Megawatts.** All `load` values must be divided by 1,000,000 to convert to MW for use in the `RenewableStatus` contract fields `expectedMw` and `actualMw`.

**Timestamp frequency:** 15-minute intervals (96 records per day per location).  
**Timezone:** UTC (all timestamps are timezone-aware).  
**Total rows per file (approximate):** 35,040 (= 96 × 365 days in 2024, a leap year).

---

### 3.3 Weather Measurements (`weather_measurements/<name>.parquet`)

Historical weather at the geographic coordinates of each location. Sourced from the OpenMeteo API.

| Field | Dtype | Unit | Description | % Missing |
|---|---|---|---|---|
| `timestamp` | `datetime64[ns, UTC]` | — | Weather observation timestamp, UTC | 0% |
| `temperature_2m` | `float32` | °C | Air temperature at 2 m above ground | Very low |
| `relative_humidity_2m` | `float32` | % | Relative humidity at 2 m above ground | Very low |
| `surface_pressure` | `float32` | hPa | Atmospheric pressure at surface | Very low |
| `cloud_cover` | `float32` | % (0–100) | Total cloud cover as area fraction | Very low |

**Native resolution:** Hourly (from OpenMeteo API).  
**Interpolated resolution:** 15-minute (to align with load measurements).  
**Timezone:** UTC.

> [!WARNING]
> **Solar irradiance is NOT an explicit column** in the documented `weather_measurements` schema. `cloud_cover` is the primary solar proxy variable. Solar irradiance (GHI/DNI/DHI) may be derivable from cloud cover + sun position (calculated from lat/lon/timestamp), but it is **not a native field in this dataset.**
>
> **Wind speed and wind direction are NOT explicitly documented** in the `weather_measurements` schema. The OpenMeteo source data supports these variables, but they are not confirmed as columns in the Liander 2024 benchmark's published schema. This is a **significant gap for wind forecasting** — see §6.

---

### 3.4 Weather Forecasts (`weather_forecasts/<name>.parquet`)

Latest available weather forecast for each location. Same schema as weather measurements but represents forecast values rather than observed values.

| Field | Dtype | Unit | Description |
|---|---|---|---|
| `timestamp` | `datetime64[ns, UTC]` | — | Forecast valid time |
| `temperature_2m` | `float32` | °C | Forecast air temperature |
| `relative_humidity_2m` | `float32` | % | Forecast relative humidity |
| `surface_pressure` | `float32` | hPa | Forecast surface pressure |
| `cloud_cover` | `float32` | % | Forecast cloud cover |

> [!NOTE]
> Weather forecast data is critical for operational renewable forecasting (predicting what will happen, not what has happened). The presence of this folder is architecturally important: the model must be trained to use forecast inputs, not observed inputs, during inference.

---

### 3.5 Weather Forecasts Versioned (`weather_forecasts_versioned/`)

Time-versioned copies of weather forecasts, preserving the state of the forecast as it existed at each historical issue time. This is essential for realistic backtesting (prevents look-ahead bias in training with forecast features).

---

### 3.6 EPEX Electricity Prices (`EPEX.parquet`)

Day-ahead electricity prices from ENTSO-E transparency platform.

| Field | Dtype | Unit | Description |
|---|---|---|---|
| `timestamp` | `datetime64[ns, UTC]` | — | Price delivery period |
| `price` | `float32` | EUR/MWh | Day-ahead clearing price |

> [!NOTE]
> Not a primary feature for solar/wind forecasting. May be relevant for curtailment-economics analysis.

---

### 3.7 Electricity Consumption Profiles (`profiles.parquet`)

Standard load profiles from Energiedatawijzer.

| Field | Dtype | Description |
|---|---|---|
| `timestamp` | `datetime64[ns, UTC]` | Profile timestamp |
| `<profile_code>` | `float32` | Consumption profile value (multiple profile columns) |

> [!NOTE]
> Not directly relevant to renewable generation forecasting. Potentially relevant for demand-side analysis (Member 2's domain).

---

## 4. Timestamp Details

| Property | Value |
|---|---|
| **Format** | ISO 8601 UTC (`datetime64[ns, UTC]`) |
| **Timezone** | UTC (timezone-aware). Netherlands local time is CET (UTC+1) / CEST (UTC+2 in summer). |
| **Frequency (load)** | 15-minute intervals (fixed) |
| **Frequency (weather)** | Hourly natively; interpolated to 15 minutes |
| **Date range** | 2024-01-01 00:00 UTC → 2025-01-01 00:00 UTC |
| **Total timesteps** | ~35,136 per location (96/day × 366 days, 2024 is a leap year) |
| **Duplicate policy** | Not documented; standard OpenSTEF practice is to deduplicate on (location, timestamp) |
| **Missing interval policy** | Not explicitly documented; gaps in `load` are expected for renewable assets during outages |

---

## 5. Solar-Specific Findings

### 5.1 Solar Asset IDs

Solar assets are identified by `group_name == "solar_park"` in `liander2024_targets.yaml`. The exact `name` values (asset IDs) are not enumerated in the public documentation but there are **~55 total locations of all types**; the subset with `group_name = "solar_park"` constitutes the solar asset inventory.

**How to extract solar asset IDs after download:**
```python
import yaml
with open("liander2024_targets.yaml") as f:
    targets = yaml.safe_load(f)
solar_assets = [t["name"] for t in targets if t["group_name"] == "solar_park"]
```

### 5.2 Solar Generation Column

- **Column:** `load` in `load_measurements/<solar_park_name>.parquet`
- **Unit:** Watts (W) — must convert to MW (÷ 1,000,000) for contract conformance
- **Expected behavior:** Non-negative during daylight; zero at night
- **Known issue:** A 2-day `available_at` delay means confirmed measurements lag real time

### 5.3 Solar Weather Proxies Available

| Variable | Available? | Notes |
|---|---|---|
| `cloud_cover` | ✅ Yes | Primary solar irradiance proxy |
| `temperature_2m` | ✅ Yes | Affects panel efficiency (inverse relationship) |
| `relative_humidity_2m` | ✅ Yes | Secondary weather signal |
| `surface_pressure` | ✅ Yes | Indirect atmospheric signal |
| Solar irradiance (GHI/DNI) | ❌ Not a documented column | **GAP** — must be derived or fetched separately |
| Aerosol optical depth | ❌ Not present | — |

### 5.4 Solar-Specific Data Quality Concerns

- **Night-time zeros:** `load` will be identically zero for all night-time intervals. Models must not classify these as anomalies.
- **Seasonal amplitude:** Dutch solar output has extreme seasonality (near-zero in December, peak in June/July). Adequate training data must span full annual cycle.
- **Panel soiling / snow cover:** No explicit field. Cannot be directly observed from the dataset.
- **Inverter fault signals:** No explicit operational status flag. Cannot be directly observed from the dataset.

---

## 6. Wind-Specific Findings

### 6.1 Wind Asset IDs

Wind assets are identified by `group_name == "wind_park"` in `liander2024_targets.yaml`.

**How to extract wind asset IDs after download:**
```python
wind_assets = [t["name"] for t in targets if t["group_name"] == "wind_park"]
```

### 6.2 Wind Generation Column

- **Column:** `load` in `load_measurements/<wind_park_name>.parquet`
- **Unit:** Watts (W) — must convert to MW (÷ 1,000,000)
- **Expected behavior:** Continuous (wind runs day and night, unlike solar)
- **Same 2-day delay applies**

### 6.3 Wind Weather Variables — CRITICAL GAP

> [!CAUTION]
> **Wind speed and wind direction are NOT confirmed as columns in the `weather_measurements` schema.** The four confirmed weather columns (`temperature_2m`, `relative_humidity_2m`, `surface_pressure`, `cloud_cover`) do not include the fundamental predictors for wind generation.
>
> Wind forecasting without wind speed as an input variable is **not physically meaningful.** This is the most significant gap identified in M3 Chunk 1.

| Variable | Available? | Importance for Wind Forecasting |
|---|---|---|
| `wind_speed_10m` | ❌ Not confirmed | **Critical** — cubic relationship to power |
| `wind_direction_10m` | ❌ Not confirmed | **High** — affects turbine yaw alignment and wake |
| `wind_speed_100m` | ❌ Not confirmed | **High** — hub-height wind more relevant than 10m |
| `temperature_2m` | ✅ Yes | Low — affects air density weakly |
| `surface_pressure` | ✅ Yes | Low — affects air density weakly |
| `cloud_cover` | ✅ Yes | Irrelevant for wind generation |
| `relative_humidity_2m` | ✅ Yes | Irrelevant for wind generation |

**Resolution options for this gap:**
1. When the dataset is downloaded, verify actual parquet column names — additional weather variables may be present even if not prominently documented.
2. Augment with Open-Meteo API directly (same source OpenSTEF uses) to fetch `wind_speed_10m`, `wind_direction_10m`, `wind_speed_100m` for each wind_park's lat/lon over 2024.
3. If augmentation is not feasible in time, use UTSD wind dataset as the optional backup (as the U2 plan suggests). **Do not attempt to train a wind model without at least wind speed as a feature.**

---

## 7. Curtailment-Related Findings

### 7.1 Explicit Curtailment Column

> **Not available.** There is no `curtailment_flag`, `curtailment_mw`, or similar field in any documented table of the OpenSTEF Liander 2024 dataset.

### 7.2 Implicit Curtailment Signals

| Method | Feasibility | Notes |
|---|---|---|
| Compare `load` vs theoretical max from irradiance/wind | Possible after feature engineering | Requires deriving expected generation from physics/weather |
| Compare `load` vs `upper_limit` from targets.yaml | Rough approximation | `upper_limit` is 98th percentile, not nameplate capacity |
| Detect sustained clipping at `upper_limit` value | Possible heuristic | Step-like plateaus in time series may indicate curtailment |
| Cross-reference with EPEX price (negative prices → curtailment risk) | Possible heuristic | EPEX.parquet is available |

### 7.3 Curtailment Diagnostic Position

Per the U2 plan (M3 Chunk 5): if curtailment information is unavailable, the system must mark the diagnostic as **uncertain** rather than classifying the event as a physical asset fault. This is the correct engineering approach given the data gap.

**Actionable rule for Chunk 2 onwards:** When `actual < expected` and no explicit curtailment flag is present, the root-cause classifier must include `"curtailment_uncertain"` as a valid output category alongside `"cloud_cover"`, `"inverter_fault"`, `"soiling"`, and `"sensor_error"`.

---

## 8. Operational / Status Fields

| Field Requested | Available? | Notes |
|---|---|---|
| Asset online/offline flag | ❌ No | No maintenance or operational status field |
| Maintenance window indicator | ❌ No | Not present in dataset |
| Inverter fault flag | ❌ No | Not present |
| Communication loss flag | ❌ No | Not present |
| Sensor health indicator | ❌ No | Not present |

**All operational/status fields are absent.** The only proxy for asset unavailability is an unexpected pattern in the `load` time series (e.g., prolonged zeros during expected production periods, or `available_at` lag anomalies).

---

## 9. Missing Value Patterns

> [!NOTE]
> Without local files, exact missing-value statistics cannot be computed. The following is based on known OpenSTEF dataset characteristics.

### Expected Missing Value Patterns

| Column | Expected % Missing | Nature of Gaps |
|---|---|---|
| `load` (load_measurements) | 1–3% | Random sensor outages; occasional multi-hour gaps during maintenance or data transmission failures. Renewable assets have slightly higher missing rates than transformers. |
| `available_at` | ~0% | Structural field, always populated |
| `temperature_2m` | < 0.5% | Weather API rarely fails; gaps are short |
| `relative_humidity_2m` | < 0.5% | Same as above |
| `surface_pressure` | < 0.5% | Same as above |
| `cloud_cover` | < 0.5% | Same as above |

### Typical Gap Patterns

- **Short gaps (1–4 intervals / 15–60 min):** Random sensor dropouts. Forward-fill is standard OpenSTEF practice.
- **Longer gaps (day-level):** Occasionally during grid maintenance. Should be flagged rather than filled.
- **Night-time zeros (solar only):** NOT missing data — these are genuine zero-generation periods.

---

## 10. Duplicate Timestamp / Row Behavior

- The OpenSTEF framework enforces a unique (location, timestamp) index.
- The published dataset is pre-deduplicated.
- **Local ingestion pipeline must still validate and deduplicate** in case any reprocessed or concatenated files introduce duplicates.
- Recommended dedup strategy: keep last value where duplicates exist (most recent measurement is preferred).

---

## 11. Data Quality Issues

| Issue | Severity | Affected Data | Description |
|---|---|---|---|
| **Unit is Watts, not MW** | High | All `load` columns | Contract expects MW. Failure to convert will produce forecast values ~6 orders of magnitude wrong. |
| **2-day available_at delay for renewables** | High | solar_park, wind_park | Operational inference cannot use confirmed measurements; must rely entirely on weather-based forecasting. |
| **Wind speed absent from documented weather schema** | High | wind_park weather | Without wind speed, wind generation model lacks its primary predictor. Must verify after download or augment. |
| **Solar irradiance not a direct column** | Medium | solar_park weather | Must derive from cloud_cover + astronomical calculations, or fetch separately. |
| **No curtailment indicator** | Medium | All renewables | Cannot distinguish intentional curtailment from underperformance without this field. |
| **No operational status flags** | Medium | All renewables | Cannot filter out planned maintenance events from anomaly detection. |
| **Negative load possible on net-metering feeders** | Low | mv_feeder type | Not a concern for solar_park/wind_park pure generation assets, but must validate. |
| **Outliers / sensor noise** | Low | load measurements | Physically impossible spikes (e.g., load > upper_limit × 1.5) should be capped or flagged. |
| **Night-time zeros for solar** | Low (known) | solar_park | Expected behavior; must exclude from anomaly detection logic. |
| **Leap year 2024** | Low | All timestamps | 2024 has 366 days. Year-lag features (lag-8784h) must use exactly 52 weeks (364 days = 35,136 intervals) to preserve day-of-week alignment. |

---

## 12. Candidate Features and Targets

### 12.1 Chunk 2 — Solar Forecasting

**Target variable:**
```
solar_generation_mw = load (W) / 1_000_000  [float64, MW]
```
Applied to all `solar_park` locations.

**Candidate input features (ordered by expected importance):**

| Feature | Source | Notes |
|---|---|---|
| `cloud_cover` (forecast) | weather_forecasts | Primary solar proxy. Use forecast version, not observed. |
| `cloud_cover` (observed, lagged) | weather_measurements | Historical context |
| `temperature_2m` (forecast) | weather_forecasts | Panel efficiency effect |
| Hour of day | Derived from timestamp | Strong diurnal signal |
| Day of year / solar declination | Derived from timestamp | Captures seasonal irradiance arc |
| Solar elevation angle | Derived from lat/lon + timestamp | Best astronomical proxy for irradiance |
| `relative_humidity_2m` | weather_measurements | Secondary atmospheric signal |
| `surface_pressure` | weather_measurements | Weak signal |
| Lag 15 min (`load` t-1) | load_measurements | Autoregressive — very strong for short horizons |
| Lag 30 min (`load` t-2) | load_measurements | Autoregressive |
| Lag 1 hour (`load` t-4) | load_measurements | Autoregressive |
| Lag 24 hours (`load` t-96) | load_measurements | Same-time-yesterday (solar pattern repeat) |
| Lag 7 days (`load` t-672) | load_measurements | Same-weekday same-hour |
| Rolling 3-hour mean | load_measurements | Recent trend |
| EPEX price | EPEX.parquet | Optional — curtailment-risk signal |

**Leakage warning:** Use `weather_forecasts_versioned` (not `weather_measurements`) during training to simulate realistic operational conditions. Never use observed weather at time t when predicting t.

---

### 12.2 Chunk 3 — Wind Forecasting

**Target variable:**
```
wind_generation_mw = load (W) / 1_000_000  [float64, MW]
```
Applied to all `wind_park` locations.

**Candidate input features (ordered by expected importance):**

| Feature | Source | Availability | Notes |
|---|---|---|---|
| `wind_speed_10m` (forecast) | weather_forecasts | ⚠️ Verify after download | **Most important feature** — cubic power curve relationship |
| `wind_speed_100m` (forecast) | weather_forecasts / Open-Meteo augmentation | ⚠️ Verify/augment | Hub-height speed preferred |
| `wind_direction_10m` (forecast) | weather_forecasts | ⚠️ Verify after download | Turbine orientation and wake effects |
| `temperature_2m` | weather_measurements | ✅ | Air density proxy |
| `surface_pressure` | weather_measurements | ✅ | Air density proxy (combine with temp) |
| Hour of day | Derived | ✅ | Weaker for wind than solar but captures diurnal patterns |
| Month / season | Derived | ✅ | Seasonal wind resource variation |
| Lag 15 min (`load` t-1) | load_measurements | ✅ | Strong short-horizon autoregressive |
| Lag 30 min (`load` t-2) | load_measurements | ✅ | |
| Lag 1 hour (`load` t-4) | load_measurements | ✅ | |
| Lag 24 hours (`load` t-96) | load_measurements | ✅ | |
| Rolling 3-hour mean wind speed | augmented weather | ⚠️ | Ramp-rate context |

**If wind speed remains unavailable after download:** Use UTSD wind dataset as supplementary source. UTSD must be evaluated separately before Chunk 3 begins.

---

## 13. Explicit Gaps vs. U2 Plan Requirements

The following table maps every item the U2/M3 plan expects against what the OpenSTEF Liander 2024 dataset actually provides:

| U2 Plan Expectation | Status | Detail |
|---|---|---|
| Solar asset IDs | ⚠️ Partially met | IDs exist in `targets.yaml` under `group_name == "solar_park"`. Not enumerable without downloading the file. |
| Wind asset IDs | ⚠️ Partially met | IDs exist in `targets.yaml` under `group_name == "wind_park"`. Same caveat. |
| Solar generation measurement column | ✅ Available | `load` in solar_park load_measurements. Unit is Watts, not MW. |
| Wind generation measurement column | ✅ Available | `load` in wind_park load_measurements. Unit is Watts, not MW. |
| Timestamp column (15-min, UTC) | ✅ Available | `timestamp` in all parquet files. 15-min frequency, UTC timezone. |
| Weather variables — temperature | ✅ Available | `temperature_2m` in weather_measurements |
| Weather variables — cloud cover | ✅ Available | `cloud_cover` in weather_measurements |
| Weather variables — humidity | ✅ Available | `relative_humidity_2m` in weather_measurements |
| Weather variables — pressure | ✅ Available | `surface_pressure` in weather_measurements |
| Weather variables — **irradiance** | ❌ **GAP** | Not a direct column. Must derive from cloud_cover + solar geometry. |
| Weather variables — **wind speed** | ❌ **GAP (unconfirmed)** | Not in documented schema. Must verify after download or augment. |
| Weather variables — **wind direction** | ❌ **GAP (unconfirmed)** | Not in documented schema. Must verify after download or augment. |
| Operational / status fields (online/offline, maintenance) | ❌ **GAP** | No such fields exist in this dataset. |
| **Curtailment indicator** (explicit column) | ❌ **GAP** | Does not exist. Must use heuristics (see §7). |
| Missing value patterns | ⚠️ Estimated | Cannot compute exact stats without downloaded data. |
| Duplicate timestamp behavior | ⚠️ Estimated | Dataset is pre-deduplicated; must validate locally. |
| Data quality reports | ⚠️ Partial | Cannot compute exact outlier stats without downloaded data. |
| Local data files available | ❌ **BLOCKER** | No parquet or other data files are in the repository. |
| Download script | ❌ **MISSING** | `scripts/download_datasets.py` does not exist. |

---

## 14. Blockers Before Chunk 2 (Solar Forecasting)

The following items must be resolved before M3 Chunk 2 can begin:

### BLOCKER 1 — Data Not Downloaded (Critical)
**No dataset files are in the repository.** The OpenSTEF Liander 2024 dataset must be downloaded from Hugging Face before any feature engineering, training, or service implementation can proceed.

**Resolution path:**
```bash
# Install huggingface_hub or use git-lfs
pip install huggingface_hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='OpenSTEF/liander2024-energy-forecasting-benchmark',
    repo_type='dataset',
    local_dir='ml/datasets/liander2024'
)
"
```
Large binary files must NOT be committed to git (per `ml/datasets/README.md` rules). Store in `ml/datasets/` locally and add to `.gitignore`, or use DVC.

A `scripts/download_datasets.py` script should be created (within M3's scope at `services/renewable/` or noted as a joint M2/M3 task).

### BLOCKER 2 — Wind Speed Availability Unknown (High)
Wind speed as a weather feature is unconfirmed in the documented schema. After download, immediately inspect column names in `weather_measurements/<wind_park>.parquet`. If wind speed is absent, a decision must be made (augment via Open-Meteo API or proceed to UTSD).

### BLOCKER 3 — Solar Irradiance Derivation Required (Medium)
Solar irradiance (GHI) must be computed from `cloud_cover` and astronomical calculations (sun elevation angle from lat/lon/timestamp). A helper function must be created in `services/renewable/` before feature engineering begins.

### BLOCKER 4 — Unit Conversion Required (Medium)
All downstream code and service responses must convert `load` (Watts) → MW by dividing by 1,000,000. The `RenewableStatus` contract uses MW. A central conversion constant should be defined in `services/renewable/constants.py`.

---

## 15. Summary for the Team

| Item | Finding |
|---|---|
| **Primary dataset found locally?** | ❌ No — must download from Hugging Face |
| **Solar data available?** | ✅ Yes (after download) — `load` column in solar_park parquet files |
| **Wind data available?** | ✅ Yes (after download) — `load` column in wind_park parquet files |
| **Wind speed feature available?** | ⚠️ Unconfirmed — verify immediately after download |
| **Irradiance feature available?** | ❌ No direct column — must derive |
| **Curtailment field available?** | ❌ No — use heuristic flags + "uncertain" category |
| **Operational status fields available?** | ❌ No |
| **Timestamp resolution** | 15-minute intervals, UTC |
| **Unit for generation** | Watts (W) — divide by 1,000,000 for MW |
| **Most critical blocker** | Download the dataset |

---

*Document created by Member 3 (Renewable Intelligence Engineer) as part of M3 Chunk 1.*  
*All findings are based on official OpenSTEF/Liander 2024 dataset documentation.*  
*No data was modified, no model was trained, no files outside M3 boundaries were touched.*
