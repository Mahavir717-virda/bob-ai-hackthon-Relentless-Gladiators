# Session 02 — OR-Tools Design (Member 4)

**Date:** 2024-07-15  
**Team Member:** Member 4 (Grid Optimization)  
**Branch:** `savan/grid-optimization`  
**Purpose:** Use Bob to design the OR-Tools implementation plan (variable types, solver choice, output format).

---

## Bob Prompt

```text
Design the OR-Tools implementation plan.

Prefer linear programming.

Use MILP only when discrete decisions are actually required.

Include:
- variables
- constraints
- objective
- output format
- infeasibility behavior

Do not modify code.
```

---

## Bob Response Summary

Bob recommended the following OR-Tools architecture:

### Solver Selection

- **Solver:** `SCIP` via `pywraplp` (OR-Tools CP-SAT excluded — overkill for continuous power dispatch)
- **Mode:** MILP — binary variables **are** required for charge/discharge mutual exclusion
- **Time limit:** 30 seconds per solve (configurable)

### Variable Design

```python
# Continuous variables
p_charge[b][t]    = solver.NumVar(0, max_charge_mw, ...)
p_discharge[b][t] = solver.NumVar(0, max_discharge_mw, ...)
soc[b][t]         = solver.NumVar(min_soc_mwh, max_soc_mwh, ...)
curtail[t]        = solver.NumVar(0, renewable_mw, ...)

# Binary variables (mutual exclusion)
y_charge[b][t]    = solver.BoolVar(...)  # 1=charging
```

### Output Format

```json
{
  "scenario_id": "string",
  "status": "feasible|infeasible",
  "actions": [
    {"action_type": "battery_charge", "resource_id": "...", "power_mw": 0.0, "start_time": "...", "end_time": "..."}
  ],
  "before": {"demand_mw": 0.0, "renewable_mw": 0.0, "curtailment_mw": 0.0, "grid_stress_index": 0.0},
  "after":  {"demand_mw": 0.0, "renewable_mw": 0.0, "curtailment_mw": 0.0, "grid_stress_index": 0.0},
  "objective_value": 0.0
}
```

### Infeasibility Behavior

- If `solver.Solve()` returns `INFEASIBLE` or `ABNORMAL`, return `status="infeasible"`
- Include `diagnostics.deficit_mw` = demand - max available flexibility
- Never fabricate a "plan" for an infeasible scenario

---

## Files Bob Changed

None — read-only design session.

---

## What We Accepted

- `pywraplp` with SCIP backend (not CP-SAT)
- Binary `y_charge[b][t]` for mutual exclusion
- Explicit infeasibility diagnostics with deficit reporting
- The exact output contract fields

## What We Rejected

- Bob suggested a simplified single-period model first; we implemented multi-period from the start since the contract requires time-series actions

## Follow-up Work

Full implementation delivered in `services/optimization/optimizer.py` (618 lines, multi-period MILP).
