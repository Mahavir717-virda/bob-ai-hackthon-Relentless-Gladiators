# `shared/errors` — Standardized System Errors

## Module Overview
Provides standardized error codes, custom error classes, and JSON error responses shared across API, services, and agent tools.

- **Error Categories:**
  - `ValidationError` — Bad query params, invalid time horizon, or malformed payload.
  - `ModelInferenceError` — Upstream ML model failure, missing features, or corrupted weights.
  - `OptimizationInfeasibleError` — OR-Tools solver determined constraints cannot be satisfied.
  - `InsufficientHistoryError` — Not enough historical 15-minute lags to compute LightGBM features.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
