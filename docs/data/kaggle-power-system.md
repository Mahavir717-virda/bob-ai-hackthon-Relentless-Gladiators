# Kaggle Power System Modelling Adapter

## Status

Step 7 final validation complete. Steps 1-6, the aggregate-series LightGBM
forecasters, Kaggle-only actual-vs-expected/Isolation Forest evaluation,
XGBoost/SHAP association models, and the Kaggle service integration have been
validated. Existing synthetic/OpenSTEF artifacts remain untouched.

## Source

- Dataset: **Power System Modelling**
- Kaggle reference: `mexwell/power-system-modelling`
- Upstream package: Open Power System Data, *Data Package Time series*, version
  `2020-10-06`, DOI `10.25832/time_series/2020-10-06`
- Extracted files: `README.md`, and 15-minute, 30-minute, and 60-minute CSVs
- Adapter default: `time_series_60min_singleindex.csv`
- Download date: 2026-09-15
- License: Kaggle reports `other`; the included README provides attribution
  guidance but does not state a standalone license. Preserve the upstream
  Open Power System Data attribution when redistributing.

## Adapter Mapping

`services/renewable/kaggle_data_loader.py` dynamically discovers columns matching
`*_solar_generation_actual` and `*_wind_generation_actual`. For each source
row, it emits normalized columns:

| Normalized field | Source or rule |
|---|---|
| `timestamp` | `utc_timestamp`, parsed as timezone-aware UTC |
| `asset_id` | Original generation column name, unchanged |
| `energy_type` | `solar` or `wind`, derived from the column name |
| `actual_mw` | Generation value, kept in the source MW unit |
| `capacity_mw` | Matching `*_solar_capacity` or `*_wind_capacity`, otherwise null |
| `source` | Constant `kaggle_power_system` |

The adapter streams the wide CSV in chunks, rejects invalid or duplicate
timestamps, reports timestamp gaps, and preserves missing generation values.
It never fills missing generation or capacity values.

Example normalized record:

```text
timestamp:   2015-01-01 00:00:00+00:00
asset_id:    DE_solar_generation_actual
energy_type: solar
actual_mw:   0.0
capacity_mw: 37248.0
source:      kaggle_power_system
```

## Data Semantics and Limits

Generation and capacity values are documented in MW. The hourly file contains
39 solar and 82 wind aggregate series, with 20 generation series having a
matching capacity series and 101 without one. The hourly timestamp grid covers
2014-12-31 23:00 UTC through 2020-09-30 23:00 UTC at one-hour intervals.

**`asset_id` represents an aggregate region/series identifier, not necessarily
a physical renewable asset.** Series represent countries, control areas, or
bidding zones. They do not provide per-park metadata, coordinates, or
nameplate mappings for every series. The adapter therefore does not claim that
an aggregate series is a physical solar or wind farm.

The dataset has no temperature, cloud cover, irradiance, humidity, pressure,
wind-speed, or wind-direction columns. No synthetic weather values are added.
Weather-based root causes cannot be claimed from these records.

There is no direct per-asset curtailment indicator. Curtailment is represented
as unavailable, never as `false` and never as a fabricated detected label.

## Step 3 Forecasting

The default training source was `time_series_60min_singleindex.csv`. The
separate module `services/renewable/kaggle_forecasting.py` was used because the
existing OpenSTEF forecasters require 15-minute load data and weather columns.
The Kaggle models use LightGBM and predict `actual_mw` directly in MW.

Features contain only information present in the source:

- Cyclic hour, weekday, day-of-year, and month features
- Past generation lags: 1, 2, 3, 6, 24, 48, and 168 hours
- Past rolling generation means over 3, 24, and 168 hours
- Capacity and lagged generation/capacity ratio only where a matching capacity
  column exists

No weather values were fabricated. No future generation values are used as
features. Missing target rows are excluded from training; they are never
converted to zero or forward-filled. Capacity-derived features are optional,
so series without capacity still train using temporal features only.

The chronological split was 70% training, 15% validation, and 15% final test,
with no shuffling. Boundaries are stored per series in each metadata file. For
example, the `AT_solar_generation_actual` split was:

