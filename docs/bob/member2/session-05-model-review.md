# Session 05 — Model Review (Member 2)

**Team Member:** Member 2 (Data + Demand Forecasting)  
**Branch:** `deep/data-forecast`  
**Purpose:** Review the demand forecasting implementation across baseline comparison, LightGBM training, evaluation metrics, reproducibility, missing data behavior, and model versioning.

---

## Prompt

> Review the demand forecasting implementation.
> Check: baseline comparison, LightGBM training, evaluation metrics, reproducibility, missing data behavior, model versioning.
> Do not modify files.

---

## Test Suite Status (Pre-Review)

All existing tests pass before review:

```
services/forecasting/tests/test_baselines.py     — 5 passed
services/forecasting/tests/test_lgbm_forecaster.py — 1 passed
services/forecasting/tests/test_features.py       — 13 passed
```

---

## 1. Baseline Comparison

**Status: ✅ Implemented correctly — ⚠️ one honest result to flag**

### Implementation

`evaluate_baselines_on_split()` (`services/forecasting/baselines.py`) evaluates both baselines over `full_series`, slicing predictions to the test window. The seasonal naive's 96-step lookback can reach into the validation partition to serve the first test rows — correct behaviour.

`compare_with_baselines()` (`ml/models/demand/trainer.py`) concatenates the baseline CSV with LightGBM test metrics and sorts by `(horizon_minutes, mae)` ascending. Both were evaluated on the **same test split** (Nov 7 → Dec 31 2024, n≈5271).

### Results

| Horizon | Persistence MAE | LightGBM MAE | Beats Persistence? | Seasonal Naive MAE |
|---|---|---|---|---|
| 15 min | **0.0382** | 0.0497 | ❌ **No** | 0.1266 |
| 30 min | 0.0631 | **0.0617** | ✅ Yes (+2.2%) | 0.1266 |
| 60 min | 0.1056 | **0.0846** | ✅ Yes (+19.9%) | 0.1266 |

**Finding — Medium:** At h=15, persistence MAE (0.0382) is lower than LightGBM MAE (0.0497) by 23%. The verification loop in `train_demand_models.py` correctly prints `"DOES NOT BEAT BASELINE"` for this horizon. The comparison table in `baseline_vs_lightgbm_comparison.json` is honest. However, `DemandModelService` still dispatches to the LightGBM 15-min booster unconditionally when `horizon=15` — it does not fall back to persistence.

**Finding — Low:** `SeasonalNaiveForecaster.predict_series()` accepts `horizon_minutes` as a parameter but ignores it entirely — the method always shifts by `seasonal_steps` (96 steps = 24h), regardless of the requested horizon. The implementation is mathematically correct for a standard seasonal naive, but the ignored parameter creates an API expectation mismatch.

---

## 2. LightGBM Training

**Status: ✅ Structurally sound — two implementation notes**

### Training loop (`train_and_evaluate()` in `ml/models/demand/trainer.py`)

- Sorted chronologically on line 77 before split
- Three independent boosters, one per horizon — correct for direct multi-step forecasting
- Target construction: `train_df["demand_mw"].shift(-periods)` contained within each split
- `notna().all(axis=1)` mask drops warm-up NaN rows from all three splits before training
- Early stopping on validation MAE — matches `"metric": "mae"` in `lgbm_params`

### Note 1 — Medium

`_prepare_feature_cols()` selects features dynamically from the input DataFrame using `pd.api.types.is_numeric_dtype`. Any extra numeric column not in `DEMAND_FEATURE_NAMES` will silently be included as a feature. The feature list is not pinned to the canonical 37-column list at training time. The current run is safe (metadata confirms exactly 37 features), but the guard is missing for future runs.

### Note 2 — Low

Four overlapping artifact naming schemes exist for the same underlying models:

| Path | Created by |
|---|---|
| `demand-lgbm-v1_h{15,30,60}min.joblib` | `save_artifacts()` in `trainer.py` |
| `demand-lgbm-v1_h{15,30,60}min.txt` | `save_artifacts()` in `trainer.py` |
| `demand_lgbm.pkl` | `train_and_serialize_artifacts.py` |
| `demand_lgbm_{15,30,60}m.pkl` | `train_and_serialize_artifacts.py` line 89 |

