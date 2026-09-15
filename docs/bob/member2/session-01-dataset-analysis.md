# Session 01 — Dataset Analysis (Member 2)

**Team Member:** Member 2 (Data + Demand Forecasting)  
**Branch:** `deep/data-forecast`  
**Purpose:** Analyse the demand-related portion of the OpenSTEF dataset. Identify fields, frequency, weather features, missing-data risks, leakage risks, and candidate lag features. Return a data-preparation plan.

---

## Prompt

> Analyze the demand-related portion of the OpenSTEF dataset in the project.
> Do not modify files.
> Identify: demand fields, timestamp field, frequency, weather features, missing-data risks, leakage risks, candidate lag features.
> Return a data-preparation plan.

---

## Source Files Examined

| Artefact | Path |
|---|---|
| Raw parquet | `ml/datasets/raw/mv_feeder/OS Edam.parquet` |
| Clean canonical | `ml/datasets/openstef_demand_clean.parquet` |
| Feature store | `ml/datasets/openstef_demand_features.parquet` |
| Weather source | `ml/datasets/raw/weather_mv_feeder_OS Edam.parquet` |
| Quality report | `ml/datasets/data_quality_report.json` |
| Feature metadata | `ml/datasets/feature_metadata.json` |

---

## Demand Fields

| Column | Type | Notes |
|---|---|---|
| `load` | `float64` (Watts) | Raw demand — single native field from OpenSTEF schema |
| `demand_mw` | `float64` (MW) | Canonical target: `load / 1e6`, derived in `pipeline.py` |
| `demand_kw` | `float64` (kW) | Convenience: `load / 1e3` |
| `is_imputed` | `bool` | Audit flag — `True` for forward-filled intervals |
| `is_out_of_range` | `bool` | Physical plausibility flag |
| `is_reverse_flow` | `bool` | Set when `load < 0` |

The **prediction target** for all models is `demand_mw`.

---

## Timestamp Field

| Property | Value |
|---|---|
| Column name | `timestamp` (plus `available_at` for telemetry latency) |
| Dtype | `datetime64[ns, UTC]` |
| Timezone | UTC — enforced by `IngestionConfig.expected_timezone` |
| Range | 2024-01-01 00:00 UTC → 2024-12-31 23:45 UTC |
| Monotonic | ✅ confirmed in `data_quality_report.json` |
| `available_at` | Records when the data point became available; enables point-in-time correctness checks |

---

## Frequency

- **15-minute intervals** (`15min`) — declared in `IngestionConfig.expected_freq`
- 35,136 total rows = 365 days × 96 intervals/day — 100% complete grid, zero gaps
- Chronological splits: 70% train / 15% val / 15% test (cut at 2024-09-13 and 2024-11-07)

---

## Weather Features

Sourced from OpenMeteo, joined on `timestamp`, split into required and optional groups in `FeatureConfig`:

| Group | Feature | Relevance to Demand |
|---|---|---|
| **Required** | `temperature_2m` | Heating/cooling load driver |
| **Required** | `relative_humidity_2m` | Comfort HVAC proxy |
| **Required** | `cloud_cover` | Irradiance proxy, indirect load effect |
| **Required** | `wind_speed_10m` | Wind chill / HVAC |
| **Required** | `shortwave_radiation` | Solar irradiance (PV export → net demand) |
| **Optional** | `surface_pressure` | Atmospheric stability |
| **Optional** | `wind_direction_10m` | Cold-wind fetch direction |
| **Optional** | `direct_radiation` | Direct beam component |
| **Optional** | `diffuse_radiation` | Diffuse sky component |
| **Optional** | `direct_normal_irradiance` | Solar panel physics |

Weather data is joined via a **left merge on `timestamp`** in `DemandFeaturePipeline.transform()`, so missing weather rows silently produce `NaN` in feature columns.

---

## Missing-Data Risks

| Risk | Detail | Policy in Code |
|---|---|---|
| **Demand NaNs** | 3 rows missing at 2024-10-27 00:15–00:45 UTC (DST clock-back ambiguity) | `FORWARD_FILL_MAX_GAP` with `max_gap = 4` intervals (1 hour); tracked via `is_imputed` in `policies.py` |
| **Reverse flow** | 5,896 rows (16.78%) have `load < 0` — prosumer net export | Flagged `is_reverse_flow`; **not dropped**; MAPE metrics are distorted by near-zero denominators |
| **Weather join gaps** | Weather Parquet may not cover every 15-min demand timestamp | Left merge produces `NaN` weather features; no imputation coded for weather columns — **gap in current pipeline** |
| **Feature warm-up NaNs** | 96-period rolling window requires 96 prior rows (24h) | First ~100 rows will have NaN lag/rolling features; must be dropped before training |
| **Multi-asset gaps** | `available_at` lag may vary by meter | Currently unused after ingestion |

