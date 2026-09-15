"""
GridPilot AI — Scenario Simulation
=====================================
8 predefined grid scenarios for testing and demonstrating the optimizer.
Each scenario generates realistic OptimizationInput data and runs it
through the real OR-Tools solver.

Chunk 7: simulateAction() / compareScenario()
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from services.optimization.models import (
    BatteryResource,
    EVResource,
    IndustrialFlexLoad,
    OptimizationInput,
    OptimizationResult,
    OptimizationWeights,
)
from services.optimization.optimizer import GridOptimizer


class ScenarioName(str, Enum):
    """The 8 predefined scenarios from the execution plan."""

    NORMAL_DAY = "NORMAL_DAY"
    EVENING_DEMAND_SPIKE = "EVENING_DEMAND_SPIKE"
    SOLAR_UNDERPERFORMANCE = "SOLAR_UNDERPERFORMANCE"
    HIGH_RENEWABLE_CURTAILMENT = "HIGH_RENEWABLE_CURTAILMENT"
    DEMAND_SPIKE_PLUS_RENEWABLE_DROP = "DEMAND_SPIKE_PLUS_RENEWABLE_DROP"
    BATTERY_UNAVAILABLE = "BATTERY_UNAVAILABLE"
    NO_FLEXIBLE_LOAD = "NO_FLEXIBLE_LOAD"
    INFEASIBLE_DEMAND = "INFEASIBLE_DEMAND"


@dataclass
class ScenarioComparison:
    """Before/after comparison of two scenario runs."""

    base_scenario: str
    modified_scenario: str
    base_result: OptimizationResult
    modified_result: OptimizationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseScenario": self.base_scenario,
            "modifiedScenario": self.modified_scenario,
            "baseResult": self.base_result.to_dict(),
            "modifiedResult": self.modified_result.to_dict(),
        }


# ---------------------------------------------------------------------------
# Default battery / EV / industrial resources used across scenarios
# ---------------------------------------------------------------------------

def _default_battery(
    soc: float = 25.0,
    max_discharge: float = 20.0,
    max_charge: float = 20.0,
    available: bool = True,
) -> Optional[BatteryResource]:
    if not available:
        return None
    return BatteryResource(
        resource_id="BESS_CENTRAL_01",
        current_soc_mwh=soc,
        min_soc_mwh=5.0,
        max_soc_mwh=50.0,
        max_charge_mw=max_charge,
        max_discharge_mw=max_discharge,
        efficiency=0.90,
    )


def _default_ev(available: bool = True) -> Optional[EVResource]:
    if not available:
        return None
    return EVResource(
        resource_id="EV_AGGREGATOR_01",
        current_demand_mw=12.0,
        flexible_fraction=0.40,
        shift_window_minutes=60,
    )


def _default_industrial(available: bool = True) -> Optional[IndustrialFlexLoad]:
    if not available:
        return None
    return IndustrialFlexLoad(
        resource_id="INDUSTRIAL_FLEX_FEEDER_04",
        current_demand_mw=28.0,
        flexible_fraction=0.30,
        shift_window_minutes=120,
        max_shift_mw=12.0,
    )


# ---------------------------------------------------------------------------
# Scenario Definitions — each returns a fully specified OptimizationInput
# ---------------------------------------------------------------------------

def build_scenario(
    name: ScenarioName,
    start_time: Optional[datetime] = None,
) -> OptimizationInput:
    """
    Build a complete OptimizationInput for the given scenario name.
    Each scenario has 4 periods (1 hour of 15-minute intervals).
    """
    if start_time is None:
        start_time = datetime.utcnow()

    n = 4  # 4 × 15 min = 1 hour

    builders = {
        ScenarioName.NORMAL_DAY: _normal_day,
        ScenarioName.EVENING_DEMAND_SPIKE: _evening_demand_spike,
        ScenarioName.SOLAR_UNDERPERFORMANCE: _solar_underperformance,
        ScenarioName.HIGH_RENEWABLE_CURTAILMENT: _high_renewable_curtailment,
        ScenarioName.DEMAND_SPIKE_PLUS_RENEWABLE_DROP: _demand_spike_plus_renewable_drop,
        ScenarioName.BATTERY_UNAVAILABLE: _battery_unavailable,
        ScenarioName.NO_FLEXIBLE_LOAD: _no_flexible_load,
        ScenarioName.INFEASIBLE_DEMAND: _infeasible_demand,
    }

    builder = builders[name]
    return builder(name.value, start_time, n)


# ---- Individual scenario builders ----


def _normal_day(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Balanced grid: moderate demand, healthy renewables, plenty of headroom.
    Expected: feasible, minimal actions needed.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[140.0, 142.0, 145.0, 143.0],
        solar_mw=[38.0, 40.0, 42.0, 39.0],
        wind_mw=[32.0, 33.0, 31.0, 34.0],
        other_generation_mw=[75.0, 75.0, 75.0, 75.0],
        ev_demand_mw=[10.0, 10.0, 10.0, 10.0],
        industrial_demand_mw=[25.0, 25.0, 25.0, 25.0],
        grid_capacity_mw=200.0,
        battery=_default_battery(),
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


def _evening_demand_spike(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Evening ramp: demand climbs sharply as solar drops.
    Expected: feasible, battery discharge + some load shifting.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[155.0, 168.0, 182.0, 190.0],
        solar_mw=[30.0, 18.0, 8.0, 2.0],
        wind_mw=[28.0, 26.0, 25.0, 24.0],
        other_generation_mw=[80.0, 80.0, 80.0, 80.0],
        ev_demand_mw=[14.0, 16.0, 18.0, 20.0],
        industrial_demand_mw=[28.0, 28.0, 28.0, 28.0],
        grid_capacity_mw=200.0,
        battery=_default_battery(soc=35.0),
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


def _solar_underperformance(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Midday with cloud cover: solar output is 40% of expected.
    Expected: feasible, battery covers the solar deficit.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[150.0, 152.0, 155.0, 153.0],
        solar_mw=[16.0, 15.0, 14.0, 17.0],  # expected ~40 MW
        wind_mw=[30.0, 31.0, 29.0, 32.0],
        other_generation_mw=[78.0, 78.0, 78.0, 78.0],
        ev_demand_mw=[10.0, 10.0, 10.0, 10.0],
        industrial_demand_mw=[26.0, 26.0, 26.0, 26.0],
        grid_capacity_mw=200.0,
        battery=_default_battery(soc=30.0),
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


def _high_renewable_curtailment(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Renewable surplus: generation exceeds grid capacity.
    Expected: feasible, battery charges, some curtailment remains.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[110.0, 108.0, 105.0, 107.0],
        solar_mw=[65.0, 70.0, 72.0, 68.0],
        wind_mw=[55.0, 58.0, 60.0, 56.0],
        other_generation_mw=[40.0, 40.0, 40.0, 40.0],
        ev_demand_mw=[8.0, 8.0, 8.0, 8.0],
        industrial_demand_mw=[20.0, 20.0, 20.0, 20.0],
        grid_capacity_mw=200.0,
        battery=_default_battery(soc=10.0, max_charge=20.0),  # low SOC = room to absorb
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


def _demand_spike_plus_renewable_drop(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Worst-case combination: demand surges while renewables fall.
    Expected: feasible but tight, heavy battery discharge + max load shifting.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[165.0, 178.0, 188.0, 195.0],
        solar_mw=[20.0, 12.0, 6.0, 3.0],
        wind_mw=[18.0, 14.0, 10.0, 8.0],
        other_generation_mw=[85.0, 85.0, 85.0, 85.0],
        ev_demand_mw=[14.0, 16.0, 18.0, 20.0],
        industrial_demand_mw=[30.0, 30.0, 30.0, 30.0],
        grid_capacity_mw=200.0,
        battery=_default_battery(soc=40.0, max_discharge=20.0),
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


def _battery_unavailable(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Battery offline: grid must balance without energy storage.
    Expected: feasible if renewables + load shifting are sufficient.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[155.0, 160.0, 165.0, 162.0],
        solar_mw=[35.0, 36.0, 34.0, 33.0],
        wind_mw=[28.0, 29.0, 30.0, 28.0],
        other_generation_mw=[80.0, 80.0, 80.0, 80.0],
        ev_demand_mw=[12.0, 12.0, 12.0, 12.0],
        industrial_demand_mw=[28.0, 28.0, 28.0, 28.0],
        grid_capacity_mw=200.0,
        battery=None,  # Battery unavailable
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


def _no_flexible_load(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    No demand-side flexibility: only battery can respond.
    Expected: feasible, battery does all the heavy lifting.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[160.0, 165.0, 170.0, 168.0],
        solar_mw=[32.0, 30.0, 28.0, 26.0],
        wind_mw=[25.0, 24.0, 23.0, 22.0],
        other_generation_mw=[80.0, 80.0, 80.0, 80.0],
        ev_demand_mw=[10.0, 10.0, 10.0, 10.0],
        industrial_demand_mw=[25.0, 25.0, 25.0, 25.0],
        grid_capacity_mw=200.0,
        battery=_default_battery(soc=35.0),
        ev=None,  # No EV flexibility
        industrial=None,  # No industrial flexibility
    )


def _infeasible_demand(
    scenario_id: str, start: datetime, n: int
) -> OptimizationInput:
    """
    Impossible scenario: demand far exceeds all available resources.
    Expected: INFEASIBLE with diagnostics.
    Required balancing ≈ 900 MW, available flexibility ≈ 40 MW.
    """
    return OptimizationInput(
        scenario_id=scenario_id,
        start_time=start,
        n_periods=n,
        demand_mw=[450.0, 480.0, 500.0, 520.0],
        solar_mw=[5.0, 4.0, 3.0, 2.0],
        wind_mw=[3.0, 2.0, 2.0, 1.0],
        other_generation_mw=[30.0, 30.0, 30.0, 30.0],
        ev_demand_mw=[5.0, 5.0, 5.0, 5.0],
        industrial_demand_mw=[10.0, 10.0, 10.0, 10.0],
        grid_capacity_mw=100.0,  # Very constrained
        battery=_default_battery(soc=8.0, max_discharge=10.0),
        ev=_default_ev(),
        industrial=_default_industrial(),
    )


# ---------------------------------------------------------------------------
# Scenario Simulator
# ---------------------------------------------------------------------------

class ScenarioSimulator:
    """
    Runs predefined scenarios through the real optimizer and provides
    before/after comparison.
    """

    def __init__(self, optimizer: Optional[GridOptimizer] = None) -> None:
        self.optimizer = optimizer or GridOptimizer()

    def simulate_action(
        self,
        scenario_name: ScenarioName,
        start_time: Optional[datetime] = None,
    ) -> OptimizationResult:
        """
        Build the named scenario and run it through the optimizer.

        Parameters
        ----------
        scenario_name : ScenarioName
            One of the 8 predefined scenarios.
        start_time : datetime, optional
            Override the scenario start time.

        Returns
        -------
        OptimizationResult
            The solver's result (feasible dispatch or infeasible diagnostics).
        """
        inp = build_scenario(scenario_name, start_time)
        return self.optimizer.solve(inp)

    def compare_scenario(
        self,
        base: ScenarioName,
        modified: ScenarioName,
        start_time: Optional[datetime] = None,
    ) -> ScenarioComparison:
        """
        Run two scenarios and return a side-by-side comparison.
        Useful for answering "what if Battery-01 is unavailable?"
        """
        base_result = self.simulate_action(base, start_time)
        modified_result = self.simulate_action(modified, start_time)

        return ScenarioComparison(
            base_scenario=base.value,
            modified_scenario=modified.value,
            base_result=base_result,
            modified_result=modified_result,
        )

    def run_all_scenarios(
        self, start_time: Optional[datetime] = None
    ) -> dict[str, OptimizationResult]:
        """Run all 8 scenarios and return a dict of results."""
        results = {}
        for name in ScenarioName:
            results[name.value] = self.simulate_action(name, start_time)
        return results
