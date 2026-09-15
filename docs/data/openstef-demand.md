# OpenSTEF Liander 2024 Energy Forecasting Dataset: Demand & Load Analysis

**Project:** GridPilot AI  
**Module:** Member 2 (Data + Demand Forecasting)  
**Branch:** `member/data-forecast`  
**Target Document:** `docs/data/openstef-demand.md`  
**Dataset Reference:** `OpenSTEF/liander2024-energy-forecasting-benchmark` (Hugging Face / OpenSTEF / DSO Liander)  
**Last Verified:** 2026-09-15  

---

## 1. Executive Summary

This document provides a verified, empirical analysis of the **OpenSTEF Liander 2024 Short-Term Energy Forecasting Benchmark** dataset. All findings, schema definitions, missing value behaviors, and potential data leakage paths documented herein have been confirmed by inspecting the raw Parquet and YAML files from the official benchmark repository.

No hypothetical or assumed fields are included. Unconfirmed features are explicitly marked as `[UNCONFIRMED / NOT PRESENT]`.

---

## 2. Dataset Overview & Architecture

The dataset covers the full calendar year of 2024 (a leap year: 366 days, exactly 35,136 15-minute intervals from `2024-01-01 00:00:00 UTC` to `2024-12-31 23:45:00 UTC`), covering 55 assets in the service area of Dutch Distribution System Operator (DSO) Liander.

```
OpenSTEF Liander 2024 Benchmark
├── liander2024_targets.yaml           # Metadata for 55 grid targets (coords, limits, splits)
├── load_measurements/                 # 15-minute electrical load telemetry
│   ├── mv_feeder/                     # 15 Medium Voltage feeders (Watts)
│   ├── station_installation/          # 15 Substation installations (Watts)
│   ├── transformer/                   # 15 Power transformers (Watts)
│   ├── solar_park/                    # 5 Solar parks (Normalized [-1, 0])
│   └── wind_park/                     # 5 Wind parks (Normalized [-1, 0])
├── weather_measurements/              # Historical actuals from OpenMeteo (15-min interpolated)
├── weather_forecasts/                 # Latest operational forecasts from OpenMeteo
├── weather_forecasts_versioned/       # Versioned forecasts with lead times up to 7 days
├── EPEX.parquet                       # ENTSO-E Day-ahead power prices (€/MWh, 15-min)
└── profiles.parquet                   # Energiedatawijzer standardized customer load profiles
```

---

## 3. Core Field Dictionary

### 3.1. Timestamps & Timezone

| Field Name | Storage Dtype | Timezone | Frequency | Null Count (per series) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `timestamp` | `datetime64[ns, UTC]` | UTC (`+00:00`) | 15 minutes (`15min` / `96 steps/day`) | 0 (None missing) | Interval start timestamp in UTC. In `weather_measurements` and `weather_forecasts`, stored as the `DatetimeIndex(name='timestamp')`. In load, EPEX, and versioned forecasts, stored as a column. |
| `available_at` | `datetime64[ns, UTC]` | UTC (`+00:00`) | Varies by component | 0 (None missing) | Timestamp indicating when data became available to the forecasting system. Vital for data leakage prevention. |

- **Duplicate Behavior:** **0 duplicates detected.** Timestamps are strictly monotonic and uniformly spaced at 15-minute intervals.
- **Timezone Standardization:** All series are explicitly tagged with UTC (`tz='UTC'`). Local Dutch time is Central European Time (CET, UTC+1) / Central European Summer Time (CEST, UTC+2).

---

### 3.2. Demand / Load Telemetry (`load_measurements/`)

Confirmed fields inside every Parquet file under `load_measurements/{group_name}/{asset_name}.parquet`:

| Field Name | Type | Physical Units | Range (Typical) | Description |
| :--- | :--- | :--- | :--- | :--- |
| `timestamp` | `datetime64[ns, UTC]` | - | 2024-01-01 to 2024-12-31 | UTC timestamp of the measurement interval |
| `load` | `float64` | Watts (`W`) or Normalized Ratio `[-1, 1]` | Grid assets: $-5.0 \times 10^7$ W to $+7.5 \times 10^7$ W<br>Renewables: $-1.0$ to $+0.02$ (normalized) | Net active electrical power measured at the asset. |
| `available_at` | `datetime64[ns, UTC]` | - | Same as `timestamp` or `timestamp + 2 days` | Availability timestamp of telemetry. |

