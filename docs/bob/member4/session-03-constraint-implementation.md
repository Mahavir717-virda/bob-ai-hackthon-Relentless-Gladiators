# Session 03 — Battery Constraint Implementation (Member 4)

**Date:** 2024-07-15  
**Team Member:** Member 4 (Grid Optimization)  
**Branch:** `savan/grid-optimization`  
**Purpose:** Ask Bob to implement a bounded task — battery constraint validation — with tests.

---

## Bob Prompt

```text
Implement validation for battery constraints.

Validate:
- current SOC
- minimum SOC
- maximum SOC
- maximum charge
- maximum discharge

Add tests.

Do not implement the complete optimizer.
```

---

## Bob Response Summary

Bob returned a `validate_battery()` function and pytest tests.

### Key Implementation Bob Contributed

```python
def validate_battery(battery: BatteryResource) -> list[str]:
    errors = []
    if not battery.resource_id:
        errors.append("Battery resource_id is required.")
    if battery.min_soc_mwh < 0:
        errors.append(f"min_soc_mwh ({battery.min_soc_mwh}) must be >= 0.")
    if battery.max_soc_mwh <= 0:
        errors.append(f"max_soc_mwh ({battery.max_soc_mwh}) must be > 0.")
    if battery.min_soc_mwh > battery.max_soc_mwh:
        errors.append(f"min_soc_mwh > max_soc_mwh.")
    if not (battery.min_soc_mwh <= battery.current_soc_mwh <= battery.max_soc_mwh):
        errors.append(f"current_soc_mwh out of [min, max] range.")
    if battery.max_charge_mw <= 0:
        errors.append(f"max_charge_mw must be > 0.")
    if battery.max_discharge_mw <= 0:
        errors.append(f"max_discharge_mw must be > 0.")
    if not (0 < battery.efficiency <= 1.0):
        errors.append(f"efficiency must be in (0, 1].")
    return errors
```

### Tests Bob Added

```python
def test_valid_battery_no_errors(): ...
def test_soc_out_of_bounds_low(): ...
def test_soc_out_of_bounds_high(): ...
def test_min_greater_than_max(): ...
def test_zero_max_charge(): ...
def test_efficiency_out_of_range(): ...
```

---

## Files Bob Changed (Conceptually)

- `services/optimization/models.py` — `BatteryResource.validate()` method
- `services/optimization/tests/test_optimization.py` — battery validation tests

---

## What We Accepted

- Full validation logic (integrated into `BatteryResource.validate()`)
- All test cases (incorporated into `TestBatteryValidation` class)
- Error message format (`"field_name (value) constraint"`)

## What We Rejected

- Bob suggested a standalone function; we integrated it as a method on the dataclass for cleaner API design

## Follow-up Work

Validation integrated into `validate_optimization_input()` in `constraints.py`, which runs all resource validations before the solver is called.
