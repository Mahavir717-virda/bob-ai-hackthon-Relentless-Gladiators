# `services/forecasting` — Demand Forecasting & Spike Detection Service

## Module Overview
Implements predictive microservices for electricity demand and sudden grid load spike classification.

- **Models:**
  - Demand Forecasting: **LightGBM** multi-horizon (`ml/models/demand/demand_lgbm.pkl`, 15-min, 30-min, 60-min horizons with upper/lower uncertainty bounds).
  - Demand Spike Detection: **XGBoost Classifier** (`ml/models/demand/spike_xgb.pkl`, 3 classes: Normal, Moderate Spike, Severe Spike).
- **Architectural Rule (Rule A):** Machine Learning is responsible for **PREDICTIONS ONLY**. ML outputs expected megawatt load and risk probabilities; it never dispatches batteries or commands grid assets.
- **Owned By:** Member 2 (Data + Demand Forecasting)
- **Branch:** `member/data-forecast`

## Architecture & File Structure
```
services/forecasting/
├── demand_model.py      # DemandModelService and DemandLGBMModel container
├── spike_model.py       # SpikeModelService for dynamic 3-class XGBoost spike inference
├── demand_features.py   # Reusable feature builder used by both training and inference
├── model_loader.py      # Cached artifact loader for demand_lgbm.pkl and spike_xgb.pkl
├── service.py           # Top-level DemandForecastService API
├── models.py            # Typed dataclasses (DemandForecast, DemandForecastPoint, SpikeRisk)
├── errors.py            # Typed error hierarchy (InvalidZoneError, InsufficientHistoryError, etc.)
└── README.md            # Module documentation
```

## Contract Conformance
Every forecast emitted by this service conforms strictly to `shared/contracts/DemandForecast.ts`:
- `zoneId`: Target grid substation/zone identifier.
- `generatedAt`: ISO 8601 UTC timestamp.
- `horizonMinutes`: 15 | 30 | 60.
- `points`: Array of timestamped predicted demand MW with confidence bounds (`[lowerBoundMw, upperBoundMw]`).
- `spikeRisk`: Level (`normal` | `moderate` | `severe`), probability, and predicted peak MW.
- `modelVersion`: Model checkpoint identifier.