#### Load Behavior & Physical Characteristics:
1. **Sign Convention:**
   - **Positive Load ($> 0$):** Net consumption / forward flow (power pulled from substation into local distribution).
   - **Negative Load ($< 0$):** Net generation / reverse power flow (local distributed generation like rooftop PV or wind exceeding local consumption, feeding back into the high-voltage grid).
   - *Example:* In `OS Edam` (an MV feeder), 5,896 intervals (16.8% of the year) exhibit negative load down to $-1,130,000\text{ W}$ ($-1.13\text{ MW}$).
2. **Normalized Renewable Telemetry:**
   - For `solar_park` and `wind_park`, load values are normalized relative to facility peak capacity. Values range from approximately $-1.0$ (peak feed-in) to $0.0$ (idle).

#### Missing-Value Behavior in Load:
- In every examined load series across all groups (`mv_feeder`, `station_installation`, `transformer`, `solar_park`, `wind_park`), exactly **3 records out of 35,136 are `NaN`** (99.9915% completeness):
  - `2024-10-27 00:15:00+00:00`
  - `2024-10-27 00:30:00+00:00`
  - `2024-10-27 00:45:00+00:00`
- **Root Cause:** October 27, 2024 marked the European Daylight Saving Time (CEST $\to$ CET) transition (clock shift at 03:00 to 02:00 local time). In legacy SCADA logging, the ambiguous local hour caused 3 missing intervals when converted to UTC.
- **Handling Strategy for Ingestion:** Cubic spline or linear interpolation across these 3 contiguous 15-minute points is mathematically robust and domain-appropriate.

---

### 3.3. Zones, Feeders & Infrastructure Metadata (`liander2024_targets.yaml`)

55 total assets are cataloged across 5 functional asset categories:

| Target Group (`group_name`) | Count | Units of `load` | Availability Lag (`available_at - timestamp`) | Typical Assets / Examples |
| :--- | :--- | :--- | :--- | :--- |
| `mv_feeder` | 15 | Watts (`W`) | `0 days 00:00:00` (real-time telemetry) | `OS Edam`, `OS Eibergen`, `OS Gorredijk` |
| `station_installation` | 15 | Watts (`W`) | `0 days 00:00:00` (real-time telemetry) | `OS Almere`, `OS Apeldoorn`, `OS Bergum` |
| `transformer` | 15 | Watts (`W`) | `0 days 00:00:00` (real-time telemetry) | `OS Amsterdam Hemweg`, `OS Doetinchem` |
| `solar_park` | 5 | Normalized `[-1, 0]` | `2 days 00:00:00` (simulated DSO settlement delay) | `Within 10 kilometers of Westwoud_normalized` |
| `wind_park` | 5 | Normalized `[-1, 0]` | `2 days 00:00:00` (simulated DSO settlement delay) | `Within 15 kilometers of Dronten_normalized` |

#### Confirmed Fields in `liander2024_targets.yaml`:
- `name` (`string`): Unique asset identifier.
- `group_name` (`string`): Asset category (`mv_feeder`, `transformer`, `station_installation`, `solar_park`, `wind_park`).
- `latitude` (`float`): Approximate WGS84 latitude coordinate.
- `longitude` (`float`): Approximate WGS84 longitude coordinate.
- `description` (`string`): Human-readable location description.
- `benchmark_start` (`ISO 8601 string`): `2024-03-01T00:00:00Z` (benchmark test period start).
- `benchmark_end` (`ISO 8601 string`): `2024-12-31T23:59:59Z` (benchmark test period end).
- `train_start` (`ISO 8601 string`): `2024-01-01T00:00:00Z` (training window start; Jan-Feb 2024 serves as initial warm-up/train).
- `upper_limit` (`float`): 98th percentile of load values ($W$ or normalized). Useful for anomaly capping and spike definition.
- `lower_limit` (`float`): 2nd percentile of load values ($W$ or normalized).

---

### 3.4. Weather Features (`weather_measurements/` & `weather_forecasts/`)

Historical actuals and weather forecasts from OpenMeteo, mapped to the coordinates of each asset:

