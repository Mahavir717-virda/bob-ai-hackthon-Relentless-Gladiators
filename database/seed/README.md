# `database/seed` — Seed Data & Deterministic Scenarios

## Module Overview
Contains deterministic fixture data for testing and demonstration.

- **Primary Scenario Fixture:** `DEMAND_SPIKE_PLUS_RENEWABLE_DROP`
  - Replays OpenSTEF historical telemetry with an +18% demand surge.
  - Injects unexpected solar generation drop from 42 MW down to 19 MW.
  - Triggers Isolation Forest anomaly (score 0.88) with `cloud_cover` root cause (84% confidence).
  - Supplies initial conditions for OR-Tools to dispatch 15 MW battery storage and 8 MW industrial load shift.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
