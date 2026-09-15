# Session 04 — Leakage Review (Member 2)

**Team Member:** Member 2 (Data + Demand Forecasting)  
**Branch:** `deep/data-forecast`  
**Purpose:** Review the current demand forecasting pipeline for data leakage across lag alignment, rolling windows, train/validation/test boundaries, future weather information, target leakage, and timestamp issues.

---

## Prompt

> Review the current demand forecasting pipeline for data leakage.
> Check: lag alignment, rolling windows, train/validation/test boundaries, future weather information, target leakage, timestamp issues.
> Do not modify code.
> Return confirmed issues and severity.

---

## Area 1 — Lag Alignment

**Status: ✅ CLEAN**

In `_add_lag_features()` (`services/forecasting/features.py`):

```python
steps = int(lag_min / freq)          # 15→1, 30→2, 60→4, 1440→96
df[col_name] = df[target].shift(steps)
```

Minimum shift is 1. At row `t`, `lag_15m[t] = demand_mw[t-1]`. Row `t` is never used to produce any lag feature for row `t`. Confirmed by `test_lag_values_never_reference_current_or_future_row` in the test suite.

**No issue.**

---

## Area 2 — Rolling Windows

**Status: ⚠️ ONE LOW-SEVERITY ISSUE — `bfill()` on spike `historical_peak_24h`**

### Rolling windows on the LightGBM path: ✅ CLEAN

`_add_rolling_features()` applies rolling to `series.shift(1)`:

```python
shifted_target = df[target].shift(1)
df[col_name] = shifted_target.rolling(w).mean()
```

At row `t`, window covers `[t-w … t-1]` — row `t` is never in scope. Confirmed by `test_rolling_mean_excludes_current_row`.

### Rolling window on the spike classifier path: ⚠️ LOW

In `DemandSpikeClassifier.build_spike_features()` (`ml/models/demand/spike_trainer.py`):

```python
df["historical_peak_24h"] = (
    df["demand_mw"].shift(1).rolling(window=96, min_periods=4).max().bfill()
)
```

The `shift(1).rolling(96)` part is correct. However, the appended **`.bfill()`** fills the leading NaN rows (rows 0–3, where `min_periods=4` is not yet met) with the first non-NaN value that comes **later in the series**. Rows 0–3 therefore receive a `historical_peak_24h` derived from future rows (rows 4+).

**Severity: LOW** — does not affect training/test metrics given the 35,136-row dataset; affects only the first 3 rows of any new asset window at inference time.

---

## Area 3 — Train/Validation/Test Boundaries

**Status: ✅ CLEAN**

`chronological_split()` (`services/forecasting/evaluate.py`):

```python
df = df.sort_values(timestamp_col).reset_index(drop=True)
train_end_idx = int(n * train_ratio)           # 0.70
val_end_idx   = int(n * (train_ratio + val_ratio))  # 0.85
train_df = df.iloc[:train_end_idx]
val_df   = df.iloc[train_end_idx:val_end_idx]
test_df  = df.iloc[val_end_idx:]
```

Splits are strictly index-contiguous slices of the chronologically sorted frame — no shuffle, no random state. Three independent `copy()` objects with reset indices.

In `train_and_evaluate()` (`ml/models/demand/trainer.py`):

```python
train_target = train_df[self.config.target_col].shift(-periods)
```

The forward shift is applied **inside each split separately** after slicing. `train_df.shift(-periods)` cannot reach into `val_df`. The `notna()` mask drops trailing boundary rows. The spike classifier's `derive_labeling_rule(train_raw, ...)` is also called only on the 70% train partition.

**No issue.**

---

## Area 4 — Future Weather Information

**Status: ⚠️ ONE MEDIUM-SEVERITY STRUCTURAL RISK**

### Training path

The weather Parquet is loaded and joined to the entire 35,136-row feature DataFrame **before** splitting (`run_features.py`):

```python
features_df = pipeline.transform(clean_df, weather_df=weather_df)
# → openstef_demand_features.parquet
# Split happens later inside train_and_evaluate()
```

The join is an equi-join on `timestamp` — each demand row receives the weather observation at the same 15-min timestamp. No test-period weather value contaminates a training-period row via the join itself.

However, the weather source `weather_measurements/mv_feeder/OS Edam.parquet` has **unknown temporal provenance**. If the Parquet contains NWP forecast values blended with reanalysis actuals, rows in the test set (Nov–Dec 2024) could carry more accurate weather than would be available at real inference time.

**Severity: MEDIUM** — The code is correct for point-in-time matching. The risk lives in the provenance of the weather Parquet, which is not validated in code. This could cause optimistic test metrics for weather-sensitive horizons (30m, 60m).

### Inference path

