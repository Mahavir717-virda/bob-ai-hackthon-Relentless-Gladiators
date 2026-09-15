"""
GridPilot AI — OR-Tools MILP Grid Optimizer
=============================================
Core optimization engine implementing multi-period mixed-integer linear
programming for grid load balancing and renewable curtailment minimization.

Solver: Google OR-Tools with SCIP backend.

Chunks implemented:
  - Chunk 4: Load Balancing Optimizer
  - Chunk 5: Curtailment Minimization
  - Chunk 6: Feasibility Handling

See formulation.md for the complete mathematical formulation.
"""

from __future__ import annotations

import math
import time
from datetime import timedelta
from typing import Any

try:
    from ortools.linear_solver import pywraplp
except ImportError:
    pywraplp = None

from services.optimization.models import (
    OptimizationInput,
    OptimizationAction,
    OptimizationMetrics,
    OptimizationResult,
    InfeasibilityDiagnostics,
)
from services.optimization.constraints import (
    validate_optimization_input,
    has_errors,
    get_binding_constraint_names,
)


class GridOptimizer:
    """
    Multi-period MILP optimizer for grid load balancing.

    Uses Google OR-Tools (SCIP solver) to compute:
      - Battery charge/discharge dispatch schedules
      - EV and industrial flexible load shift recommendations
      - Renewable curtailment minimization
      - Feasibility diagnostics for impossible scenarios

    The optimizer CALCULATES actions. It never hardcodes expected results.
    """

    SOLVER_ID = "SCIP"
    SOLVER_NAME = "OR-Tools-SCIP"

    def __init__(self) -> None:
        pass

    def solve(self, inp: OptimizationInput) -> OptimizationResult:
        """
        Solve the grid optimization problem.

        Parameters
        ----------
        inp : OptimizationInput
            Complete problem specification including demand forecasts,
            renewable availability, resource constraints, and weights.

        Returns
        -------
        OptimizationResult
            Feasible dispatch plan OR infeasible diagnostics.
            Never fabricates a plan for an infeasible problem.
        """
        # ---- Step 1: Validate inputs ----
        violations = validate_optimization_input(inp)
        errors = [v for v in violations if v.severity == "error"]
        if errors:
            return OptimizationResult(
                scenario_id=inp.scenario_id,
                status="infeasible",
                diagnostics=InfeasibilityDiagnostics(
                    required_balancing_mw=0,
                    available_flexibility_mw=0,
                    estimated_deficit_mw=0,
                    binding_constraints=[str(e) for e in errors],
                ),
            )

        # ---- Step 2: Build and solve MILP ----
        t_start = time.time()
        solver = pywraplp.Solver.CreateSolver(self.SOLVER_ID)
        if solver is None:
            return OptimizationResult(
                scenario_id=inp.scenario_id,
                status="infeasible",
                diagnostics=InfeasibilityDiagnostics(
                    required_balancing_mw=0,
                    available_flexibility_mw=0,
                    estimated_deficit_mw=0,
                    binding_constraints=["SCIP solver not available."],
                ),
            )

        solver.SetTimeLimit(int(inp.time_limit_seconds * 1000))

        T = inp.n_periods
        dt = inp.dt_hours
        w = inp.weights
        infinity = solver.infinity()

        # ---- Step 3: Create decision variables ----

        # Battery variables
        p_charge = []
        p_discharge = []
        soc = []
        is_charging = []  # binary for mutual exclusion

        has_battery = inp.battery is not None and (
            inp.battery.max_charge_mw > 0 or inp.battery.max_discharge_mw > 0
        )

        if has_battery:
            bat = inp.battery
            eta_ch = bat.charge_efficiency
            eta_dis = bat.discharge_efficiency

            for t in range(T):
                p_charge.append(
                    solver.NumVar(0, bat.max_charge_mw, f"p_charge_{t}")
                )
                p_discharge.append(
                    solver.NumVar(0, bat.max_discharge_mw, f"p_discharge_{t}")
                )
                soc.append(
                    solver.NumVar(bat.min_soc_mwh, bat.max_soc_mwh, f"soc_{t}")
                )
                is_charging.append(
                    solver.IntVar(0, 1, f"is_charging_{t}")
                )

        # EV shift variables
        shift_ev = []
        has_ev = inp.ev is not None and inp.ev.max_shiftable_mw > 0

        if has_ev:
            for t in range(T):
                max_ev_shift = inp.ev.flexible_fraction * inp.ev_demand_mw[t]
                shift_ev.append(
                    solver.NumVar(0, max(0, max_ev_shift), f"shift_ev_{t}")
                )

        # Industrial shift variables
        shift_ind = []
        has_ind = (
            inp.industrial is not None
            and inp.industrial.max_shiftable_mw > 0
        )

        if has_ind:
            for t in range(T):
                max_ind_shift = min(
                    inp.industrial.flexible_fraction * inp.industrial_demand_mw[t],
                    inp.industrial.max_shift_mw,
                )
                shift_ind.append(
                    solver.NumVar(0, max(0, max_ind_shift), f"shift_ind_{t}")
                )

        # Renewable dispatch variables
        r_used = []
        curtail = []
        for t in range(T):
            total_renew = inp.solar_mw[t] + inp.wind_mw[t]
            r_used.append(
                solver.NumVar(0, max(0, total_renew), f"r_used_{t}")
            )
            curtail.append(
                solver.NumVar(0, max(0, total_renew), f"curtail_{t}")
            )

        # Imbalance slack variables
        deficit = []
        oversupply = []
        for t in range(T):
            deficit.append(solver.NumVar(0, infinity, f"deficit_{t}"))
            oversupply.append(solver.NumVar(0, infinity, f"oversupply_{t}"))

        # ---- Step 4: Add constraints ----

        # C1 + C2: Battery SOC dynamics and bounds
        if has_battery:
            for t in range(T):
                if t == 0:
                    # SOC[0] = SOC_init + η_ch * P_ch[0] * dt − P_dis[0] * dt / η_dis
                    solver.Add(
                        soc[0]
                        == bat.current_soc_mwh
                        + eta_ch * p_charge[0] * dt
                        - p_discharge[0] * dt / eta_dis,
                        f"soc_dynamics_{t}",
                    )
                else:
                    solver.Add(
                        soc[t]
                        == soc[t - 1]
                        + eta_ch * p_charge[t] * dt
                        - p_discharge[t] * dt / eta_dis,
                        f"soc_dynamics_{t}",
                    )

                # C3 + C4: Mutual exclusion via binary variable
                solver.Add(
                    p_charge[t] <= bat.max_charge_mw * is_charging[t],
                    f"charge_link_{t}",
                )
                solver.Add(
                    p_discharge[t] <= bat.max_discharge_mw * (1 - is_charging[t]),
                    f"discharge_link_{t}",
                )

        # C7: Renewable dispatch balance
        for t in range(T):
            total_renew = inp.solar_mw[t] + inp.wind_mw[t]
            solver.Add(
                r_used[t] + curtail[t] == total_renew,
                f"renew_balance_{t}",
            )

        # C8: Power balance
        for t in range(T):
            supply = inp.other_generation_mw[t] + r_used[t]
            if has_battery:
                supply += p_discharge[t] - p_charge[t]

            demand_side = inp.demand_mw[t]
            if has_ev:
                demand_side -= shift_ev[t]
            if has_ind:
                demand_side -= shift_ind[t]

            solver.Add(
                supply + deficit[t] - oversupply[t] == demand_side,
                f"power_balance_{t}",
            )

        # C9: Grid capacity
        for t in range(T):
            gen = inp.other_generation_mw[t] + r_used[t]
            if has_battery:
                gen += p_discharge[t]
            solver.Add(
                gen <= inp.grid_capacity_mw,
                f"grid_capacity_{t}",
            )

        # ---- Step 5: Objective function ----
        objective = solver.Objective()
        objective.SetMinimization()

        for t in range(T):
            # Curtailment penalty
            objective.SetCoefficient(curtail[t], w.curtailment)
            # Deficit penalty (very high)
            objective.SetCoefficient(deficit[t], w.deficit)
            # Oversupply penalty (mild)
            objective.SetCoefficient(oversupply[t], w.oversupply)
            # Battery cycling cost
            if has_battery:
                objective.SetCoefficient(p_charge[t], w.battery_cycling)
                objective.SetCoefficient(p_discharge[t], w.battery_cycling)
            # EV disruption
            if has_ev:
                objective.SetCoefficient(shift_ev[t], w.ev_disruption)
            # Industrial disruption
            if has_ind:
                objective.SetCoefficient(shift_ind[t], w.industrial_disruption)

        # ---- Step 6: Solve ----
        status = solver.Solve()
        solve_time = time.time() - t_start

        # ---- Step 7: Extract solution ----
        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return self._extract_solution(
                inp, solver, status, solve_time,
                p_charge, p_discharge, soc, is_charging,
                shift_ev, shift_ind, r_used, curtail,
                deficit, oversupply,
                has_battery, has_ev, has_ind,
            )
        else:
            return self._build_infeasible_result(inp, solve_time)

    def _extract_solution(
        self,
        inp: OptimizationInput,
        solver: pywraplp.Solver,
        status: int,
        solve_time: float,
        p_charge: list,
        p_discharge: list,
        soc: list,
        is_charging: list,
        shift_ev: list,
        shift_ind: list,
        r_used: list,
        curtail: list,
        deficit: list,
        oversupply: list,
        has_battery: bool,
        has_ev: bool,
        has_ind: bool,
    ) -> OptimizationResult:
        """Convert solved MILP variables into OptimizationResult contract."""

        T = inp.n_periods
        dt = inp.dt_hours
        actions: list[OptimizationAction] = []

        # --- Aggregate battery actions ---
        if has_battery:
            total_charge = sum(p_charge[t].solution_value() for t in range(T))
            total_discharge = sum(p_discharge[t].solution_value() for t in range(T))

            if total_discharge > 0.01:
                # Find the time window of discharge
                dis_start, dis_end = self._find_action_window(
                    [p_discharge[t].solution_value() for t in range(T)],
                    inp.start_time,
                    inp.period_minutes,
                )
                avg_discharge = total_discharge / max(
                    1,
                    sum(1 for t in range(T) if p_discharge[t].solution_value() > 0.01),
                )
                actions.append(
                    OptimizationAction(
                        resource_id=inp.battery.resource_id,
                        action_type="battery_discharge",
                        power_mw=round(avg_discharge, 2),
                        start_time=dis_start,
                        end_time=dis_end,
                    )
                )

            if total_charge > 0.01:
                ch_start, ch_end = self._find_action_window(
                    [p_charge[t].solution_value() for t in range(T)],
                    inp.start_time,
                    inp.period_minutes,
                )
                avg_charge = total_charge / max(
                    1,
                    sum(1 for t in range(T) if p_charge[t].solution_value() > 0.01),
                )
                actions.append(
                    OptimizationAction(
                        resource_id=inp.battery.resource_id,
                        action_type="battery_charge",
                        power_mw=round(avg_charge, 2),
                        start_time=ch_start,
                        end_time=ch_end,
                    )
                )

        # --- Aggregate EV shift actions ---
        if has_ev:
            total_ev_shift = sum(shift_ev[t].solution_value() for t in range(T))
            if total_ev_shift > 0.01:
                ev_start, ev_end = self._find_action_window(
                    [shift_ev[t].solution_value() for t in range(T)],
                    inp.start_time,
                    inp.period_minutes,
                )
                avg_ev = total_ev_shift / max(
                    1,
                    sum(1 for t in range(T) if shift_ev[t].solution_value() > 0.01),
                )
                actions.append(
                    OptimizationAction(
                        resource_id=inp.ev.resource_id,
                        action_type="shift_ev_load",
                        power_mw=round(avg_ev, 2),
                        start_time=ev_start,
                        end_time=ev_end,
                    )
                )

        # --- Aggregate industrial shift actions ---
        if has_ind:
            total_ind_shift = sum(shift_ind[t].solution_value() for t in range(T))
            if total_ind_shift > 0.01:
                ind_start, ind_end = self._find_action_window(
                    [shift_ind[t].solution_value() for t in range(T)],
                    inp.start_time,
                    inp.period_minutes,
                )
                avg_ind = total_ind_shift / max(
                    1,
                    sum(1 for t in range(T) if shift_ind[t].solution_value() > 0.01),
                )
                actions.append(
                    OptimizationAction(
                        resource_id=inp.industrial.resource_id,
                        action_type="shift_industrial_load",
                        power_mw=round(avg_ind, 2),
                        start_time=ind_start,
                        end_time=ind_end,
                    )
                )

        # --- Curtailment actions (by renewable type) ---
        total_curtail = sum(curtail[t].solution_value() for t in range(T))
        if total_curtail > 0.01:
            # Attribute curtailment proportionally to solar and wind
            total_solar = sum(inp.solar_mw)
            total_wind = sum(inp.wind_mw)
            total_renew = total_solar + total_wind

            if total_renew > 0:
                solar_fraction = total_solar / total_renew
                wind_fraction = total_wind / total_renew

                if solar_fraction > 0:
                    curt_start, curt_end = self._find_action_window(
                        [curtail[t].solution_value() * solar_fraction for t in range(T)],
                        inp.start_time,
                        inp.period_minutes,
                    )
                    actions.append(
                        OptimizationAction(
                            resource_id="SOLAR_GRID",
                            action_type="curtail_solar",
                            power_mw=round(total_curtail * solar_fraction / T, 2),
                            start_time=curt_start,
                            end_time=curt_end,
                        )
                    )
                if wind_fraction > 0:
                    curt_start, curt_end = self._find_action_window(
                        [curtail[t].solution_value() * wind_fraction for t in range(T)],
                        inp.start_time,
                        inp.period_minutes,
                    )
                    actions.append(
                        OptimizationAction(
                            resource_id="WIND_GRID",
                            action_type="curtail_wind",
                            power_mw=round(total_curtail * wind_fraction / T, 2),
                            start_time=curt_start,
                            end_time=curt_end,
                        )
                    )

        # --- Compute before / after metrics ---
        before = self._compute_before_metrics(inp)
        after = self._compute_after_metrics(
            inp, r_used, curtail, deficit, oversupply,
            p_charge, p_discharge, shift_ev, shift_ind,
            has_battery, has_ev, has_ind,
        )

        return OptimizationResult(
            scenario_id=inp.scenario_id,
            status="feasible",
            actions=actions,
            before=before,
            after=after,
            objective_value=solver.Objective().Value(),
            solver_name=self.SOLVER_NAME,
            solve_time_seconds=solve_time,
        )

    def _compute_before_metrics(
        self, inp: OptimizationInput
    ) -> OptimizationMetrics:
        """Compute grid metrics WITHOUT optimization (baseline)."""
        avg_demand = sum(inp.demand_mw) / max(1, inp.n_periods)
        avg_solar = sum(inp.solar_mw) / max(1, inp.n_periods)
        avg_wind = sum(inp.wind_mw) / max(1, inp.n_periods)
        avg_renew = avg_solar + avg_wind
        avg_other = sum(inp.other_generation_mw) / max(1, inp.n_periods)

        # Without optimization: all excess renewable is curtailed
        usable_renew = min(avg_renew, max(0, avg_demand - avg_other))
        curtailment_before = max(0, avg_renew - usable_renew)

        # Grid stress: how much net demand vs capacity
        net_demand = max(0, avg_demand - avg_renew - avg_other)
        stress = min(1.0, net_demand / inp.grid_capacity_mw) if inp.grid_capacity_mw > 0 else 1.0

        return OptimizationMetrics(
            demand_mw=round(avg_demand, 2),
            renewable_mw=round(avg_renew, 2),
            curtailment_mw=round(curtailment_before, 2),
            grid_stress=round(stress, 4),
        )

    def _compute_after_metrics(
        self,
        inp: OptimizationInput,
        r_used: list,
        curtail: list,
        deficit: list,
        oversupply: list,
        p_charge: list,
        p_discharge: list,
        shift_ev: list,
        shift_ind: list,
        has_battery: bool,
        has_ev: bool,
        has_ind: bool,
    ) -> OptimizationMetrics:
        """Compute grid metrics AFTER optimization."""
        T = inp.n_periods

        avg_r_used = sum(r_used[t].solution_value() for t in range(T)) / max(1, T)
        avg_curtail = sum(curtail[t].solution_value() for t in range(T)) / max(1, T)

        # Effective demand after load shifting
        avg_demand = sum(inp.demand_mw) / max(1, T)
        if has_ev:
            avg_demand -= sum(shift_ev[t].solution_value() for t in range(T)) / max(1, T)
        if has_ind:
            avg_demand -= sum(shift_ind[t].solution_value() for t in range(T)) / max(1, T)

        # Net unmet demand after all actions
        avg_other = sum(inp.other_generation_mw) / max(1, T)
        battery_net = 0.0
        if has_battery:
            battery_net = (
                sum(p_discharge[t].solution_value() for t in range(T))
                - sum(p_charge[t].solution_value() for t in range(T))
            ) / max(1, T)

        net_demand = max(0, avg_demand - avg_r_used - avg_other - battery_net)
        stress = min(1.0, net_demand / inp.grid_capacity_mw) if inp.grid_capacity_mw > 0 else 1.0

        return OptimizationMetrics(
            demand_mw=round(avg_demand, 2),
            renewable_mw=round(avg_r_used, 2),
            curtailment_mw=round(avg_curtail, 2),
            grid_stress=round(stress, 4),
        )

    def _build_infeasible_result(
        self, inp: OptimizationInput, solve_time: float
    ) -> OptimizationResult:
        """
        Construct an infeasible result with diagnostics.

        Chunk 6: Never fabricate a plan for an infeasible problem.
        """
        # Compute diagnostics
        avg_demand = sum(inp.demand_mw) / max(1, inp.n_periods)
        avg_supply = sum(
            inp.other_generation_mw[t] + inp.solar_mw[t] + inp.wind_mw[t]
            for t in range(inp.n_periods)
        ) / max(1, inp.n_periods)

        required = max(0, avg_demand - avg_supply)

        flexibility = 0.0
        if inp.battery:
            flexibility += inp.battery.max_discharge_mw
        if inp.ev:
            flexibility += inp.ev.max_shiftable_mw
        if inp.industrial:
            flexibility += inp.industrial.max_shiftable_mw

        deficit_mw = max(0, required - flexibility)
        binding = get_binding_constraint_names(inp)

        return OptimizationResult(
            scenario_id=inp.scenario_id,
            status="infeasible",
            before=self._compute_before_metrics(inp),
            objective_value=0.0,
            solver_name=self.SOLVER_NAME,
            solve_time_seconds=solve_time,
            diagnostics=InfeasibilityDiagnostics(
                required_balancing_mw=round(required, 2),
                available_flexibility_mw=round(flexibility, 2),
                estimated_deficit_mw=round(deficit_mw, 2),
                binding_constraints=binding,
            ),
        )

    @staticmethod
    def _find_action_window(
        values: list[float],
        start_time,
        period_minutes: int,
    ) -> tuple[str, str]:
        """
        Find the start and end time of an action based on which
        periods have non-zero values.
        """
        first_active = 0
        last_active = len(values) - 1

        for i, v in enumerate(values):
            if v > 0.01:
                first_active = i
                break

        for i in range(len(values) - 1, -1, -1):
            if values[i] > 0.01:
                last_active = i
                break

        action_start = start_time + timedelta(minutes=first_active * period_minutes)
        action_end = start_time + timedelta(minutes=(last_active + 1) * period_minutes)

        # Use strftime to produce a clean UTC ISO string without timezone offset suffix.
        # datetime.isoformat() can emit "+00:00" for tz-aware datetimes, which combined
        # with the appended "Z" yields an invalid timestamp that fails Date.parse().
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return action_start.strftime(fmt), action_end.strftime(fmt)
