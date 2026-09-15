# Session 02 — Forecast Design (Member 2)

**Team Member:** Member 2 (Data + Demand Forecasting)  
**Branch:** `deep/data-forecast`  
**Purpose:** Design the demand forecasting pipeline for GridPilot covering baselines, feature engineering, chronological split, metrics, leakage prevention, and model versioning.

---

## Prompt

> Design a demand forecasting pipeline for GridPilot.
> Target: 15, 30 and 60 minute forecasts.
> Primary model: LightGBM.
> Include: baselines, feature engineering, chronological split, metrics, leakage prevention, model versioning.
> Do not modify files.

---

## Pipeline Overview

```
Raw Parquet (OS Edam · load · timestamp · available_at)
    │
    ▼
DemandIngestionPipeline  (services/data/pipeline.py)
    │
    ▼
openstef_demand_clean.parquet  (demand_mw · UTC · 15-min grid)
    │
    ▼
DemandFeaturePipeline.transform  (services/forecasting/features.py)
    │
    ▼
openstef_demand_features.parquet  (37 features · past-only)
    │
    ▼
chronological_split  (70% train · 15% val · 15% test)
    │
    ├──► PersistenceForecaster     (services/forecasting/baselines.py)
    ├──► SeasonalNaiveForecaster   (services/forecasting/baselines.py)
    └──► LightGBMDemandForecaster  (ml/models/demand/trainer.py)
              │
              ▼
         train h=15m / h=30m / h=60m  (early stopping on val MAE)
              │
              ▼
         calculate_metrics  (MAE · RMSE · MAPE per horizon)
              │
              ▼
         compare_with_baselines  (baseline_vs_lightgbm_comparison.json)
              │
              ▼
         save_artifacts  (.joblib + .txt + metadata.json)
              │
              ▼
         ModelLoader  (model_loader.py · in-memory cache)
              │
              ▼
         DemandModelService.forecast_demand  (demand_model.py)
              │
              ▼
         DemandForecast contract  (models.py · shared/contracts)
```

---

## 1. Data Contracts

Raw schema defined in `services/data/config.py`:

| Column | Dtype | Unit | Role |
|---|---|---|---|
| `timestamp` | `datetime64[ns, UTC]` | — | Index |
| `load` | `float64` | Watts | Raw demand |
| `available_at` | `datetime64[ns, UTC]` | — | Telemetry latency guard |

Canonical output of `DemandIngestionPipeline.process()` adds:

| Column | Derivation | Use |
|---|---|---|
| `demand_mw` | `load / 1e6` | **Prediction target** |
| `demand_kw` | `load / 1e3` | Display only, excluded from features |
| `is_imputed` | forward-fill policy | Excluded from features |
| `is_out_of_range` | range check | Excluded from features |
| `is_reverse_flow` | `load < 0` flag | Excluded from features |

---

## 2. Feature Engineering

Implemented in `DemandFeaturePipeline` (`services/forecasting/features.py`), versioned at `1.0.0`. Total: **37 features**.

### 2a. Autoregressive Lags — `_add_lag_features()`

| Feature | Shift | Lookback | Purpose |
|---|---|---|---|
| `demand_mw_lag_15m` | `shift(1)` | 15 min | Most recent reading |
| `demand_mw_lag_30m` | `shift(2)` | 30 min | Short-term momentum |
| `demand_mw_lag_60m` | `shift(4)` | 1 hour | Intra-hour level |
| `demand_mw_lag_1440m` | `shift(96)` | 24 hours | Same-time-yesterday |

### 2b. Rolling Statistics — `_add_rolling_features()`

Applied to `series.shift(1)` — rolling window is **strictly over past rows** [t-w … t-1], never including row t.

| Window (periods) | Wall-clock | Stats computed |
|---|---|---|
| 4 | 1 hour | mean, std, min, max |
| 16 | 4 hours | mean, std, min, max |
| 96 | 24 hours | mean, std, min, max |

→ 12 rolling features total.

### 2c. Momentum Features — `_add_momentum_features()`

| Feature | Formula | Signal |
|---|---|---|
| `demand_mw_diff_15m` | `lag_15m − lag_30m` | 15-min slope |
| `demand_mw_diff_1h` | `lag_15m − lag_60m` | 1-hour acceleration |

Both operands are strictly past lags — no leakage.

### 2d. Calendar Features — `_add_calendar_features()`

**Calendar (9 features):**