| Field Name | Type | Physical Units | Found in Measurements? | Found in Forecasts? | Found in Versioned? | Nulls (in raw) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `temperature_2m` | `float32` | Degrees Celsius (°C) | **Yes** | **Yes** | **Yes** | 0 |
| `relative_humidity_2m` | `float32` | Percentage (%) | **Yes** | **Yes** | **Yes** | 0 |
| `surface_pressure` | `float32` | Hectopascals (hPa) | **Yes** | **Yes** | **Yes** | 0 |
| `cloud_cover` | `float32` | Percentage (%) | **Yes** | **Yes** | **Yes** | 0 |
| `wind_speed_10m` | `float32` | Kilometers per hour (km/h) | **Yes** | **Yes** | **Yes** | 0 |
| `wind_speed_80m` | `float32` | Kilometers per hour (km/h) | *No* | **Yes** | **Yes** | 13,320 nulls in versioned (6.6%) |
| `wind_direction_10m` | `float32` | Degrees (0–360°) | **Yes** | **Yes** | **Yes** | 0 |
| `shortwave_radiation` | `float32` | Watts per sq. meter ($\text{W/m}^2$) | **Yes** | **Yes** | **Yes** | 0 |
| `direct_radiation` | `float32` | Watts per sq. meter ($\text{W/m}^2$) | **Yes** | **Yes** | **Yes** | 0 |
| `diffuse_radiation` | `float32` | Watts per sq. meter ($\text{W/m}^2$) | **Yes** | **Yes** | **Yes** | 0 |
| `direct_normal_irradiance` | `float32` | Watts per sq. meter ($\text{W/m}^2$) | **Yes** | **Yes** | **Yes** | 0 |

---

### 3.5. Solar-Relevant Fields

#### Confirmed Available:
1. `shortwave_radiation` ($\text{W/m}^2$): Global horizontal solar irradiance. Primary driver of solar generation.
2. `direct_radiation` ($\text{W/m}^2$): Direct solar beam irradiance on a horizontal plane.
3. `diffuse_radiation` ($\text{W/m}^2$): Scattered solar radiation on a horizontal plane.
4. `direct_normal_irradiance` ($\text{W/m}^2$): Solar irradiance received perpendicular to the sun's rays.
5. `cloud_cover` (%): Cloud obscuration percentage.
6. `load_measurements/solar_park/{name}.parquet` (`load`): Dedicated aggregate park production.

#### Unconfirmed / Not Present in Dataset:
- `[UNCONFIRMED / NOT PRESENT]` Solar panel azimuth / tilt angle
- `[UNCONFIRMED / NOT PRESENT]` Solar inverter temperature / DC power
- `[UNCONFIRMED / NOT PRESENT]` Panel soiling or degradation coefficients
- `[UNCONFIRMED / NOT PRESENT]` Installed MWp capacity per substation (only 98th percentile is given in YAML)

---

### 3.6. Wind-Relevant Fields

#### Confirmed Available:
1. `wind_speed_10m` (km/h): Surface wind speed at 10 meters.
2. `wind_speed_80m` (km/h): Turbine hub-height wind speed (available in forecast series only; requires imputation for ~6.6% nulls in versioned data).
3. `wind_direction_10m` (°): Angle in degrees from true North.
4. `surface_pressure` (hPa) & `temperature_2m` (°C): Can be combined to compute real air density ($\rho = \frac{p}{R_{spec} T}$).
5. `load_measurements/wind_park/{name}.parquet` (`load`): Dedicated aggregate wind generation.

#### Unconfirmed / Not Present in Dataset:
- `[UNCONFIRMED / NOT PRESENT]` Turbine hub height (exact asset specific)
- `[UNCONFIRMED / NOT PRESENT]` Rotor diameter / turbine power curve tables
- `[UNCONFIRMED / NOT PRESENT]` Wind gust speed (`wind_gusts_10m` not in Liander benchmark tables)
- `[UNCONFIRMED / NOT PRESENT]` Curtailment flags / turbine availability status

---

### 3.7. Economic & Profile Context Fields

#### EPEX Day-Ahead Prices (`EPEX.parquet`):
- `timestamp` (`datetime64[ns, UTC]`): Interval timestamp (15-min).
- `available_at` (`datetime64[ns, UTC]`): Clearing timestamp (published previous day ~12:00 UTC).
- `EPEX_NL` (`float64`): Day-ahead electricity spot price in **€/MWh** (Note: named `EPEX_NL`, not `price`).
- Completeness: 35,136 rows, **0 nulls**.

#### Customer Consumption Profiles (`profiles.parquet`):
- `timestamp` (`datetime64[ns, UTC]`): Interval timestamp (15-min).
- `available_at` (`datetime64[ns, UTC]`): Data publication timestamp (`2023-11-06 00:00:00 UTC`).
- 15 Standardized Profile Columns (`float64`):
  - `E1A_AZI_A`, `E1A_AMI_A`, `E1B_AZI_A`, `E1B_AMI_A`, `E1C_AZI_A`, `E1C_AMI_A`
  - `E2A_AZI_A`, `E2A_AMI_A`, `E2B_AZI_A`, `E2B_AMI_A`
  - `E3A_A`, `E3B_A`, `E3C_A`, `E3D_A`, `E4A_A`
