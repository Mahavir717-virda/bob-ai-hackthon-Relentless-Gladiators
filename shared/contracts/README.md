# `shared/contracts` — Ground Truth System Contracts

## Module Overview
Houses canonical, immutable TypeScript interfaces defining data exchange between frontend, API gateway, ML services, optimizer, and AI agent.

- **Status:** Frozen interfaces (modifiable solely by Member 1 / Team Leader).
- **Core Interfaces:**
  1. `DemandForecast` — 15/30/60-min demand predictions and spike classification.
  2. `RenewableStatus` — Solar/wind telemetry, performance ratios, anomaly flags, and SHAP root cause.
  3. `OptimizationResult` — Feasible/infeasible dispatch actions, before/after metrics, objective value.
  4. `WeatherData` — Global horizontal irradiance, wind speed, temperature, cloud cover.
  5. `GridState` — Current 15-minute substation load, generation, battery state-of-charge.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
