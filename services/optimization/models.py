"""
GridPilot AI — Optimization Resource Models
=============================================
Data classes for battery energy storage, EV charging, industrial flexible loads,
renewable sources, grid state, and optimization I/O contracts.

Every resource is validated before it reaches the solver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Resource Models (Chunk 2)
# ---------------------------------------------------------------------------

@dataclass
class BatteryResource:
    """
    Battery Energy Storage System (BESS) resource.

    Physical constraints:
      - SOC must stay within [min_soc_mwh, max_soc_mwh]
      - Charge/discharge rates bounded
      - Charge and discharge are mutually exclusive per period
      - Round-trip efficiency < 1 represents energy losses
    """

    resource_id: str
    current_soc_mwh: float
    min_soc_mwh: float
    max_soc_mwh: float
    max_charge_mw: float
    max_discharge_mw: float
    efficiency: float = 0.90  # round-trip efficiency

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []

        if not self.resource_id:
            errors.append("Battery resource_id is required.")

        if self.min_soc_mwh < 0:
            errors.append(
                f"min_soc_mwh ({self.min_soc_mwh}) must be >= 0."
            )
        if self.max_soc_mwh <= 0:
            errors.append(
                f"max_soc_mwh ({self.max_soc_mwh}) must be > 0."
            )
        if self.min_soc_mwh > self.max_soc_mwh:
            errors.append(
                f"min_soc_mwh ({self.min_soc_mwh}) > max_soc_mwh ({self.max_soc_mwh})."
            )
        if self.current_soc_mwh < self.min_soc_mwh:
            errors.append(
                f"current_soc_mwh ({self.current_soc_mwh}) < min_soc_mwh ({self.min_soc_mwh})."
            )
        if self.current_soc_mwh > self.max_soc_mwh:
            errors.append(
                f"current_soc_mwh ({self.current_soc_mwh}) > max_soc_mwh ({self.max_soc_mwh})."
            )
        if self.max_charge_mw < 0:
            errors.append(
                f"max_charge_mw ({self.max_charge_mw}) must be >= 0."
            )
        if self.max_discharge_mw < 0:
            errors.append(
                f"max_discharge_mw ({self.max_discharge_mw}) must be >= 0."
            )
        if not (0.0 < self.efficiency <= 1.0):
            errors.append(
                f"efficiency ({self.efficiency}) must be in (0, 1]."
            )

        return errors

    @property
    def charge_efficiency(self) -> float:
        """One-way charge efficiency = √(round-trip efficiency)."""
        return math.sqrt(self.efficiency)

    @property
    def discharge_efficiency(self) -> float:
        """One-way discharge efficiency = √(round-trip efficiency)."""
        return math.sqrt(self.efficiency)

    @property
    def available_discharge_mwh(self) -> float:
        """Energy available to discharge before hitting min SOC."""
        return max(0.0, self.current_soc_mwh - self.min_soc_mwh)

    @property
    def available_charge_mwh(self) -> float:
        """Energy capacity remaining before hitting max SOC."""
        return max(0.0, self.max_soc_mwh - self.current_soc_mwh)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceId": self.resource_id,
            "currentSocMwh": self.current_soc_mwh,
            "minSocMwh": self.min_soc_mwh,
            "maxSocMwh": self.max_soc_mwh,
            "maxChargeMw": self.max_charge_mw,
            "maxDischargeMw": self.max_discharge_mw,
            "efficiency": self.efficiency,
        }


@dataclass
class EVResource:
    """
    Electric Vehicle charging aggregation resource.

    A fraction of EV charging demand is flexible and can be shifted
    to a later time window to relieve grid stress.
    """

    resource_id: str
    current_demand_mw: float
    flexible_fraction: float  # 0.0 – 1.0
    shift_window_minutes: int = 60  # how far load can be deferred

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.resource_id:
            errors.append("EV resource_id is required.")
        if self.current_demand_mw < 0:
            errors.append(
                f"current_demand_mw ({self.current_demand_mw}) must be >= 0."
            )
        if not (0.0 <= self.flexible_fraction <= 1.0):
            errors.append(
                f"flexible_fraction ({self.flexible_fraction}) must be in [0, 1]."
            )
        if self.shift_window_minutes <= 0:
            errors.append(
                f"shift_window_minutes ({self.shift_window_minutes}) must be > 0."
            )

        return errors

    @property
    def max_shiftable_mw(self) -> float:
        """Maximum MW that can be shifted away."""
        return self.current_demand_mw * self.flexible_fraction

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceId": self.resource_id,
            "currentDemandMw": self.current_demand_mw,
            "flexibleFraction": self.flexible_fraction,
            "shiftWindowMinutes": self.shift_window_minutes,
        }


@dataclass
class IndustrialFlexLoad:
    """
    Industrial flexible load resource.

    Large industrial consumers may agree to reduce or defer a fraction
    of their load during grid stress events.
    """

    resource_id: str
    current_demand_mw: float
    flexible_fraction: float  # 0.0 – 1.0
    shift_window_minutes: int = 120
    max_shift_mw: float = 15.0  # cap on instantaneous shift

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.resource_id:
            errors.append("Industrial resource_id is required.")
        if self.current_demand_mw < 0:
            errors.append(
                f"current_demand_mw ({self.current_demand_mw}) must be >= 0."
            )
        if not (0.0 <= self.flexible_fraction <= 1.0):
            errors.append(
                f"flexible_fraction ({self.flexible_fraction}) must be in [0, 1]."
            )
        if self.shift_window_minutes <= 0:
            errors.append(
                f"shift_window_minutes ({self.shift_window_minutes}) must be > 0."
            )
        if self.max_shift_mw < 0:
            errors.append(
                f"max_shift_mw ({self.max_shift_mw}) must be >= 0."
            )

        return errors

    @property
    def max_shiftable_mw(self) -> float:
        """Maximum MW that can be shifted, respecting both fraction and cap."""
        return min(
            self.current_demand_mw * self.flexible_fraction,
            self.max_shift_mw,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceId": self.resource_id,
            "currentDemandMw": self.current_demand_mw,
            "flexibleFraction": self.flexible_fraction,
            "shiftWindowMinutes": self.shift_window_minutes,
            "maxShiftMw": self.max_shift_mw,
        }


@dataclass
class RenewableSource:
    """Single renewable generation asset (solar or wind)."""

    asset_id: str
    asset_type: str  # "solar" | "wind"
    available_mw: float  # available generation capacity right now

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.asset_id:
            errors.append("Renewable asset_id is required.")
        if self.asset_type not in ("solar", "wind"):
            errors.append(
                f"asset_type must be 'solar' or 'wind', got '{self.asset_type}'."
            )
        if self.available_mw < 0:
            errors.append(
                f"available_mw ({self.available_mw}) must be >= 0."
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "assetId": self.asset_id,
            "assetType": self.asset_type,
            "availableMw": self.available_mw,
        }


# ---------------------------------------------------------------------------
# Grid State (Chunk 3)
# ---------------------------------------------------------------------------

@dataclass
class GridState:
    """
    Snapshot of the current grid operating state.

    Aggregates demand, generation, and resource availability
    for a single point in time or a series of periods.
    """

    timestamp: datetime
    demand_mw: float
    other_generation_mw: float  # non-flexible conventional generation
    grid_capacity_mw: float
    renewable_sources: list[RenewableSource] = field(default_factory=list)

    @property
    def total_renewable_mw(self) -> float:
        return sum(r.available_mw for r in self.renewable_sources)

    @property
    def solar_mw(self) -> float:
        return sum(
            r.available_mw for r in self.renewable_sources if r.asset_type == "solar"
        )

    @property
    def wind_mw(self) -> float:
        return sum(
            r.available_mw for r in self.renewable_sources if r.asset_type == "wind"
        )

    @property
    def grid_stress(self) -> float:
        """Grid stress index ∈ [0, 1]. Higher = more stressed."""
        if self.grid_capacity_mw <= 0:
            return 1.0
        net_demand = self.demand_mw - self.total_renewable_mw
        stress = max(0.0, net_demand) / self.grid_capacity_mw
        return min(1.0, stress)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.demand_mw < 0:
            errors.append(f"demand_mw ({self.demand_mw}) must be >= 0.")
        if self.other_generation_mw < 0:
            errors.append(
                f"other_generation_mw ({self.other_generation_mw}) must be >= 0."
            )
        if self.grid_capacity_mw <= 0:
            errors.append(
                f"grid_capacity_mw ({self.grid_capacity_mw}) must be > 0."
            )
        for r in self.renewable_sources:
            errors.extend(r.validate())
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() + "Z",
            "demandMw": self.demand_mw,
            "otherGenerationMw": self.other_generation_mw,
            "gridCapacityMw": self.grid_capacity_mw,
            "totalRenewableMw": self.total_renewable_mw,
            "gridStress": round(self.grid_stress, 4),
            "renewableSources": [r.to_dict() for r in self.renewable_sources],
        }


# ---------------------------------------------------------------------------
# Optimization I/O Contracts
# ---------------------------------------------------------------------------

@dataclass
class OptimizationWeights:
    """Configurable objective function weights."""

    curtailment: float = 10.0
    deficit: float = 100.0
    oversupply: float = 1.0
    battery_cycling: float = 0.5
    ev_disruption: float = 2.0
    industrial_disruption: float = 3.0


@dataclass
class OptimizationInput:
    """
    Complete input to the optimization solver.

    Contains the grid state time series and all available flexible resources
    for a set of time periods (each 15 minutes).
    """

    scenario_id: str
    start_time: datetime
    n_periods: int  # number of 15-minute periods
    period_minutes: int = 15

    # Per-period arrays (length = n_periods)
    demand_mw: list[float] = field(default_factory=list)
    solar_mw: list[float] = field(default_factory=list)
    wind_mw: list[float] = field(default_factory=list)
    other_generation_mw: list[float] = field(default_factory=list)
    ev_demand_mw: list[float] = field(default_factory=list)
    industrial_demand_mw: list[float] = field(default_factory=list)

    # Grid
    grid_capacity_mw: float = 200.0

    # Resources
    battery: Optional[BatteryResource] = None
    ev: Optional[EVResource] = None
    industrial: Optional[IndustrialFlexLoad] = None

    # Solver config
    weights: OptimizationWeights = field(default_factory=OptimizationWeights)
    time_limit_seconds: float = 30.0

    @property
    def dt_hours(self) -> float:
        """Duration of one period in hours."""
        return self.period_minutes / 60.0

    def validate(self) -> list[str]:
        """Validate the full optimization input. Returns list of errors."""
        errors: list[str] = []

        if self.n_periods <= 0:
            errors.append(f"n_periods ({self.n_periods}) must be > 0.")

        # Check array lengths
        for name, arr in [
            ("demand_mw", self.demand_mw),
            ("solar_mw", self.solar_mw),
            ("wind_mw", self.wind_mw),
            ("other_generation_mw", self.other_generation_mw),
            ("ev_demand_mw", self.ev_demand_mw),
            ("industrial_demand_mw", self.industrial_demand_mw),
        ]:
            if len(arr) != self.n_periods:
                errors.append(
                    f"{name} length ({len(arr)}) != n_periods ({self.n_periods})."
                )

        # Check non-negative values
        for name, arr in [
            ("demand_mw", self.demand_mw),
            ("solar_mw", self.solar_mw),
            ("wind_mw", self.wind_mw),
            ("other_generation_mw", self.other_generation_mw),
        ]:
            for t, v in enumerate(arr):
                if v < 0:
                    errors.append(f"{name}[{t}] = {v} is negative.")

        # Check grid capacity
        if self.grid_capacity_mw <= 0:
            errors.append(
                f"grid_capacity_mw ({self.grid_capacity_mw}) must be > 0."
            )

        # Validate sub-resources
        if self.battery:
            errors.extend(self.battery.validate())
        if self.ev:
            errors.extend(self.ev.validate())
        if self.industrial:
            errors.extend(self.industrial.validate())

        return errors


@dataclass
class OptimizationAction:
    """A single dispatch action recommended by the optimizer."""

    resource_id: str
    action_type: str  # battery_charge, battery_discharge, shift_ev_load, shift_industrial_load, curtail_solar, curtail_wind
    power_mw: float
    start_time: str  # ISO 8601
    end_time: str  # ISO 8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceId": self.resource_id,
            "actionType": self.action_type,
            "powerMw": round(self.power_mw, 2),
            "startTime": self.start_time,
            "endTime": self.end_time,
        }


@dataclass
class OptimizationMetrics:
    """Before/after grid metrics snapshot."""

    demand_mw: float
    renewable_mw: float
    curtailment_mw: float
    grid_stress: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "demandMw": round(self.demand_mw, 2),
            "renewableMw": round(self.renewable_mw, 2),
            "curtailmentMw": round(self.curtailment_mw, 2),
            "gridStress": round(self.grid_stress, 4),
            "gridStressIndex": round(self.grid_stress, 4),
        }


@dataclass
class InfeasibilityDiagnostics:
    """Diagnostics returned when the optimization is infeasible."""

    required_balancing_mw: float
    available_flexibility_mw: float
    estimated_deficit_mw: float
    binding_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requiredBalancingMw": round(self.required_balancing_mw, 2),
            "availableFlexibilityMw": round(self.available_flexibility_mw, 2),
            "estimatedDeficitMw": round(self.estimated_deficit_mw, 2),
            "bindingConstraints": self.binding_constraints,
        }


@dataclass
class OptimizationResult:
    """
    Complete optimization result matching the shared OptimizationResult contract.

    Conforms to: shared/contracts/OptimizationResult.ts
    """

    scenario_id: str
    status: str  # "feasible" | "infeasible"
    actions: list[OptimizationAction] = field(default_factory=list)
    before: Optional[OptimizationMetrics] = None
    after: Optional[OptimizationMetrics] = None
    objective_value: float = 0.0
    solver_name: str = "OR-Tools-SCIP"
    solve_time_seconds: float = 0.0
    diagnostics: Optional[InfeasibilityDiagnostics] = None

    def _zero_metrics(self) -> "OptimizationMetrics":
        """Return a zeroed metrics object used when after-metrics are unavailable."""
        return OptimizationMetrics(
            demand_mw=0.0,
            renewable_mw=0.0,
            curtailment_mw=0.0,
            grid_stress=0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        # Map internal status to the SolverStatus enum expected by the TS contract.
        # "optimal" / "feasible" / "infeasible" are the only valid values.
        solver_status = "optimal" if self.status == "feasible" else "infeasible"

        # before/after are required (non-optional) in the contract; never emit null.
        before_dict = self.before.to_dict() if self.before else self._zero_metrics().to_dict()
        after_dict = self.after.to_dict() if self.after else self._zero_metrics().to_dict()

        result: dict[str, Any] = {
            "scenarioId": self.scenario_id,
            "status": self.status,
            "solverStatus": solver_status,
            "actions": [a.to_dict() for a in self.actions],
            "before": before_dict,
            "after": after_dict,
            "objectiveValue": round(self.objective_value, 4),
            "solveDurationMs": round(self.solve_time_seconds * 1000),
        }
        if self.diagnostics:
            result["diagnostics"] = self.diagnostics.to_dict()
        return result