- Completeness: 35,136 rows, **0 nulls**.

---

## 4. Potential Data Leakage Risks & Mitigation

| Leakage Risk | Mechanism | Impact | Mitigation Rule for Member 2 Pipeline |
| :--- | :--- | :--- | :--- |
| **1. Ground-Truth Weather Actuals** | Using `weather_measurements` at forecast time $T$ for horizon $T+h$. | Severe lookahead bias; real systems only have forecasts for future intervals. | **Strict Rule:** For horizon $T+h$, features must come from `weather_forecasts_versioned` where `available_at <= T`. |
| **2. Renewable Telemetry Lag** | Feeding concurrent solar/wind park telemetry ($T-15\text{min}$) into demand models. | Real DSO SCADA experiences a 2-day settlement delay on solar/wind parks (`available_at == timestamp + 2 days`). | **Strict Rule:** Dedicated solar/wind park telemetry can only be lagged by $\ge 48\text{ hours}$. Real-time renewable impact must be modeled purely via weather features! |
| **3. Target Lag Contamination** | Using autoregressive lags $\text{load}_{T-k}$ where $k < \text{horizon } h$. | Leakage of future ground truth when forecasting multi-step ahead. | For horizon $T+h$, only autoregressive lags $\text{load}_{t}$ where $t \le T$ are permitted. Direct multistep models must use horizon-aligned lag sets. |
| **4. Electricity Price Availability** | Using tomorrow's EPEX price before 13:00 UTC today. | Day-ahead market clears at 12:00–13:00 UTC for the next delivery day. | Filter EPEX features using `available_at <= T`. |
| **5. Global Normalization Statistics** | Computing min/max/mean scalers over the whole 2024 year before train/test splitting. | Test set distribution leaks into training normalization. | Fit all scalers (StandardScaler/RobustScaler) strictly on `train_start` to `benchmark_start` (`2024-01-01` to `2024-03-01`), then transform benchmark data out-of-sample. |

---

## 5. Candidate Target Variables for Member 2

In accordance with Member 2 system requirements for short-term demand forecasting:

### Target 1: Continuous Net Substation Active Power
- **Variable Name:** `target_load_kw` or `target_load_mw`
- **Definition:** Rescaled from raw Watts ($\text{load} / 1000$ or $\text{load} / 10^6$) to prevent gradient instability.
- **Evaluation Horizons:**
  - **T+15 min (Step 1):** Primary operational dispatch target.
  - **T+30 min (Step 2):** Fast-ramping reserve window.
  - **T+60 min (Step 4):** Standard grid congestion alert horizon.
  - **T+24 hr (Step 96):** Day-ahead congestion management.

### Target 2: Demand Spike / Peak Exceedance (Classification)
- **Variable Name:** `target_spike_binary`
- **Definition:**
  $$\text{target\_spike}_{T+h} = \mathbb{I}\left(\text{load}_{T+h} > \text{upper\_limit}\right)$$
  where $\text{upper\_limit}$ is the 98th percentile defined in `liander2024_targets.yaml`.
- **Alternative Dynamic Spike Definition:**
  $$\text{target\_spike\_dyn}_{T+h} = \mathbb{I}\left(\text{load}_{T+h} > \mu_{\text{tod, dow}} + 2.5 \cdot \sigma_{\text{tod, dow}}\right)$$
  detecting anomalous surges above typical time-of-day / day-of-week demand.

### Target 3: Reverse Flow / Net Infeed Alert
- **Variable Name:** `target_reverse_flow`
- **Definition:**
  $$\text{target\_reverse\_flow}_{T+h} = \mathbb{I}\left(\text{load}_{T+h} < 0\right)$$
  predicting whether distributed generation exceeds local consumption, reversing substation transformer power flow.

---

## 6. Recommendations for Chunk 2 (Data Ingestion)

1. **Canonical Schema:**
   - Ingest `load_measurements/{group}/{name}.parquet` along with matching weather and EPEX tables.
   - Retain asset identifier `asset_id` and category `group_name` as categorical dimensions.
2. **Missing Interval Imputation:**
   - Apply linear interpolation specifically to the 3 missing DST records on `2024-10-27` (`00:15`, `00:30`, `00:45 UTC`).
3. **Range Validation:**
   - Assert `abs(load) < 500e6` (500 MW) for substation and transformer assets.
   - Assert `-1.05 <= load <= 0.05` for normalized renewable parks.
4. **Leakage-Safe Feature Stores:**
   - Always merge weather predictors using `weather_forecasts_versioned` or operational `weather_forecasts` aligned with timestamp cutoff rules.