| Partition | Range (UTC) | Rows |
|---|---|---:|
| Train | 2015-01-01 07:00 to 2019-01-10 11:00 | 35,237 |
| Validation | 2019-01-10 12:00 to 2019-11-21 02:00 | 7,551 |
| Test | 2019-11-21 03:00 to 2020-09-30 17:00 | 7,551 |

### Training Results

| Type | Discovered | Trained | Skipped | Mean validation MAE (MW) | Mean validation RMSE (MW) | Mean validation MAPE | Mean test MAE (MW) | Mean test RMSE (MW) | Mean test MAPE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Solar | 39 | 38 | 1 | 47.913 | 92.696 | 28.42% | 133.568 | 248.385 | 37.54% |
| Wind | 82 | 81 | 1 | 109.010 | 171.147 | 22.29% | 201.872 | 292.923 | 25.56% |

MAPE excludes rows whose actual generation is zero or effectively zero, so
night-time solar and zero-output intervals do not create infinite values. MAE
and RMSE include all held-out valid rows.

The skipped series were `HR_solar_generation_actual` with 10 valid observations
and `HR_wind_onshore_generation_actual` with 22 valid observations. The minimum
usable-observation threshold was 500.

Artifacts are stored separately under
`ml/models/renewable/artifacts/kaggle/`:

- One `.pkl` and metadata `.json` per trained aggregate series
- `kaggle_forecasting_manifest.json` containing counts, splits, metrics, and
  skipped-series reasons

The persisted model was loaded successfully in a fresh Python process and
returned non-negative predictions in MW. This forecasting model predicts
aggregate renewable generation and does not represent an individual physical
renewable asset.

These models are forecasting-only. Because the dataset contains no weather,
maintenance, curtailment, or equipment-status fields, the results do not
support claims about cloud cover, irradiance, temperature, wind speed,
inverter/turbine faults, maintenance, or curtailment.

## Validation

The focused tests in `services/renewable/tests/test_kaggle_data_loader.py` and
`services/renewable/tests/test_kaggle_forecasting.py` cover solar and wind
loading, MW preservation, capacity matching and missing capacity, UTC parsing,
missing values, timestamp gaps, duplicate rejection, chronological splitting,
future-leakage prevention, zero-safe MAPE, model persistence, and fresh-process
inference. The combined focused suite passes 9 tests.

No anomaly detector, Isolation Forest, XGBoost root-cause model, or
`RenewableStatus` orchestration was changed or trained in Step 3.

## Step 4 Actual-vs-Expected and Anomaly Detection

`services/renewable/kaggle_anomaly.py` adds a separate Kaggle-only analysis
path. It does not route aggregate data through the existing weather-aware
OpenSTEF anomaly service and does not change the shared `RenewableStatus`
contract.

For each evaluated aggregate series it calculates absolute deviation, absolute
error, percentage deviation, performance ratio, and capacity ratios when a
valid positive capacity is supplied. When expected generation is missing or at
or below `1e-6 MW`, percentage deviation and performance ratio are null.
Missing actual or expected observations are not sent to the Isolation Forest
and are not marked as anomalies. Missing capacity remains unavailable and is
never inferred.

The detector uses only source-supported features: actual/expected values,
deviation and ratio values, rolling performance, calendar features, and
capacity ratios when available. No weather, maintenance, equipment, or
fabricated curtailment features are used. The default curtailment state is
`unknown`; only an explicitly supplied signal can suppress an anomaly.

Each series uses a chronological 80% training and 20% evaluation split. The
detector is an `IsolationForest` with 200 estimators, contamination `0.05`,
`random_state=42`, and one worker. Its `decision_function` score is exposed:
lower values are more anomalous and zero is the fitted decision boundary. The
score is not a probability, and confidence is unavailable rather than invented.

### Real Evaluation