| Feature | Encoding | Notes |
|---|---|---|
| `hour` | int 0–23 | LightGBM categorical |
| `day_of_week` | int 0–6 | LightGBM categorical |
| `is_weekend` | binary | 1 if Sat/Sun |
| `is_holiday` | binary | Dutch 2024 holidays via `holidays.py` |
| `season` | int 1–4 | Winter/Spring/Summer/Autumn |
| `sin_hour`, `cos_hour` | cyclical | 24-hour period |
| `sin_dow`, `cos_dow` | cyclical | 7-day period |

**Weather (10 features):**

| Feature | Group | Driver |
|---|---|---|
| `temperature_2m` | Required | Heating / cooling load |
| `relative_humidity_2m` | Required | HVAC comfort |
| `cloud_cover` | Required | Net irradiance proxy |
| `wind_speed_10m` | Required | Wind-chill HVAC |
| `shortwave_radiation` | Required | PV export → net demand |
| `surface_pressure` | Optional | Atmospheric stability |
| `wind_direction_10m` | Optional | Cold-wind fetch |
| `direct_radiation` | Optional | Direct beam |
| `diffuse_radiation` | Optional | Sky scatter |
| `direct_normal_irradiance` | Optional | PV physics |

---

## 3. Chronological Split

Implemented in `chronological_split()` (`services/forecasting/evaluate.py`). **No shuffle, no random state dependency.**

| Split | Ratio | Rows | Date range |
|---|---|---|---|
| Train | 70% | 24,595 | 2024-01-01 → 2024-09-13 04:30 UTC |
| Validation | 15% | 5,270 | 2024-09-13 04:45 → 2024-11-07 02:00 UTC |
| Test | 15% | 5,271 | 2024-11-07 02:15 → 2024-12-31 23:45 UTC |

The test set covers November–December, capturing autumn/winter demand peaks — the hardest distributional regime in the dataset.

Target construction per horizon in `train_and_evaluate()`:

```python
# At row t, target = ground truth at t + periods
train_target = train_df["demand_mw"].shift(-periods)
```

This shift stays within the train partition — validation/test future values are never accessible to the train booster.

---

## 4. Baselines

Implemented in `services/forecasting/baselines.py`.

**Persistence (`PersistenceForecaster`):**
> ŷ(t+h) = y(t) — shift by `h / 15` steps

**Seasonal Naive (`SeasonalNaiveForecaster`):**
> ŷ(t+h) = y(t + h − S), where S = 1440 min = 96 steps (24-hour cycle)

Both evaluated via `evaluate_baselines_on_split()` on the full series — leading test-set rows retain their prior-day lookback without leaking future observations.

---

## 5. LightGBM Primary Model

### Architecture

Three independent boosters, one per horizon:

| Booster key | Target construction | Artifact |
|---|---|---|
| `h=15` | `demand_mw.shift(-1)` | `demand-lgbm-v1_h15min.joblib` |
| `h=30` | `demand_mw.shift(-2)` | `demand-lgbm-v1_h30min.joblib` |
| `h=60` | `demand_mw.shift(-4)` | `demand-lgbm-v1_h60min.joblib` |

### Hyperparameters (`LightGBMTrainingConfig`)

| Parameter | Value | Rationale |
|---|---|---|
| `objective` | `regression` | MAE-adjacent regression loss |
| `metric` | `mae` | Matches primary evaluation metric |
| `learning_rate` | `0.05` | Conservative; offset by 500 rounds |
| `num_leaves` | `31` | Balanced depth/variance |
| `min_data_in_leaf` | `20` | Prevents overfitting on rare patterns |
| `feature_fraction` | `0.9` | Mild feature subsampling |
| `bagging_fraction / freq` | `0.9 / 5` | Row subsampling for regularization |
| `num_boost_round` | `500` | Max iterations with early stop |
| `early_stopping_rounds` | `30` | Stop when val MAE plateaus |
| `seed` | `42` | Reproducible |

### Confidence Intervals

In `DemandModelService.forecast_demand()`:

```python
lower_bound = max(0.0, pred_mw - 1.96 * horizon_rmse[h])
upper_bound = pred_mw + 1.96 * horizon_rmse[h]
```

Gaussian 95% interval using per-horizon test-set RMSE as spread parameter. Suitable for v1 — should be replaced with quantile regression in future.

---

## 6. Metrics

Computed by `calculate_metrics()` (`services/forecasting/evaluate.py`). NaN pairs excluded; MAPE excludes `|y_true| ≤ 1e-4`.

### Achieved Results

