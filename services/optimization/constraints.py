"""
GridPilot AI — Constraint Validation
======================================
Pre-solver validation of all grid resources and optimization inputs.
Catches physically impossible configurations before they reach OR-Tools.
"""

from __future__ import annotations

from services.optimization.models import (
    BatteryResource,
    EVResource,
    IndustrialFlexLoad,
    GridState,
    OptimizationInput,
)


class ConstraintViolation:
    """Represents a single constraint violation with severity."""

    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error" | "warning"

    def __repr__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


def validate_battery(battery: BatteryResource) -> list[ConstraintViolation]:
    """
    Validate battery resource constraints.
    Ensures physical consistency of SOC, charge/discharge rates, and efficiency.
    """
    violations: list[ConstraintViolation] = []

    for err in battery.validate():
        violations.append(ConstraintViolation("battery", err))

    # Physics warnings
    if battery.efficiency < 0.7:
        violations.append(
            ConstraintViolation(
                "battery.efficiency",
                f"Efficiency {battery.efficiency} is unusually low (< 0.7). "
                "Verify this is intentional.",
                severity="warning",
            )
        )

    if battery.max_charge_mw > 0 and battery.max_soc_mwh > 0:
        # Time to full charge
        hours_to_full = battery.available_charge_mwh / (
            battery.max_charge_mw * battery.charge_efficiency
        )
        if hours_to_full < 0.05:  # < 3 minutes
            violations.append(
                ConstraintViolation(
                    "battery",
                    f"Battery nearly full — only {hours_to_full * 60:.1f} min "
                    "to max SOC at max charge rate.",
                    severity="warning",
                )
            )

    return violations


def validate_ev(ev: EVResource) -> list[ConstraintViolation]:
    """Validate EV resource constraints."""
    violations: list[ConstraintViolation] = []

    for err in ev.validate():
        violations.append(ConstraintViolation("ev", err))

    if ev.flexible_fraction == 0.0 and ev.current_demand_mw > 0:
        violations.append(
            ConstraintViolation(
                "ev.flexible_fraction",
                "EV has demand but zero flexibility — it cannot participate "
                "in load shifting.",
                severity="warning",
            )
        )

    return violations


def validate_industrial(
    ind: IndustrialFlexLoad,
) -> list[ConstraintViolation]:
    """Validate industrial flexible load constraints."""
    violations: list[ConstraintViolation] = []

    for err in ind.validate():
        violations.append(ConstraintViolation("industrial", err))

    if ind.max_shift_mw < ind.current_demand_mw * ind.flexible_fraction:
        violations.append(
            ConstraintViolation(
                "industrial.max_shift_mw",
                f"max_shift_mw ({ind.max_shift_mw}) is below the computed "
                f"flexible capacity ({ind.current_demand_mw * ind.flexible_fraction:.2f} MW). "
                "The cap will bind.",
                severity="warning",
            )
        )

    return violations


def validate_grid_state(state: GridState) -> list[ConstraintViolation]:
    """Validate grid state snapshot."""
    violations: list[ConstraintViolation] = []

    for err in state.validate():
        violations.append(ConstraintViolation("grid_state", err))

    if state.grid_stress > 0.9:
        violations.append(
            ConstraintViolation(
                "grid_state.stress",
                f"Grid stress is critically high ({state.grid_stress:.2f}). "
                "Immediate action recommended.",
                severity="warning",
            )
        )

    return violations


def validate_optimization_input(
    inp: OptimizationInput,
) -> list[ConstraintViolation]:
    """
    Comprehensive validation of the full optimization input.

    Returns errors and warnings. The solver should not proceed if there
    are any violations with severity='error'.
    """
    violations: list[ConstraintViolation] = []

    # Base validation from the model
    for err in inp.validate():
        violations.append(ConstraintViolation("input", err))

    # Resource-specific validation
    if inp.battery:
        violations.extend(validate_battery(inp.battery))
    if inp.ev:
        violations.extend(validate_ev(inp.ev))
    if inp.industrial:
        violations.extend(validate_industrial(inp.industrial))

    # Cross-resource checks
    if len(inp.demand_mw) == inp.n_periods:
        max_demand = max(inp.demand_mw) if inp.demand_mw else 0
        total_flexibility = 0.0
        if inp.battery:
            total_flexibility += inp.battery.max_discharge_mw
        if inp.ev:
            total_flexibility += inp.ev.max_shiftable_mw
        if inp.industrial:
            total_flexibility += inp.industrial.max_shiftable_mw

        max_supply = max(
            (inp.other_generation_mw[t] + inp.solar_mw[t] + inp.wind_mw[t])
            for t in range(inp.n_periods)
        ) if inp.n_periods > 0 else 0

        if max_demand > max_supply + total_flexibility:
            violations.append(
                ConstraintViolation(
                    "supply_demand",
                    f"Peak demand ({max_demand:.1f} MW) exceeds maximum supply "
                    f"({max_supply:.1f} MW) + total flexibility "
                    f"({total_flexibility:.1f} MW). Problem may be infeasible.",
                    severity="warning",
                )
            )

    return violations


def has_errors(violations: list[ConstraintViolation]) -> bool:
    """Check if any violation is an error (not just warning)."""
    return any(v.severity == "error" for v in violations)


def get_binding_constraint_names(
    inp: OptimizationInput,
) -> list[str]:
    """
    Identify which constraints are most likely to be binding in an
    infeasible scenario. Used for diagnostics reporting.
    """
    binding: list[str] = []

    for t in range(inp.n_periods):
        total_supply = inp.other_generation_mw[t] + inp.solar_mw[t] + inp.wind_mw[t]
        if total_supply < inp.demand_mw[t]:
            binding.append(
                f"Period {t}: supply ({total_supply:.1f} MW) < demand ({inp.demand_mw[t]:.1f} MW)"
            )

    if inp.battery:
        if inp.battery.available_discharge_mwh < 1.0:
            binding.append(
                f"Battery SOC near minimum — only {inp.battery.available_discharge_mwh:.2f} MWh available"
            )
        if inp.battery.max_discharge_mw == 0:
            binding.append("Battery discharge disabled (max_discharge_mw = 0)")

    if inp.ev and inp.ev.flexible_fraction == 0:
        binding.append("EV flexibility is zero — no load shifting possible")

    if inp.industrial and inp.industrial.flexible_fraction == 0:
        binding.append("Industrial flexibility is zero — no load shifting possible")

    if inp.grid_capacity_mw > 0:
        for t in range(inp.n_periods):
            total_gen = inp.other_generation_mw[t] + inp.solar_mw[t] + inp.wind_mw[t]
            if total_gen > inp.grid_capacity_mw:
                binding.append(
                    f"Period {t}: generation ({total_gen:.1f} MW) exceeds "
                    f"grid capacity ({inp.grid_capacity_mw:.1f} MW)"
                )

    return binding
