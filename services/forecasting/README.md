# `services/forecasting` — Demand Forecasting & Spike Detection Service

## Module Overview
Implements predictive microservices for electricity demand and sudden grid load spike classification.

- **Models:**
  - Demand Forecasting: **LightGBM** (15-min, 30-min, 60-min horizons with upper/lower uncertainty bounds).
  - Demand Spike Detection: **XGBoost Classifier** (Normal, Moderate Spike, Severe Spike).
- **Architectural Rule (Rule A):** Machine Learning is responsible for **PREDICTIONS ONLY**. ML outputs expected megawatt load and risk probabilities; it never dispatches batteries or commands grid assets.
- **Owned By:** Member 2 (Data + Demand Forecasting)
- **Branch:** `member/data-forecast`

## Contract Conformance
Every forecast emitted by this service must conform strictly to `shared/contracts/DemandForecast.ts`:
- `zoneId`: Target grid substation/zone identifier.
- `horizonMinutes`: 15 | 30 | 60.
- `points`: Array of timestamped predicted demand MW with confidence bounds.
- `spikeRisk`: Level (`normal` | `moderate` | `severe`), probability, and predicted peak MW.
- `modelVersion`: Deterministic model checkpoint identifier.
