# `database/schema` — Database Schemas & DDL

## Module Overview
Defines relational schemas for PostgreSQL storing grid telemetry, historical predictions, anomaly events, optimization plans, and operator brief logs.

- **Primary Entities:**
  - `grid_telemetry` — 15-minute readings of demand, solar, wind, and battery status.
  - `demand_forecasts` — Predicted MW loads and spike probabilities.
  - `renewable_anomalies` — Detected asset underperformance and root cause classifications.
  - `optimization_runs` — Solved dispatch plans and before/after grid stress indices.
  - `operator_briefs` — Generated 8-part incident summaries and copilot conversation logs.
- **Owned By:** Member 1 (Team Leader) with Member 2
- **Branch:** `leader/integration`
