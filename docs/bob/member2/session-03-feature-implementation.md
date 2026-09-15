# Session 03 — Feature Implementation (Member 2)

**Team Member:** Member 2 (Data + Demand Forecasting)  
**Branch:** `deep/data-forecast`  
**Purpose:** Implement the demand feature-generation module and add tests for timestamp ordering, missing history, and future-data leakage.

---

## Prompt

> Implement the demand feature-generation module.
> Add: 15-minute lag, 30-minute lag, 1-hour lag, 24-hour lag, calendar features.
> Add tests for: timestamp ordering, missing history, future-data leakage.
> Do not modify unrelated modules.

---

## Implementation Finding

The demand feature-generation module in `services/forecasting/features.py` was fully implemented and correct before this session. All four required lags and all calendar features were already in place.

| Required feature | Implementation | Status |
|---|---|---|
| 15-minute lag | `_add_lag_features()` — `shift(1)` | ✅ Present |
| 30-minute lag | `_add_lag_features()` — `shift(2)` | ✅ Present |
| 1-hour lag | `_add_lag_features()` — `shift(4)` | ✅ Present |
| 24-hour lag | `_add_lag_features()` — `shift(96)` | ✅ Present |
| Calendar features | `_add_calendar_features()` — hour, dow, weekend, holiday, season, sin/cos | ✅ Present |

Modifying working code without a reason would violate the engineering constraint of minimal change.

---

## Tests Added

File: `services/forecasting/tests/test_features.py`

7 new tests added inside the existing `TestDemandFeaturePipeline` class. Total test count: 6 (existing) → 13.

### Timestamp Ordering (2 tests)

#### `test_transform_sorts_unsorted_input`

Shuffles the 200-row DataFrame with `sample(frac=1, random_state=0)`, then asserts:
1. Output rows are chronologically sorted (`ts.diff().iloc[1:] >= 0`)
2. `lag_15m[i]` equals `demand_mw[i-1]` in the **sorted** output — not in the original shuffled row order

This verifies that `transform()` sorts by timestamp as its first step before computing any feature.

#### `test_output_timestamp_monotonic_ascending`

Asserts `ts.diff().iloc[1:] > 0` on an already-sorted input. Confirms strict monotonicity is never broken — no duplicate or reversed timestamps can appear in the output.

---

### Missing History (3 tests)

#### `test_lag_nan_for_insufficient_history`

Uses only 10 rows. Asserts exact NaN counts per lag column:

| Column | Expected NaN count | Reason |
|---|---|---|
| `demand_mw_lag_15m` | 1 | Needs 1 prior row |
| `demand_mw_lag_30m` | 2 | Needs 2 prior rows |
| `demand_mw_lag_60m` | 4 | Needs 4 prior rows |
| `demand_mw_lag_1440m` | 10 (all) | Needs 96 prior rows — none available with 10-row input |

#### `test_single_row_all_lags_nan`

A single-row DataFrame must produce all-NaN lag, rolling, and momentum columns — there is no past to look back at.

#### `test_minimum_rows_for_24h_lag`

Uses exactly 97 rows. Asserts:
- Rows 0–95 are NaN for `demand_mw_lag_1440m`
- Row 96 is the first non-NaN value and must equal `demand_mw[0]` exactly (`assertAlmostEqual` to 6 decimal places)

---

### Future-Data Leakage (2 extended tests)

The mutation-proof test (`test_future_data_mutation_zero_leakage_proof`) already existed. Two complementary tests were added:

#### `test_lag_values_never_reference_current_or_future_row`

Row-by-row check across all 200 rows: for every valid `i`, `lag_15m[i] == demand_mw[i-1]`. If row `i` were used to produce `lag_15m[i]`, this would fail.

#### `test_rolling_mean_excludes_current_row`

Uses a minimal config (`rolling_windows=[4]`, no groupby). Mutates `demand_mw[50] = 999999.0`, then:
- Asserts `roll_mean_4[50]` is **unchanged** — depends only on rows 46–49, not row 50
- Asserts `roll_mean_4[51]`, `[52]`, `[53]`, `[54]` **do** change — row 50 is now in their past window

This is a two-sided proof: current row excluded, past rows correctly included.

---

## Full Test Suite Result

```
services/forecasting/tests/test_features.py — 13 passed in 1.38s

  test_calendar_and_dutch_holidays            PASSED
  test_future_data_mutation_zero_leakage_proof PASSED
  test_lag_features_exact_past_offsets        PASSED
  test_lag_nan_for_insufficient_history       PASSED   ← new
  test_lag_values_never_reference_current_or_future_row PASSED  ← new
  test_minimum_rows_for_24h_lag               PASSED   ← new
  test_output_timestamp_monotonic_ascending   PASSED   ← new
  test_rolling_features_exact_past_windows    PASSED
  test_rolling_mean_excludes_current_row      PASSED   ← new
  test_single_row_all_lags_nan                PASSED   ← new
  test_transform_sorts_unsorted_input         PASSED   ← new
  test_version_exported                       PASSED
  test_weather_merge_and_alignment            PASSED
```

---

## Files Changed

| File | Change |
|---|---|
| `services/forecasting/tests/test_features.py` | Added 7 new test methods to `TestDemandFeaturePipeline` |

No production code was modified.

---

## What Was Not Changed

`services/forecasting/features.py` — the feature module itself — was left untouched. All four lag features, all calendar features, the rolling window implementation, and the momentum features were already correctly implemented.
