# Session 01 — Mathematical Formulation (Member 4)

**Date:** 2024-07-15  
**Team Member:** Member 4 (Grid Optimization)  
**Branch:** `savan/grid-optimization`  
**Purpose:** Use Bob to identify decision variables, hard constraints, and objective terms for the grid optimization MILP.

---

## Bob Prompt

```text
Analyze the GridPilot optimization requirements.

Do not modify files.

Identify:
- decision variables
- hard constraints
- objective terms
- battery constraints
- EV/flexible-load constraints
- grid capacity
- renewable curtailment
- feasibility conditions

Return a mathematical formulation.
```

---

## Bob Response Summary

Bob analyzed the problem domain and returned the following mathematical formulation:

### Decision Variables

| Variable | Type | Description |
|---|---|---|
| `p_charge[b,t]` | Continuous ≥ 0 | Battery b charge power (MW) at period t |
| `p_discharge[b,t]` | Continuous ≥ 0 | Battery b discharge power (MW) at period t |
| `y[b,t]` | Binary {0,1} | 1 = charging, 0 = discharging (mutual exclusion) |
| `soc[b,t]` | Continuous | Battery b State of Charge (MWh) at end of period t |
| `p_flex[f,t]` | Continuous | Industrial flexible load f (MW) at period t |
| `p_ev[e,t]` | Continuous | EV fleet e charge rate (MW) at period t |
| `curtail[t]` | Continuous ≥ 0 | Curtailed renewable energy (MW) at period t |

### Hard Constraints

1. **Energy Balance:** `renewable[t] - curtail[t] + discharge[t] - charge[t] + flex_shift[t] = demand[t]`
2. **Grid Capacity:** Total flow ≤ `grid_capacity_mw`
3. **Battery SOC Dynamics:** `soc[b,t] = soc[b,t-1] + η·charge[b,t] - discharge[b,t]`
4. **SOC Bounds:** `min_soc_mwh ≤ soc[b,t] ≤ max_soc_mwh`
5. **Charge/Discharge Exclusion:** `charge[b,t] ≤ M·y[b,t]`, `discharge[b,t] ≤ M·(1-y[b,t])`
6. **Flexible Load Bounds:** `min_mw ≤ p_flex[f,t] ≤ max_mw`
7. **Curtailment Bound:** `0 ≤ curtail[t] ≤ renewable_available[t]`

### Objective Function

Minimize:
```
∑_t [ w1 · grid_stress[t] + w2 · curtail[t] + w3 · (demand[t] - renewable[t] + curtail[t]) ]
```

### Feasibility Conditions

- Demand cannot exceed grid capacity + available flexibility
- Battery SOC cannot go below minimum at any period
- Infeasibility must be explicitly detected and reported with a deficit diagnostic

---

## Files Bob Changed

None — this was a read-only analysis session.

---

## What We Accepted

- Complete mathematical formulation structure
- Mutual exclusion constraint design (binary variable `y[b,t]`)
- Feasibility detection requirement (never silently ignore infeasibility)

## What We Rejected

- Bob suggested using a pure LP relaxation; we decided to keep MILP because mutual exclusion requires binary variables

## Follow-up Work

Implemented in `services/optimization/formulation.md` (full LaTeX notation) and `services/optimization/optimizer.py` (OR-Tools SCIP backend).