| Horizon | Model | MAE (MW) | RMSE (MW) | MAPE (%) | n |
|---|---|---|---|---|---|
| 15 min | **Persistence** | **0.0382** | 0.0673 | 12.25 | 5,271 |
| 15 min | LightGBM | 0.0497 | 0.0829 | 14.27 | 5,270 |
| 15 min | Seasonal Naive | 0.1266 | 0.1976 | 37.63 | 5,271 |
| 30 min | **LightGBM** | **0.0617** | **0.0972** | **17.79** | 5,269 |
| 30 min | Persistence | 0.0631 | 0.0996 | 19.09 | 5,271 |
| 30 min | Seasonal Naive | 0.1266 | 0.1976 | 37.63 | 5,271 |
| 60 min | **LightGBM** | **0.0846** | **0.1257** | **21.81** | 5,267 |
| 60 min | Persistence | 0.1056 | 0.1492 | 29.99 | 5,271 |
| 60 min | Seasonal Naive | 0.1266 | 0.1976 | 37.63 | 5,271 |

**Key finding:** Persistence wins at 15 min (MAE 0.038 vs 0.050). LightGBM takes over decisively at 30 min and 60 min — the operationally meaningful dispatch horizons.

---

## 7. Leakage Prevention

| Control | Implementation | Verified |
|---|---|---|
| Rolling window excludes row t | `series.shift(1).rolling(w)` in `_add_rolling_features()` | ✅ |
| Lag shift ≥ 1 | Minimum lag 15 min = `shift(1)` in `_add_lag_features()` | ✅ |
| Target created by forward shift | `demand_mw.shift(-periods)` inside train partition only | ✅ |
| Spike threshold derived from train only | `derive_labeling_rule()` receives only `train_df` | ✅ |
| Audit cols excluded from feature matrix | `non_feature_cols` set in `transform()` | ✅ |
| Baseline evaluation uses full-series shift | `evaluate_baselines_on_split()` shifts over full series, reads only test slice | ✅ |
| Chronological split — no shuffle | `sort_values(timestamp)` then integer index cuts | ✅ |
| `available_at` excluded | In `non_feature_cols` in `transform()` | ✅ |

---

## 8. Model Versioning

### Artefact Layer (`save_artifacts()`)

```
ml/models/demand/
  demand-lgbm-v1_h15min.joblib
  demand-lgbm-v1_h15min.txt
  demand-lgbm-v1_h30min.{joblib,txt}
  demand-lgbm-v1_h60min.{joblib,txt}
  demand-lgbm-v1_training_metadata.json
  demand-lgbm-v1_test_metrics.csv
  demand_lgbm.pkl   ← DemandLGBMModel bundle (all horizons)
```

### Metadata Layer

`demand-lgbm-v1_training_metadata.json` contains: `model_version`, `feature_version`, `hyperparameters`, `feature_names`, `split_info`, per-horizon `val_metrics` + `test_metrics`, `best_iteration`, `training_seconds`.

### Service Layer

`model_version = "demand-lgbm-v1"` is stamped on every `DemandForecast` response in the `modelVersion` field. Feature pipeline versioned independently via `FEATURE_PIPELINE_VERSION = "1.0.0"`.

---

## 9. Inference Path

```
DemandModelService.forecast_demand()
    │
    ├─ validate zone_id, horizon ∈ {15, 30, 60}
    ├─ require ≥ 96 steps history (InsufficientHistoryError)
    ├─ build_demand_features(prior_history, weather_forecast)
    │     └─ DemandFeaturePipeline.transform()   ← same code as training
    ├─ lgbm_model.predict(X_latest, horizon=h)   ← per-horizon booster
    ├─ CI = pred ± 1.96 × horizon_rmse[h]
    ├─ SpikeModelService.evaluate_telemetry()    ← XGBoost classifier
    └─ return DemandForecast(points, spikeRisk, modelVersion)
```

The inference path calls the **identical** `DemandFeaturePipeline.transform()` used at training time — training–serving skew is eliminated by design.

---

## 10. Open Issues & Recommended Next Steps

| Priority | Issue | Recommendation |
|---|---|---|
| **High** | 15-min persistence beats LightGBM | Use persistence for h=15 in production; LightGBM for h=30 and h=60 |
| **High** | CI uses Gaussian RMSE — calibration not measured | Replace with quantile LightGBM objectives (`0.025` / `0.975`) |
| **Medium** | Weather NaN imputation missing | Add forward-fill (≤4 intervals) for weather cols in `transform()` with warning |
| **Medium** | No same-week lag (`lag_10080m`) | Add to `FeatureConfig.lag_minutes` |
| **Medium** | Validation MAPE inflated (39–50%) | Investigate autumn 2024 load events; separate MAPE on non-reverse-flow rows |
| **Low** | `demand_lgbm.pkl` bundles all horizons | Switch to three separate instances with independent `force_reload` |
| **Low** | `available_at` not used at inference | Add point-in-time filter: reject rows where `available_at > now()` |
