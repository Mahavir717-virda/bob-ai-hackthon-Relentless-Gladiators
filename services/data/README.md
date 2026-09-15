# `services/data` — Data Pipeline & Ingestion Service

## Module Overview
Responsible for acquiring, cleaning, standardizing, and feeding timeseries data into GridPilot AI.

- **Primary Data Backbone:** OpenSTEF Liander 2024 historical grid telemetry (15-minute resolution).
- **Secondary Sources:** EDS-lab PV datasets, UTSD Wind generation feeds.
- **Architectural Boundary:** Ingestion, validation, resampling, and feature preparation only. Never generates predictions or optimizes dispatch schedules.
- **Owned By:** Member 2 (Data + Demand Forecasting)
- **Branch:** `member/data-forecast`

## Key Responsibilities
1. Parse raw OpenSTEF datasets and weather feeds into unified timeseries frames.
2. Provide deterministic replay data for incident scenarios (e.g. `DEMAND_SPIKE_PLUS_RENEWABLE_DROP`).
3. Maintain data hygiene: handle missing values, duplicates, time-zone alignment (UTC/local), and prevent temporal leakage in training features.