`DemandModelService.forecast_demand()` passes `weather_forecast` explicitly — semantically correct at inference time. No issue on the inference path.

---

## Area 5 — Target Leakage

**Status: ✅ CLEAN**

**LightGBM trainer** — `_prepare_feature_cols()` explicitly excludes the target and unit variants:

```python
excluded_cols = {
    self.config.target_col,        # "demand_mw"
    "load", "demand_kw",
    "is_imputed", "is_out_of_range", "is_reverse_flow",
    ...
}
```

**Feature pipeline** — `transform()` maintains a matching `non_feature_cols` set excluding `demand_mw`, `load`, `demand_kw`, and all audit columns.

**Inference service** — `feature_cols` is populated from `lgbm_model.feature_names`, the 37-element list frozen at training time — `demand_mw` is not in that list.

**No issue.**

---

## Area 6 — Timestamp Issues

**Status: ⚠️ ONE LOW-SEVERITY ISSUE — inference filter on `timestamp` not `available_at`**

### Sorting

`transform()` calls `df.sort_values(timestamp_col).reset_index(drop=True)` as its first operation. All feature computations operate on positional index after this sort.

### DST / timezone handling

All timestamps normalised to UTC in ingestion (`IngestionConfig.expected_timezone = "UTC"`). Feature pipeline coerces via `pd.to_datetime(df[ts_col], utc=True)`. The three October 27 DST-ambiguous rows were forward-filled and flagged `is_imputed=True`; `is_imputed` is excluded from features.

### `available_at` column — structural gap, LOW severity

In `DemandModelService.forecast_demand()`:

```python
prior_history = hist_df[hist_df["timestamp"] <= start_dt]
```

The filter uses `timestamp` (measurement time), not `available_at` (telemetry delivery time). If any rows have `available_at > start_dt`, they would be included in `prior_history` even though the data was not yet accessible at prediction time.

The column is present in the raw and canonical datasets but **never used as a filter anywhere in the pipeline**. It is excluded from features but the inference-time history filter does not respect it.

**Severity: LOW** — Practical gap between `timestamp` and `available_at` for a 15-min MV-feeder meter is likely under 1 minute. Becomes critical if the system is used with a meter that has significant publication lag.

---

## Summary Table

| # | Area | Issue | Severity |
|---|---|---|---|
| 1 | Lag alignment | None — shift ≥ 1 on all lags | ✅ None |
| 2 | Rolling windows — LightGBM path | None — applied to `shift(1)` series | ✅ None |
| 3 | Rolling windows — Spike path | `.bfill()` on `historical_peak_24h` fills rows 0–3 from future observations | ⚠️ **Low** |
| 4 | Train/val/test boundaries | None — integer-index slices, target shift contained within each split | ✅ None |
| 5 | Spike label thresholds | None — `derive_labeling_rule` receives `train_raw` only | ✅ None |
| 6 | Future weather | Weather provenance unverified — could be reanalysis with post-hoc accuracy at test timestamps | ⚠️ **Medium** |
| 7 | Target leakage | None — `demand_mw` excluded at two independent layers | ✅ None |
| 8 | Timestamp sorting | None — `sort_values` is first operation in `transform()` | ✅ None |
| 9 | DST / timezone | None — all timestamps normalised to UTC; DST gap rows flagged and excluded | ✅ None |
| 10 | `available_at` inference filter | History filtered on `timestamp ≤ start_dt`, not `available_at ≤ start_dt` | ⚠️ **Low** |
| 11 | Missing feature zero-fill at inference | Missing weather features silently filled with `0.0` — correctness risk, not leakage | ℹ️ Note |

---

## Two Confirmed Issues Requiring Action

### Issue A — Low — `bfill()` on spike `historical_peak_24h`

**Location:** `ml/models/demand/spike_trainer.py` line 72

```python
# Current (vulnerable)
df["demand_mw"].shift(1).rolling(window=96, min_periods=4).max().bfill()

# Fix: change min_periods to 1 — removes need for bfill entirely
df["demand_mw"].shift(1).rolling(window=96, min_periods=1).max()
```

The `.bfill()` causes rows 0–3 to look forward for their fill value. Changing `min_periods=4` to `min_periods=1` removes the need for `bfill()` while retaining valid past-only semantics from the very first row.

### Issue B — Medium — Weather provenance not verified

**Location:** `services/forecasting/run_features.py` lines 64 and 82

No code change will fix this — it requires inspecting the OpenSTEF dataset documentation to confirm whether the weather Parquet contains NWP forecast values (available at prediction time) or ERA5/reanalysis values (computed retrospectively). If the latter, test-set MAPE for 30m and 60m horizons is optimistic. The fix is to add an assertion or data-lineage note in `run_features.py` before generating the feature store.