| Type | Series evaluated | Observations evaluated | Anomalies | Anomaly percentage |
|---|---:|---:|---:|---:|
| Solar | 38 | 344,814 | 45,897 | 13.3107% |
| Wind | 81 | 702,395 | 147,158 | 20.9509% |
| **Total** | **119** | **1,047,209** | **193,055** | **18.4352%** |

The evaluation periods are chronological and individual boundaries are stored
in each detector metadata file. The two sparse HR series were skipped because
their Step 3 forecast artifacts were unavailable.

Detector artifacts are stored separately under
`ml/models/renewable/artifacts/kaggle_anomaly/`, including one persisted
Isolation Forest bundle and metadata JSON per evaluated series plus
`kaggle_anomaly_manifest.json`.

**Unsupervised anomaly detection; no authoritative anomaly ground truth is
available.** The anomaly percentage is a detector output, not a precision,
recall, or accuracy measurement. Low output is not classified as an equipment
failure. No XGBoost, SHAP, weather-based root cause, or equipment-fault
classification was performed in Step 4.

The combined Step 2/3/4 and existing performance/diagnostic regression suite
passes 36 tests. No root-cause modeling was performed.

## Step 5 Root-Cause Association

Step 5 adds `services/renewable/kaggle_root_cause.py`, a separate
XGBoost/SHAP association path for the Kaggle aggregate data. It does not
modify the legacy OpenSTEF root-cause module, Step 3 forecasting artifacts,
Step 4 anomaly artifacts, shared contracts, or service orchestration.

Separate pooled models were trained for solar and wind. The target is finite
percentage deviation, not a physical cause label. Rows with expected
generation at or below `0.001 MW` are excluded from training because their
percentage deviations are numerically unstable; they remain uncertainty cases
when analyzed. Training uses chronological 70%/15%/15% train/validation/test
partitions with no shuffling.

Features actually used:

- Expected MW and expected/capacity ratio
- Capacity where supplied, never inferred
- Hour, weekday, day-of-year, and month cyclic features
- Generation lags at 1, 2, 3, 6, 24, 48, and 168 hours
- Rolling generation means over 3, 24, and 168 hours

No weather, maintenance, equipment-status, or fabricated curtailment feature
was used. `curtailment_status` remains `unknown`. The dataset has no
authoritative physical root-cause labels, so no classifier accuracy or causal
claim is reported.

### Model Diagnostics

| Model | Train rows | Validation rows | Test rows | Validation MAE (percentage points) | Test MAE (percentage points) | Test RMSE (percentage points) |
|---|---:|---:|---:|---:|---:|---:|
| Solar pooled | 737,865 | 158,114 | 158,114 | 2,277.91 | 1,859.61 | 69,242.37 |
| Wind pooled | 2,432,538 | 521,258 | 521,259 | 33.63 | 92.17 | 6,407.41 |

The solar percentage-deviation diagnostics remain large because heterogeneous
aggregate solar series contain small positive expected values; percentage
errors amplify those rows even after the near-zero training gate. These are
model diagnostics only and do not measure physical root-cause quality.

Artifacts are stored alongside the Kaggle artifacts under
`ml/models/renewable/artifacts/kaggle/`:

- `kaggle_root_cause_xgb_solar.pkl` and metadata
- `kaggle_root_cause_xgb_wind.pkl` and metadata
- `kaggle_root_cause_manifest.json`

For anomalous rows with sufficient evidence, SHAP returns the strongest feature
contributions. A representative fresh-process explanation returned the
evidence features `expected_capacity_ratio`, `roll_mean_168`, `lag_2`,
`roll_mean_24`, and `roll_mean_3`, with the association category
`unusually low generation relative to expected`. Confidence was `null`, not a
fabricated probability, and curtailment remained `unknown`.

Outputs use these evidence-limited categories:

- `expected/normal temporal variation`
- `unusually low generation relative to expected`
- `unusually high generation relative to expected`
- `insufficient evidence`

Missing actual/expected values, non-anomalous rows, missing required features,
and unavailable deviation values return `insufficient evidence`. SHAP values
explain model association only; they do not prove cloud cover, irradiance,
temperature, inverter failure, turbine failure, maintenance, or curtailment.

