# `services/optimization` — Mathematical Grid Optimization Service

## Module Overview
The authoritative mathematical decision engine of GridPilot AI. Computes constraint-feasible dispatch and load-balancing recommendations to minimize grid stress and prevent clean energy curtailment.

- **Engine:** Google OR-Tools (Mixed-Integer Linear Programming / SCIP solver).
- **Architectural Rule (Rule B):** The Optimizer is responsible for **DECISIONS ONLY**.
  - Calculates exact battery charge/discharge MW and timing.
  - Computes flexible industrial/EV load shifting schedules.
  - Calculates renewable curtailment mitigation.
  - Verifies physical feasibility (battery state-of-charge limits, ramp rates, line capacities).
  - The LLM and ML models must **never** invent dispatch numbers or bypass this optimizer.
- **Owned By:** Member 4 (Grid Optimization)
- **Branch:** `member/grid-optimization`

## Contract Conformance
Outputs strictly match `shared/contracts/OptimizationResult.ts`:
- `scenarioId`: Correlation ID of the optimization request.
- `status`: `"feasible"` | `"infeasible"`.
- `actions`: Array of discrete actions (`battery_charge`, `battery_discharge`, `shift_flexible_load`, `curtail_solar`, `curtail_wind`) with `resourceId`, `powerMw`, and time bounds.
- `before` / `after`: Metrics comparison (`demandMw`, `renewableMw`, `curtailmentMw`, `gridStressIndex`).
- `objectiveValue`: Cost/stress minimization objective score.
