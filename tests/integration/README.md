# `tests/integration` — Integration Test Suites

## Module Overview
Verifies cross-service communication, shared contract conformance, and pipeline execution.

- **Primary Suites:**
  - `contract_validation.test.ts` — Asserts API responses adhere to `shared/contracts`.
  - `scenario_replay.test.ts` — Runs the deterministic `DEMAND_SPIKE_PLUS_RENEWABLE_DROP` end-to-end scenario.
  - `optimization_feasibility.test.ts` — Tests solver boundaries and constraint violations.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