The loader only reads `demand_lgbm.pkl`, so none of the duplicates affect runtime, but the `ml/models/demand/` directory is cluttered.

### Booster size by horizon

| Booster | Best iteration | File size |
|---|---|---|
| h=15 | 205 | 607 KB |
| h=30 | **360** | **1,060 KB** |
| h=60 | 199 | 589 KB |

The 30-min booster trained for substantially more iterations. Expected — the 30-min horizon is harder than 15m (where persistence dominates) but more tractable than 60m.

---

## 3. Evaluation Metrics

**Status: ✅ Correct implementation — ⚠️ MAPE distortion on test set**

### `calculate_metrics()` (`services/forecasting/evaluate.py`)

- NaN pairs excluded via `valid_mask` — correct
- MAPE excludes `|y_true| ≤ 1e-4` via `nonzero_mask` — prevents divide-by-zero
- Returns `None` for MAPE (not `NaN`) when no nonzero ground-truth values exist — handled gracefully

### Val vs test MAPE gap — Medium

| Horizon | Val MAPE | Test MAPE | Ratio |
|---|---|---|---|
| 15 min | 39.63% | 14.27% | 2.8× |
| 30 min | 42.99% | 17.79% | 2.4× |
| 60 min | 50.00% | 21.81% | 2.3× |

Validation spans Sep–Nov (autumn transition), test spans Nov–Dec (winter). The test MAPE is substantially lower than val MAPE — the opposite of overfitting. This is explained by the 16.78% reverse-flow rows: when `|y_true|` is near zero (net-export rows), MAPE explodes. The test window (winter) has higher gross demand and fewer near-zero rows, making its MAPE appear better. The reported MAPE values are not comparable across splits.

### No confidence intervals — Low

Metrics are point estimates over ~5,270 test samples. No standard error or confidence interval is computed. The "LightGBM beats persistence at 30m" claim cannot be tested for statistical significance from the current artifacts.

---

## 4. Reproducibility

**Status: ✅ Strong — one gap**

### Seed control confirmed

| Component | Seed | Location |
|---|---|---|
| LightGBM | `"seed": 42` | `LightGBMTrainingConfig.lgbm_params` in `config.py` |
| XGBoost spike | `random_state=42` | `SpikeClassifierConfig.random_seed` in `spike_config.py` |

`bagging_freq=5` with `bagging_fraction=0.9` confirms row subsampling is active and seeded. Chronological split is deterministic — no random state needed.

### Gap — Low: wall-clock timestamp in metadata

`demand_lgbm_metadata.json` records a `training_timestamp` via `datetime.now(timezone.utc)` in `train_and_serialize_artifacts.py`. This field changes on every re-run even when the model is bit-for-bit identical. If these artifacts are tracked in git, every retrain produces a noisy diff with no information content.

### Gap — Low: library version not recorded

Neither joblib nor LightGBM version is recorded in any metadata file. A LightGBM major version bump can change the booster internal format, making `.joblib` files unloadable. The `.txt` text-format boosters are more portable but are not loaded by the production `ModelLoader`.

---

## 5. Missing Data Behavior

**Status: ✅ Training — ⚠️ Inference**

### Training

NaN rows are dropped by the `notna().all(axis=1)` mask in `trainer.py` — correctly eliminates warm-up rows. `lgb.Dataset` sees no NaN predictor values.

### Inference — `demand_model.py`

**Row-level NaN recovery (lines 201–207):**

```python
missing_in_row = [c for c in feature_cols if latest_feature_row[c].isna().any()]
if missing_in_row:
    recent_context = feated_df.iloc[-3:][feature_cols].ffill()
    ...
    if still_missing:
        raise MissingFeatureError(still_missing, ...)
```

The ffill window is only **3 rows (45 minutes)**. Correct fail-fast behaviour for gaps longer than 45 minutes.

**Column-level zero-fill (lines 194–196) — Medium:**

