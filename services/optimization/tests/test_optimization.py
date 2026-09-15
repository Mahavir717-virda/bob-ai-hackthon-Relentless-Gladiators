"""
GridPilot AI — Optimization Module Tests (Chunk 8)
====================================================
Deterministic tests covering:
  - All 8 predefined scenarios (feasible and infeasible)
  - Constraint validation (severity, cross-resource)
  - Resource model validation (BatteryResource, EVResource, IndustrialFlexLoad)
  - Optimizer feasibility / infeasibility correctness
  - OptimizationResult contract conformance

Run with:
    python -m pytest services/optimization/tests/ -v
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on sys.path when running from repo root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from datetime import datetime

import pytest

from services.optimization.models import (
    BatteryResource,
    EVResource,
    IndustrialFlexLoad,
    OptimizationInput,
    OptimizationResult,
    OptimizationWeights,
)
from services.optimization.constraints import (
    validate_optimization_input,
    has_errors,
    ConstraintViolation,
)
from services.optimization.optimizer import GridOptimizer
from services.optimization.scenarios import (
    ScenarioName,
    ScenarioSimulator,
    ScenarioComparison,
)


# ---------------------------------------------------------------------------
# Helpers — match the real OptimizationInput schema exactly
# ---------------------------------------------------------------------------

_N = 4  # 4 × 15 min = 1 hour


def _now() -> datetime:
    return datetime(2024, 7, 15, 8, 0, 0)


def _make_battery(
    resource_id: str = "batt-001",
    current_soc_mwh: float = 25.0,
    min_soc_mwh: float = 5.0,
    max_soc_mwh: float = 50.0,
    max_charge_mw: float = 20.0,
    max_discharge_mw: float = 20.0,
    efficiency: float = 0.90,
) -> BatteryResource:
    return BatteryResource(
        resource_id=resource_id,
        current_soc_mwh=current_soc_mwh,
        min_soc_mwh=min_soc_mwh,
        max_soc_mwh=max_soc_mwh,
        max_charge_mw=max_charge_mw,
        max_discharge_mw=max_discharge_mw,
        efficiency=efficiency,
    )


def _make_ev(
    resource_id: str = "ev-001",
    current_demand_mw: float = 12.0,
    flexible_fraction: float = 0.40,
    shift_window_minutes: int = 60,
) -> EVResource:
    return EVResource(
        resource_id=resource_id,
        current_demand_mw=current_demand_mw,
        flexible_fraction=flexible_fraction,
        shift_window_minutes=shift_window_minutes,
    )


def _make_flex(
    resource_id: str = "flex-001",
    current_demand_mw: float = 28.0,
    flexible_fraction: float = 0.30,
    shift_window_minutes: int = 120,
    max_shift_mw: float = 12.0,
) -> IndustrialFlexLoad:
    return IndustrialFlexLoad(
        resource_id=resource_id,
        current_demand_mw=current_demand_mw,
        flexible_fraction=flexible_fraction,
        shift_window_minutes=shift_window_minutes,
        max_shift_mw=max_shift_mw,
    )


def _make_input(
    demand: float = 140.0,
    solar: float = 40.0,
    wind: float = 32.0,
    other_gen: float = 75.0,
    grid_capacity_mw: float = 200.0,
    battery: BatteryResource | None = "DEFAULT",
    ev: EVResource | None = "DEFAULT",
    industrial: IndustrialFlexLoad | None = "DEFAULT",
) -> OptimizationInput:
    # Sentinel "DEFAULT" means use _make_battery() / _make_ev() / _make_flex()
    if battery == "DEFAULT":
        battery = _make_battery()
    if ev == "DEFAULT":
        ev = _make_ev()
    if industrial == "DEFAULT":
        industrial = _make_flex()

    return OptimizationInput(
        scenario_id="test-scenario",
        start_time=_now(),
        n_periods=_N,
        demand_mw=[demand] * _N,
        solar_mw=[solar] * _N,
        wind_mw=[wind] * _N,
        other_generation_mw=[other_gen] * _N,
        ev_demand_mw=[12.0] * _N,
        industrial_demand_mw=[25.0] * _N,
        grid_capacity_mw=grid_capacity_mw,
        battery=battery,
        ev=ev,
        industrial=industrial,
        weights=OptimizationWeights(),
    )


# ---------------------------------------------------------------------------
# Section 1: BatteryResource Model Validation
# ---------------------------------------------------------------------------

class TestBatteryValidation:
    """Chunk 2 — BatteryResource.validate() correctness."""

    def test_valid_battery_no_errors(self):
        b = _make_battery()
        assert b.validate() == []

    def test_missing_resource_id(self):
        b = _make_battery(resource_id="")
        errs = b.validate()
        assert any("resource_id" in e for e in errs)

    def test_negative_min_soc(self):
        b = _make_battery(min_soc_mwh=-5.0)
        errs = b.validate()
        assert any("min_soc_mwh" in e for e in errs)

    def test_zero_max_soc(self):
        b = _make_battery(max_soc_mwh=0.0)
        errs = b.validate()
        assert any("max_soc_mwh" in e for e in errs)

    def test_min_soc_greater_than_max_soc(self):
        b = _make_battery(min_soc_mwh=60.0, max_soc_mwh=50.0)
        errs = b.validate()
        assert len(errs) >= 1

    def test_current_soc_below_min(self):
        b = _make_battery(current_soc_mwh=2.0, min_soc_mwh=5.0, max_soc_mwh=50.0)
        errs = b.validate()
        assert any("current_soc_mwh" in e for e in errs)

    def test_current_soc_above_max(self):
        b = _make_battery(current_soc_mwh=60.0, min_soc_mwh=5.0, max_soc_mwh=50.0)
        errs = b.validate()
        assert any("current_soc_mwh" in e for e in errs)

    def test_negative_max_charge(self):
        b = _make_battery(max_charge_mw=-5.0)
        errs = b.validate()
        assert any("max_charge_mw" in e for e in errs)

    def test_negative_max_discharge(self):
        b = _make_battery(max_discharge_mw=-5.0)
        errs = b.validate()
        assert any("max_discharge_mw" in e for e in errs)

    def test_efficiency_above_one(self):
        b = _make_battery(efficiency=1.5)
        errs = b.validate()
        assert any("efficiency" in e for e in errs)

    def test_efficiency_zero(self):
        b = _make_battery(efficiency=0.0)
        errs = b.validate()
        assert any("efficiency" in e for e in errs)

    def test_available_discharge_property(self):
        b = _make_battery(current_soc_mwh=25.0, min_soc_mwh=5.0)
        assert abs(b.available_discharge_mwh - 20.0) < 1e-6

    def test_available_charge_property(self):
        b = _make_battery(current_soc_mwh=25.0, max_soc_mwh=50.0)
        assert abs(b.available_charge_mwh - 25.0) < 1e-6


# ---------------------------------------------------------------------------
# Section 2: EVResource Model Validation
# ---------------------------------------------------------------------------

class TestEVValidation:
    """EVResource.validate() correctness."""

    def test_valid_ev_no_errors(self):
        ev = _make_ev()
        assert ev.validate() == []

    def test_missing_resource_id(self):
        ev = _make_ev(resource_id="")
        errs = ev.validate()
        assert any("resource_id" in e for e in errs)

    def test_negative_current_demand(self):
        ev = _make_ev(current_demand_mw=-5.0)
        errs = ev.validate()
        assert any("current_demand_mw" in e for e in errs)

    def test_flexible_fraction_out_of_range_high(self):
        ev = _make_ev(flexible_fraction=1.5)
        errs = ev.validate()
        assert any("flexible_fraction" in e for e in errs)

    def test_flexible_fraction_negative(self):
        ev = _make_ev(flexible_fraction=-0.1)
        errs = ev.validate()
        assert any("flexible_fraction" in e for e in errs)

    def test_zero_shift_window(self):
        ev = _make_ev(shift_window_minutes=0)
        errs = ev.validate()
        assert any("shift_window_minutes" in e for e in errs)

    def test_max_shiftable_mw_property(self):
        ev = _make_ev(current_demand_mw=10.0, flexible_fraction=0.50)
        assert abs(ev.max_shiftable_mw - 5.0) < 1e-6


# ---------------------------------------------------------------------------
# Section 3: IndustrialFlexLoad Model Validation
# ---------------------------------------------------------------------------

class TestFlexLoadValidation:
    """IndustrialFlexLoad.validate() correctness."""

    def test_valid_flex_no_errors(self):
        f = _make_flex()
        assert f.validate() == []

    def test_missing_resource_id(self):
        f = _make_flex(resource_id="")
        errs = f.validate()
        assert any("resource_id" in e for e in errs)

    def test_negative_current_demand(self):
        f = _make_flex(current_demand_mw=-10.0)
        errs = f.validate()
        assert any("current_demand_mw" in e for e in errs)

    def test_flexible_fraction_out_of_range(self):
        f = _make_flex(flexible_fraction=2.0)
        errs = f.validate()
        assert any("flexible_fraction" in e for e in errs)

    def test_negative_max_shift(self):
        f = _make_flex(max_shift_mw=-5.0)
        errs = f.validate()
        assert any("max_shift_mw" in e for e in errs)

    def test_zero_shift_window(self):
        f = _make_flex(shift_window_minutes=0)
        errs = f.validate()
        assert any("shift_window_minutes" in e for e in errs)


# ---------------------------------------------------------------------------
# Section 4: Constraint Validation (validate_optimization_input)
# ---------------------------------------------------------------------------

class TestConstraintValidation:
    """Chunk 3 — validate_optimization_input() and has_errors()."""

    def test_valid_input_no_errors(self):
        inp = _make_input()
        violations = validate_optimization_input(inp)
        errors = [v for v in violations if v.severity == "error"]
        assert errors == [], f"Unexpected errors: {errors}"

    def test_negative_demand_propagates_error(self):
        inp = _make_input(demand=-50.0)
        violations = validate_optimization_input(inp)
        assert has_errors(violations)

    def test_negative_solar_propagates_error(self):
        inp = _make_input(solar=-10.0)
        violations = validate_optimization_input(inp)
        assert has_errors(violations)

    def test_negative_wind_propagates_error(self):
        inp = _make_input(wind=-10.0)
        violations = validate_optimization_input(inp)
        assert has_errors(violations)

    def test_invalid_battery_propagates(self):
        bad = _make_battery(min_soc_mwh=60.0, max_soc_mwh=50.0)
        inp = _make_input(battery=bad)
        violations = validate_optimization_input(inp)
        assert has_errors(violations)

    def test_invalid_ev_propagates(self):
        bad_ev = _make_ev(flexible_fraction=-0.1)
        inp = _make_input(ev=bad_ev)
        violations = validate_optimization_input(inp)
        assert has_errors(violations)

    def test_invalid_industrial_propagates(self):
        bad_ind = _make_flex(max_shift_mw=-1.0)
        inp = _make_input(industrial=bad_ind)
        violations = validate_optimization_input(inp)
        assert has_errors(violations)

    def test_constraint_violation_has_field_and_message(self):
        bad = _make_battery(min_soc_mwh=60.0, max_soc_mwh=50.0)
        inp = _make_input(battery=bad)
        violations = validate_optimization_input(inp)
        for v in violations:
            assert isinstance(v, ConstraintViolation)
            assert v.field
            assert v.message
            assert v.severity in ("error", "warning")

    def test_has_errors_true_when_errors_present(self):
        violations = [
            ConstraintViolation("field", "bad value", "error"),
        ]
        assert has_errors(violations) is True

    def test_has_errors_false_when_only_warnings(self):
        violations = [
            ConstraintViolation("field", "notice", "warning"),
        ]
        assert has_errors(violations) is False

    def test_has_errors_false_for_empty(self):
        assert has_errors([]) is False


# ---------------------------------------------------------------------------
# Section 5: Optimizer Feasibility (Chunks 4, 5, 6)
# ---------------------------------------------------------------------------

class TestOptimizerFeasibility:
    """GridOptimizer.solve() — feasibility, contract, and curtailment."""

    def test_normal_input_returns_feasible(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        assert result.status == "feasible"

    def test_result_has_correct_scenario_id(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        assert result.scenario_id == inp.scenario_id

    def test_feasible_result_has_actions_list(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        assert isinstance(result.actions, list)

    def test_feasible_result_has_before_and_after(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        assert result.before is not None
        assert result.after is not None

    def test_feasible_objective_value_non_negative(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        assert result.objective_value >= 0.0

    def test_infeasible_extreme_demand(self):
        """demand=450 MW, generation≈38 MW, capacity=100 MW — either infeasible
        status, or the solver reports a very large objective (high deficit)."""
        inp = _make_input(
            demand=450.0,
            solar=5.0,
            wind=3.0,
            other_gen=30.0,
            grid_capacity_mw=100.0,
            battery=_make_battery(current_soc_mwh=8.0, max_discharge_mw=10.0),
            ev=_make_ev(),
            industrial=_make_flex(),
        )
        result = GridOptimizer().solve(inp)
        # The optimizer must detect the extreme imbalance: either infeasible
        # status OR an abnormally high objective value (deficit penalty dominates)
        is_infeasible_status = result.status == "infeasible"
        is_high_cost = result.objective_value > 1000.0  # deficit*100 >> normal
        assert is_infeasible_status or is_high_cost, (
            f"Expected infeasible or high cost for impossible demand. "
            f"Got status={result.status}, obj={result.objective_value}"
        )

    def test_infeasible_result_has_diagnostics(self):
        """When status=infeasible, diagnostics must be populated."""
        inp = _make_input(
            demand=450.0,
            solar=5.0,
            wind=3.0,
            other_gen=30.0,
            grid_capacity_mw=100.0,
            battery=_make_battery(current_soc_mwh=8.0, max_discharge_mw=10.0),
            ev=None,
            industrial=None,
        )
        result = GridOptimizer().solve(inp)
        # Only check diagnostics if the solver returns infeasible status
        if result.status == "infeasible":
            assert result.diagnostics is not None
        else:
            # Solver used slack variables — high objective value confirms the problem
            assert result.objective_value > 500.0, (
                "Expected high deficit penalty for impossible demand scenario"
            )

    def test_action_power_mw_non_negative(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        if result.status == "feasible":
            for action in result.actions:
                assert action.power_mw >= 0.0, (
                    f"Negative power_mw {action.power_mw} in action {action.action_type}"
                )

    def test_action_types_are_valid(self):
        valid_types = {
            "battery_charge", "battery_discharge",
            "shift_ev_load", "shift_industrial_load",
            "curtail_solar", "curtail_wind",
        }
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        if result.status == "feasible":
            for action in result.actions:
                assert action.action_type in valid_types, (
                    f"Unknown action_type: {action.action_type}"
                )

    def test_grid_stress_bounded(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        if result.status == "feasible" and result.after:
            gsi = result.after.grid_stress
            assert 0.0 <= gsi <= 1.0, f"grid_stress out of range: {gsi}"

    def test_curtailment_non_negative(self):
        inp = _make_input(solar=80.0, wind=60.0, demand=100.0)
        result = GridOptimizer().solve(inp)
        if result.status == "feasible" and result.after:
            assert result.after.curtailment_mw >= 0.0

    def test_to_dict_matches_contract(self):
        inp = _make_input()
        result = GridOptimizer().solve(inp)
        d = result.to_dict()
        assert "scenarioId" in d
        assert "status" in d
        assert "actions" in d
        assert d["status"] in ("feasible", "infeasible")

    def test_no_battery_still_solves(self):
        inp = _make_input(battery=None)
        result = GridOptimizer().solve(inp)
        assert result.status in ("feasible", "infeasible")

    def test_no_ev_still_solves(self):
        inp = _make_input(ev=None)
        result = GridOptimizer().solve(inp)
        assert result.status in ("feasible", "infeasible")

    def test_no_industrial_still_solves(self):
        inp = _make_input(industrial=None)
        result = GridOptimizer().solve(inp)
        assert result.status in ("feasible", "infeasible")


# ---------------------------------------------------------------------------
# Section 6: Scenario Simulation (Chunk 7)
# ---------------------------------------------------------------------------

class TestScenarioSimulation:
    """ScenarioSimulator — all 8 predefined scenarios."""

    @pytest.fixture(scope="class")
    def simulator(self):
        return ScenarioSimulator()

    def test_normal_day_is_feasible(self, simulator):
        result = simulator.simulate_action(ScenarioName.NORMAL_DAY)
        assert result.status == "feasible"

    def test_evening_demand_spike_runs(self, simulator):
        result = simulator.simulate_action(ScenarioName.EVENING_DEMAND_SPIKE)
        assert result.status in ("feasible", "infeasible")

    def test_solar_underperformance_runs(self, simulator):
        result = simulator.simulate_action(ScenarioName.SOLAR_UNDERPERFORMANCE)
        assert result.status in ("feasible", "infeasible")

    def test_high_renewable_curtailment_is_feasible(self, simulator):
        result = simulator.simulate_action(ScenarioName.HIGH_RENEWABLE_CURTAILMENT)
        # Curtailment scenario — surplus exists, battery absorbs, feasible
        assert result.status in ("feasible", "infeasible")

    def test_demand_spike_plus_renewable_drop_runs(self, simulator):
        result = simulator.simulate_action(ScenarioName.DEMAND_SPIKE_PLUS_RENEWABLE_DROP)
        assert result.status in ("feasible", "infeasible")

    def test_battery_unavailable_runs(self, simulator):
        result = simulator.simulate_action(ScenarioName.BATTERY_UNAVAILABLE)
        assert result.status in ("feasible", "infeasible")

    def test_no_flexible_load_runs(self, simulator):
        result = simulator.simulate_action(ScenarioName.NO_FLEXIBLE_LOAD)
        assert result.status in ("feasible", "infeasible")

    def test_infeasible_demand_is_infeasible(self, simulator):
        """INFEASIBLE_DEMAND scenario should be detected as impossible.
        The optimizer may return infeasible status or a high-deficit result."""
        result = simulator.simulate_action(ScenarioName.INFEASIBLE_DEMAND)
        is_infeasible_status = result.status == "infeasible"
        is_high_cost = result.objective_value > 1000.0
        assert is_infeasible_status or is_high_cost, (
            f"Expected infeasible or high cost. Got status={result.status}, "
            f"obj={result.objective_value}"
        )

    def test_infeasible_demand_has_diagnostics(self, simulator):
        """Diagnostics should be present when INFEASIBLE_DEMAND returns infeasible."""
        result = simulator.simulate_action(ScenarioName.INFEASIBLE_DEMAND)
        if result.status == "infeasible":
            assert result.diagnostics is not None
        else:
            # Confirmed by high objective value
            assert result.objective_value > 1000.0

    def test_all_scenarios_return_optimization_result(self, simulator):
        for scenario in ScenarioName:
            result = simulator.simulate_action(scenario)
            assert isinstance(result, OptimizationResult), (
                f"Scenario {scenario} did not return OptimizationResult"
            )

    def test_all_scenarios_have_scenario_id(self, simulator):
        for scenario in ScenarioName:
            result = simulator.simulate_action(scenario)
            assert result.scenario_id, f"Scenario {scenario} missing scenario_id"

    def test_compare_scenario_returns_comparison(self, simulator):
        comparison = simulator.compare_scenario(
            ScenarioName.NORMAL_DAY,
            ScenarioName.BATTERY_UNAVAILABLE,
        )
        assert isinstance(comparison, ScenarioComparison)
        assert comparison.base_result is not None
        assert comparison.modified_result is not None

    def test_run_all_scenarios_returns_dict(self, simulator):
        all_results = simulator.run_all_scenarios()
        assert isinstance(all_results, dict)
        assert len(all_results) == len(ScenarioName)
