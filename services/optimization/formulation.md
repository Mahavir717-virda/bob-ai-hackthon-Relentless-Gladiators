# GridPilot Optimization — Mathematical Formulation

## 1. Overview

Multi-period Mixed-Integer Linear Program (MILP) for grid load balancing and
renewable curtailment minimization. Solved using Google OR-Tools with the SCIP
backend.

The optimizer receives demand/renewable forecasts and computes constraint-feasible
dispatch actions for battery energy storage, EV charging shifts, and industrial
flexible load reductions.

---

## 2. Sets

| Symbol | Description |
|--------|-------------|
| T = {0, 1, ..., n-1} | Time periods (each 15 minutes, Δt = 0.25 hours) |

---

## 3. Parameters

### Grid Parameters

| Symbol | Unit | Description |
|--------|------|-------------|
| D[t] | MW | Forecasted total demand at period t |
| R_solar[t] | MW | Available solar generation at period t |
| R_wind[t] | MW | Available wind generation at period t |
| G_other[t] | MW | Non-flexible conventional generation at period t |
| G_cap | MW | Maximum grid transmission capacity |

### Battery Parameters

| Symbol | Unit | Description |
|--------|------|-------------|
| SOC_init | MWh | Initial state of charge |
| SOC_min | MWh | Minimum allowed state of charge |
| SOC_max | MWh | Maximum capacity (state of charge) |
| P_ch_max | MW | Maximum charge rate |
| P_dis_max | MW | Maximum discharge rate |
| η | - | Round-trip efficiency (0 < η ≤ 1) |

Derived: η_ch = √η (charge efficiency), η_dis = √η (discharge efficiency)

### EV Charging Parameters

| Symbol | Unit | Description |
|--------|------|-------------|
| D_ev[t] | MW | EV charging demand at period t |
| f_ev | - | Flexible fraction (0 ≤ f_ev ≤ 1) |

### Industrial Flexible Load Parameters

| Symbol | Unit | Description |
|--------|------|-------------|
| D_ind[t] | MW | Industrial demand at period t |
| f_ind | - | Flexible fraction (0 ≤ f_ind ≤ 1) |
| S_ind_max | MW | Maximum instantaneous shift |

### Objective Weights

| Symbol | Default | Description |
|--------|---------|-------------|
| w_curt | 10.0 | Curtailment penalty (high — we want to minimize waste) |
| w_deficit | 100.0 | Demand deficit penalty (very high — grid stability) |
| w_oversupply | 1.0 | Oversupply penalty (mild — prefer slight oversupply to deficit) |
| w_battery | 0.5 | Battery cycling cost (degradation) |
| w_ev | 2.0 | EV load disruption cost |
| w_ind | 3.0 | Industrial load disruption cost |

---

## 4. Decision Variables

### Continuous Variables

| Variable | Bounds | Unit | Description |
|----------|--------|------|-------------|
| P_ch[t] | [0, P_ch_max] | MW | Battery charge power at period t |
| P_dis[t] | [0, P_dis_max] | MW | Battery discharge power at period t |
| SOC[t] | [SOC_min, SOC_max] | MWh | Battery SOC after period t |
| shift_ev[t] | [0, f_ev·D_ev[t]] | MW | EV load shifted at period t |
| shift_ind[t] | [0, min(f_ind·D_ind[t], S_ind_max)] | MW | Industrial load shifted at period t |
| R_used[t] | [0, R_solar[t]+R_wind[t]] | MW | Renewable generation dispatched |
| curtail[t] | [0, R_solar[t]+R_wind[t]] | MW | Renewable generation curtailed |
| deficit[t] | ≥ 0 | MW | Unmet demand (slack) |
| oversupply[t] | ≥ 0 | MW | Excess generation (slack) |

### Integer (Binary) Variables

| Variable | Domain | Description |
|----------|--------|-------------|
| z_ch[t] | {0, 1} | 1 if battery is charging at period t, 0 otherwise |

Used to enforce mutual exclusion of charge and discharge.

---

## 5. Constraints

### C1 — Battery SOC Dynamics

For t = 0:
```
SOC[0] = SOC_init + η_ch · P_ch[0] · Δt − P_dis[0] · Δt / η_dis
```

For t ≥ 1:
```
SOC[t] = SOC[t-1] + η_ch · P_ch[t] · Δt − P_dis[t] · Δt / η_dis
```

### C2 — Battery SOC Bounds
```
SOC_min ≤ SOC[t] ≤ SOC_max   ∀t ∈ T
```

### C3 — Battery Charge Rate Bound (linked to binary)
```
P_ch[t] ≤ P_ch_max · z_ch[t]   ∀t ∈ T
```

### C4 — Battery Discharge Rate Bound (mutual exclusion)
```
P_dis[t] ≤ P_dis_max · (1 − z_ch[t])   ∀t ∈ T
```

### C5 — EV Shift Bounds
```
0 ≤ shift_ev[t] ≤ f_ev · D_ev[t]   ∀t ∈ T
```

### C6 — Industrial Shift Bounds
```
0 ≤ shift_ind[t] ≤ min(f_ind · D_ind[t], S_ind_max)   ∀t ∈ T
```

### C7 — Renewable Dispatch Balance
```
R_used[t] + curtail[t] = R_solar[t] + R_wind[t]   ∀t ∈ T
```

### C8 — Power Balance
```
G_other[t] + R_used[t] + P_dis[t] − P_ch[t] + deficit[t] − oversupply[t]
  = D[t] − shift_ev[t] − shift_ind[t]   ∀t ∈ T
```

### C9 — Grid Capacity
```
G_other[t] + R_used[t] + P_dis[t] ≤ G_cap   ∀t ∈ T
```

---

## 6. Objective Function

```
Minimize  Σ_{t∈T} (
    w_curt      · curtail[t]
  + w_deficit   · deficit[t]
  + w_oversupply· oversupply[t]
  + w_battery   · (P_ch[t] + P_dis[t])
  + w_ev        · shift_ev[t]
  + w_ind       · shift_ind[t]
)
```

---

## 7. Feasibility Detection

If the solver returns `INFEASIBLE`, the system reports:

- Required balancing MW (total demand − total available generation)
- Available flexibility MW (battery discharge + EV shift + industrial shift)
- Estimated deficit MW
- Which constraints are most likely binding (via constraint analysis)

The solver never fabricates a plan for an infeasible problem.

---

## 8. Grid Stress Index

Pre-optimization:
```
stress_before = (D_total − R_total) / G_cap
```

Post-optimization:
```
stress_after = (D_adjusted − R_used_total − battery_net) / G_cap
```

Clamped to [0, 1].

---

## 9. Solver Configuration

- **Solver:** SCIP (via OR-Tools)
- **Time limit:** 30 seconds (configurable)
- **Relative gap:** 0.01 (1% optimality tolerance)
- **Formulation type:** MILP (binary variables for charge/discharge mutual exclusion only)