The Step 5-specific tests pass 3 tests. The final Step 2/3/4/5 plus legacy
root-cause regression command passes 22 tests. No Step 6 work was performed.

## Step 6 Renewable Intelligence Service

`services/renewable/kaggle_service.py` integrates the persisted Kaggle
forecasting, anomaly, and root-cause association artifacts without changing
the existing synthetic/OpenSTEF service. It exposes:

- `getRenewableStatus(assetId, timestamp)`
- `detectAnomalies(timeRange)`
- `analyzeRootCause(assetId, timestamp)`

The service dynamically resolves the exact aggregate `asset_id`, loads its
Step 3 LightGBM model and Step 4 Isolation Forest bundle, and loads the pooled
Step 5 solar or wind XGBoost/SHAP bundle when an anomaly is present. Models and
the hourly source CSV are cached per process; requests never retrain models.

The consolidated status includes `asset_id`, UTC `timestamp`, `energy_type`,
actual and expected MW, deviations, performance ratio, capacity and capacity
ratio when available, anomaly flag/score, curtailment status, root-cause
association, confidence, evidence, uncertainty, and `weather_available=false`.
Missing values remain null. Near-zero expected generation uses the existing
safe ratio behavior. Missing capacity remains null. Curtailment is always
`unknown` for this source.

Service errors use `KaggleRenewableServiceError` with codes including
`UNKNOWN_ASSET`, `INVALID_TIMESTAMP`, `TIMESTAMP_OUT_OF_RANGE`,
`INVALID_TIME_RANGE`, `MISSING_FORECAST_MODEL`, `MISSING_ANOMALY_MODEL`, and
artifact-load errors. Missing Step 5 artifacts return `insufficient evidence`
rather than a fabricated physical diagnosis.

The service preserves aggregate semantics: `DE_solar_generation_actual` and
similar identifiers are not converted into plant, turbine, inverter, or panel
IDs. The source has no weather or direct curtailment fields, so the service
does not fabricate them. SHAP evidence remains model contribution/association,
not proof of physical causation. The Step 6 integration tests pass 9 tests
against the persisted real Kaggle artifacts.

## Step 7 Final Validation

The final accepted Kaggle Step 2-6 suite plus stable legacy unit tests passes
62 tests with 3 dependency deprecation warnings and no test failures. The
complete `services/renewable/tests` run passes 67 tests but retains two
pre-existing failures in `test_e2e_scenarios.py`: one strict XPASS for an
existing synthetic curtailment scenario and one synthetic registry-state
failure. These failures are outside the Kaggle service path and no unrelated
test or synthetic service code was changed.

Final end-to-end checks passed for:

- Solar `DE_solar_generation_actual` at `2019-06-01T12:00:00Z`: actual
  `27046.0 MW`, expected `25385.544278075788 MW`, deviation `6.54095%`,
  performance ratio `1.06541`, anomaly `true`, anomaly score `-0.05601`, and
  five SHAP association evidence entries.
- Wind `AT_wind_onshore_generation_actual` at the same timestamp: actual
  `976.0 MW`, expected `1072.0440191572063 MW`, deviation `-8.95896%`,
  performance ratio `0.91041`, anomaly `false`, and capacity fields null
  because no matching capacity exists.

Leakage review passed: chronological splits are enforced; lag features use
prior rows; rolling features use shifted prior observations; no future target
is used; and root-cause training uses chronological partitions. Missing source
values remain missing and can make derived evidence unavailable.

Determinism passed: repeated service requests returned identical solar status
and SHAP evidence. Random states are fixed for LightGBM, Isolation Forest, and
XGBoost. Fresh-process loading passed for representative Step 3, Step 4, and
Step 5 artifacts. All three manifests remain present, and representative
synthetic model metadata remains intact.

Missing-data and safety checks passed for null actual/expected/capacity,
zero/near-zero expected values, invalid asset/timestamp/range, unknown assets,
and missing artifact behavior. Curtailment remained `unknown`; no weather,
physical asset identity, capacity, or physical root-cause labels were
fabricated.