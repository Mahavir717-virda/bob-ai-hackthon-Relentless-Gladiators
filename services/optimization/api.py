"""FastAPI HTTP adapter for Grid Optimization Service (Port 8004).

Maps the Node.js API gateway payload schema to the real OptimizationInput
dataclasses used by GridOptimizer / OptimizationService.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Body

from services.optimization.service import OptimizationService
from services.optimization.models import (
    BatteryResource,
    EVResource,
    IndustrialFlexLoad,
    OptimizationInput,
    OptimizationWeights,
)

app = FastAPI(title="GridPilot Optimization Service", version="1.0.0")

_service: Optional[OptimizationService] = None


def get_service() -> OptimizationService:
    global _service
    if _service is None:
        _service = OptimizationService()
    return _service


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "grid_optimization"}


@app.get("/scenarios")
def list_scenarios() -> dict[str, Any]:
    """Return available predefined scenario names."""
    return {"scenarios": OptimizationService.get_available_scenarios()}


@app.post("/simulate")
def simulate_scenario(payload: dict = Body(...)) -> dict:
    """Run a named predefined scenario through the real optimizer."""
    try:
        service = get_service()
        scenario_name = payload.get("scenarioId", "NORMAL_DAY")
        start_time_raw = payload.get("targetTimestamp")
        start_time = (
            datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
            if start_time_raw
            else None
        )
        result = service.simulate_scenario(scenario_name, start_time)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_SCENARIO", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "SOLVER_EXECUTION_ERROR", "message": str(exc)},
        ) from exc


@app.post("/solve")
def solve(payload: dict = Body(...)) -> dict:
    """
    Solve the grid optimization problem with an arbitrary input payload.

    Expected payload shape (all optional — sensible defaults applied):
    {
      "scenarioId": str,
      "targetTimestamp": ISO8601 str,
      "horizonMinutes": int,          # total planning horizon (default 60)
      "periodMinutes": int,           # period granularity (default 15)
      "demandMw": float | list[float],
      "solarMw": float | list[float],
      "windMw": float | list[float],
      "otherGenerationMw": float | list[float],
      "gridCapacityMw": float,
      "battery": {
        "resourceId": str,
        "currentSocMwh": float,
        "minSocMwh": float,
        "maxSocMwh": float,
        "maxChargeMw": float,
        "maxDischargeMw": float,
        "efficiency": float
      },
      "evDemandMw": float | list[float],
      "industrialDemandMw": float | list[float]
    }
    """
    try:
        service = get_service()

        # ── Time ────────────────────────────────────────────────────────────
        target_raw = payload.get("targetTimestamp")
        if target_raw:
            start_time = datetime.fromisoformat(target_raw.replace("Z", "+00:00"))
        else:
            start_time = datetime.utcnow()

        horizon_minutes = int(payload.get("horizonMinutes", 60))
        period_minutes = int(payload.get("periodMinutes", 15))
        n_periods = max(1, horizon_minutes // period_minutes)

        # ── Helper: scalar → repeated list ──────────────────────────────────
        def to_list(val: Any, n: int, default: float = 0.0) -> list[float]:
            if isinstance(val, list):
                if len(val) == n:
                    return [float(v) for v in val]
                # Pad or trim
                base = [float(v) for v in val]
                return (base * n)[:n] if len(base) < n else base[:n]
            scalar = float(val) if val is not None else default
            return [scalar] * n

        demand_mw       = to_list(payload.get("demandMw"),           n_periods, 85.0)
        solar_mw        = to_list(payload.get("solarMw"),            n_periods, 0.0)
        wind_mw         = to_list(payload.get("windMw"),             n_periods, 0.0)
        other_gen_mw    = to_list(payload.get("otherGenerationMw"),  n_periods, 0.0)
        ev_demand_mw    = to_list(payload.get("evDemandMw"),         n_periods, 0.0)
        ind_demand_mw   = to_list(payload.get("industrialDemandMw"), n_periods, 0.0)

        grid_capacity_mw = float(payload.get("gridCapacityMw", 200.0))

        # ── Battery ──────────────────────────────────────────────────────────
        battery: Optional[BatteryResource] = None
        bc = payload.get("battery") or payload.get("batteryConstraints")
        if bc:
            max_cap  = float(bc.get("maxCapacityMwh", bc.get("maxSocMwh", 40.0)))
            cur_soc  = float(bc.get("currentSocMwh", bc.get("currentSocPercent", 50.0)))
            min_soc  = float(bc.get("minSocMwh", bc.get("minSocPercent", 10.0)))
            max_soc  = float(bc.get("maxSocMwh", max_cap * 0.9))

            # If values look like percentages (0-100), convert to MWh
            if cur_soc > 1.0 and max_cap > 0:
                cur_soc = cur_soc / 100.0 * max_cap
            if min_soc > 1.0 and max_cap > 0:
                min_soc = min_soc / 100.0 * max_cap
            if max_soc > max_cap:
                max_soc = max_cap

            battery = BatteryResource(
                resource_id=bc.get("resourceId", "BESS_01"),
                current_soc_mwh=cur_soc,
                min_soc_mwh=min_soc,
                max_soc_mwh=max_soc,
                max_charge_mw=float(bc.get("maxChargePowerMw", bc.get("maxChargeMw", 20.0))),
                max_discharge_mw=float(bc.get("maxDischargePowerMw", bc.get("maxDischargeMw", 20.0))),
                efficiency=float(bc.get("roundTripEfficiency", bc.get("efficiency", 0.9))),
            )

        # ── EV flexible load ─────────────────────────────────────────────────
        ev: Optional[EVResource] = None
        ev_raw = payload.get("ev")
        if ev_raw:
            ev = EVResource(
                resource_id=ev_raw.get("resourceId", "EV_FLEET_01"),
                current_demand_mw=float(ev_raw.get("currentDemandMw", 5.0)),
                flexible_fraction=float(ev_raw.get("flexibleFraction", 0.5)),
                shift_window_minutes=int(ev_raw.get("shiftWindowMinutes", 60)),
            )

        # ── Industrial flexible load ──────────────────────────────────────────
        industrial: Optional[IndustrialFlexLoad] = None
        fl = payload.get("flexibleLoad") or payload.get("flexibleLoadConstraints")
        if fl:
            total_flex = float(fl.get("totalFlexibleMw", fl.get("maxShiftMw", 10.0)))
            industrial = IndustrialFlexLoad(
                resource_id=fl.get("resourceId", "IND_FLEX_01"),
                current_demand_mw=total_flex * 2,  # flex is ~50% of total
                flexible_fraction=0.5,
                shift_window_minutes=int(fl.get("maxShiftDurationMinutes", fl.get("shiftWindowMinutes", 60))),
                max_shift_mw=total_flex,
            )

        # ── Build OptimizationInput ──────────────────────────────────────────
        opt_input = OptimizationInput(
            scenario_id=payload.get("scenarioId", "MANUAL_SOLVE"),
            start_time=start_time,
            n_periods=n_periods,
            period_minutes=period_minutes,
            demand_mw=demand_mw,
            solar_mw=solar_mw,
            wind_mw=wind_mw,
            other_generation_mw=other_gen_mw,
            ev_demand_mw=ev_demand_mw,
            industrial_demand_mw=ind_demand_mw,
            grid_capacity_mw=grid_capacity_mw,
            battery=battery,
            ev=ev,
            industrial=industrial,
            weights=OptimizationWeights(),
        )

        result = service.solve_dispatch(opt_input)
        return result.to_dict()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "SOLVER_EXECUTION_ERROR", "message": str(exc)},
        ) from exc


@app.post("/compare")
def compare_scenarios(payload: dict = Body(...)) -> dict:
    """Compare two named scenarios."""
    try:
        service = get_service()
        base = payload.get("baseScenario", "NORMAL_DAY")
        modified = payload.get("modifiedScenario", "EVENING_DEMAND_SPIKE")
        return service.compare_scenarios(base, modified)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "COMPARISON_ERROR", "message": str(exc)},
        ) from exc