```python
for c in feature_cols:
    if c not in feated_df.columns:
        feated_df[c] = 0.0
```

Zero is structurally wrong for weather features (`temperature_2m=0.0` = 0°C is a valid physical value but almost certainly not the correct default). This runs **silently with no warning or logging**, and happens before the row-level NaN check. The same pattern also appears in `DemandLGBMModel.predict()` at lines 68–70.

---

## 6. Model Versioning

**Status: ✅ Versioning present — ⚠️ two structural gaps**

### What is versioned correctly

- `model_version = "demand-lgbm-v1"` hardcoded in `LightGBMTrainingConfig` and stamped on every artifact and API response
- `feature_version = "1.0.0"` in both `LightGBMTrainingConfig` and `SpikeClassifierConfig`, cross-referenced with `FEATURE_PIPELINE_VERSION = "1.0.0"` in `features.py`
- `modelVersion` propagated through `DemandForecast` to every API response
- Per-horizon `.txt` text-format boosters are LightGBM-native portable format

### Gap 1 — Medium: No version check at load time

`ModelLoader.get_demand_model()` loads `demand_lgbm.pkl` and returns the deserialized object with no version verification:

```python
# model_loader.py — no version check
model = joblib.load(model_path)
self._cached_demand_model = model
return model
```

If an older or newer `.pkl` is present on disk, it will be served with no warning.

### Gap 2 — Low: `demand_lgbm_metadata.json` target field mismatch

`demand_lgbm_metadata.json` records:
```json
"target": "demandMw"
```

The actual training target column is `"demand_mw"` (snake_case). The camelCase value `"demandMw"` matches the TypeScript contract but not the Python training code. The authoritative `demand-lgbm-v1_training_metadata.json` correctly records `"target_col": "demand_mw"`. The two files describe the same model but disagree on the target field name.

---

## Summary Table

| # | Area | Finding | Severity |
|---|---|---|---|
| 1 | Baseline comparison | h=15 LightGBM loses to persistence — correctly logged, but `DemandModelService` still dispatches to LGBM at h=15 | **Medium** |
| 2 | Baseline comparison | `SeasonalNaiveForecaster.predict_series` ignores `horizon_minutes` parameter | **Low** |
| 3 | LightGBM training | Feature cols selected dynamically — no pin to canonical 37-column list | **Medium** |
| 4 | LightGBM training | Four overlapping artifact naming schemes for same models | **Low** |
| 5 | Evaluation metrics | Val vs test MAPE 2–3× gap caused by reverse-flow near-zero rows — misleading as standalone accuracy | **Medium** |
| 6 | Evaluation metrics | No confidence intervals or significance test on any metric | **Low** |
| 7 | Reproducibility | Training timestamp changes on every re-run — noisy git diffs | **Low** |
| 8 | Reproducibility | LightGBM and joblib version not recorded in metadata | **Low** |
| 9 | Missing data — inference | Weather columns missing from DataFrame silently zero-filled at two call sites | **Medium** |
| 10 | Model versioning | `ModelLoader` performs no version check on deserialized object | **Medium** |
| 11 | Model versioning | `demand_lgbm_metadata.json` records `"target": "demandMw"` instead of `"demand_mw"` | **Low** |
| 12 | Spike classifier | Macro F1 = 0.536, moderate precision = 0.265, severe precision = 0.200 — low minority-class precision despite sample weighting | **Medium** |

---

## Spike Classifier Metrics

From `spike_evaluation_metrics.json`:

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | 0.9979 | 0.9935 | 0.9957 | 5,239 |
| moderate | 0.2647 | 0.3600 | 0.3051 | 25 |
| severe | 0.2000 | 0.6667 | 0.3077 | 6 |
| **macro** | **0.4875** | **0.6734** | **0.5362** | — |

The model correctly classifies normal demand (F1=0.9957) but has weak minority-class precision. 34 out of 5,239 normal rows are misclassified as spike events (false alarm rate 0.65%), while 16 out of 31 true spike events are correctly flagged. Given the extreme class imbalance (95/4/1 split in training), the `sample_weight="balanced"` approach in `spike_trainer.py` has improved recall but left precision low.