---

## Leakage Risks

| Risk | Status | Location |
|---|---|---|
| **Rolling window on current row** | ✅ Mitigated — rolling applied to `series.shift(1)` | `_add_rolling_features()` in `features.py` |
| **Lag shift ≥ 1** | ✅ Mitigated — minimum lag 15 min = `shift(1)` | `_add_lag_features()` in `features.py` |
| **Spike label uses future** | ⚠️ Requires strict split discipline | `spike_labeling.py` — labels derived only from `train_df` |
| **Weather temporal alignment** | ⚠️ Risk if forecast weather used at train time | `available_at` not used for weather join |
| **`demand_kw` and `load` as features** | ✅ Excluded | In `non_feature_cols` set in `transform()` |
| **`is_imputed` / audit cols as features** | ✅ Excluded | In `non_feature_cols` set in `transform()` |

---

## Candidate Lag Features

| Feature | Formula | Lookback | Rationale |
|---|---|---|---|
| `demand_mw_lag_15m` | `shift(1)` | 15 min | Most recent reading |
| `demand_mw_lag_30m` | `shift(2)` | 30 min | Short-term trend |
| `demand_mw_lag_60m` | `shift(4)` | 1 hour | Intra-hour pattern |
| `demand_mw_lag_1440m` | `shift(96)` | 24 hours | Same-time-yesterday baseline |
| `demand_mw_roll_mean_{4,16,96}` | rolling mean on shifted series | 1h / 4h / 24h | Smoothed level |
| `demand_mw_roll_std_{4,16,96}` | rolling std on shifted series | 1h / 4h / 24h | Volatility / spike risk |
| `demand_mw_roll_min/max_{4,16,96}` | rolling min/max | 1h / 4h / 24h | Envelope / regime |
| `demand_mw_diff_15m` | `lag_15m − lag_30m` | — | 15-min slope |
| `demand_mw_diff_1h` | `lag_15m − lag_60m` | — | 1-hour acceleration |

**Recommended additions not yet implemented:**
- `demand_mw_lag_10080m` (168h = same time last week) — weekly seasonality
- `demand_mw_roll_std_288` (3-day volatility) — better spike risk signal
- Weather × time interaction (e.g. `temperature_2m × is_weekend`)

---

## Data-Preparation Plan

### Phase 0 — Already Complete

- ✅ Raw → canonical ingestion via `DemandIngestionPipeline`
- ✅ Forward-fill policy for DST gap (3 rows, flagged)
- ✅ Duplicate/gap/range checks pass (100% retention)
- ✅ Feature engineering v1.0.0 (37 features) in `services/forecasting/features.py`
- ✅ Chronological 70/15/15 split preserved in training metadata
- ✅ Lag leakage prevention verified in code

### Phase 1 — Validation Actions

- [ ] Profile weather parquet temporal coverage — confirm every demand timestamp has a weather row; quantify NaN rate per weather column after left merge
- [ ] Quantify warm-up NaN budget — first 96 rows per asset must be excluded from training
- [ ] Audit spike-label temporal boundary — verify `derive_labeling_rule()` is called only on the 70% train split
- [ ] Check `available_at` lag distribution — flag any rows where lag exceeds the 15-min horizon

### Phase 2 — Controlled Additions

- [ ] Add `lag_10080m` (same-time last week) to `FeatureConfig.lag_minutes`
- [ ] Add `demand_mw_roll_std_288` (3-day volatility window)
- [ ] Add weather NaN imputation step in `transform()` — forward-fill ≤4 periods with warning
- [ ] Add point-in-time filter using `available_at` at inference time

### Phase 3 — Spike Classifier Preparation

- [ ] Confirm class imbalance handling — class 0 = 95%, class 1 = 4%, class 2 = 1%
- [ ] Confirm spike features match demand forecast features exactly across both serialised models

---

## Key Facts Summary

| Property | Value |
|---|---|
| Asset | OS Edam (MV feeder, Liander DSO) |
| Period | 2024-01-01 → 2024-12-31 (full year, UTC) |
| Rows | 35,136 (zero gaps, zero dropped) |
| Frequency | 15-min uniform grid |
| Target | `demand_mw` = `load` / 1×10⁶ |
| Reverse flow rows | 5,896 (16.78%) — valid prosumer export |
| Weather features | 10 total (5 required, 5 optional) via OpenMeteo |
| Feature count | 37 (10 weather + 4 lag + 12 rolling + 2 diff + 9 calendar) |
| Warm-up rows | ~96 (24h) at dataset start |
| Max fill gap | 4 intervals (1 hour) — forward fill only |
| Spike classes | 0=normal (95%), 1=moderate (4%), 2=severe (1%) |
| Models in place | LightGBM @ 15m/30m/60m + XGBoost spike classifier |
