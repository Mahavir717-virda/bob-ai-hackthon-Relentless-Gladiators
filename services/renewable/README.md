# `services/renewable` — Renewable Intelligence Service

## Module Overview
Delivers solar and wind power output predictions, flags asset anomalies, and provides machine-learning-driven root cause diagnostics.

- **Models:**
  - Solar Generation Forecast: **LightGBM**
  - Wind Generation Forecast: **LightGBM**
  - Asset Anomaly Detection: **Isolation Forest** (detects unexpected underproduction given weather conditions)
  - Root-Cause Classification: **XGBoost Classifier + SHAP** (`cloud_cover`, `inverter_fault`, `soiling`, `curtailment`, `sensor_error`)
- **Architectural Rule (Rule A & C):** Diagnoses performance deviations and generates confidence scores. Does not guess dispatch decisions. Explains evidence without confusing correlation with causation.
- **Owned By:** Member 3 (Renewable Intelligence)
- **Branch:** `member/renewable-intelligence`

## Contract Conformance
Conforms to `shared/contracts/RenewableStatus.ts`:
- `assetId`, `assetType` (`solar` | `wind` | `hydro`).
- `expectedMw`, `actualMw`, `performanceRatio`.
- `anomaly`: Boolean flag + anomaly score.
- `likelyRootCause`: Categorized cause, confidence score (0-1), and feature evidence string.
