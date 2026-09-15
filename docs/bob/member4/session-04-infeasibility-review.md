# Session 04 — Infeasibility Review (Member 4)

**Date:** 2024-07-15  
**Team Member:** Member 4 (Grid Optimization)  
**Branch:** `savan/grid-optimization`  
**Purpose:** Ask Bob to review the optimizer's infeasibility handling against a concrete stress scenario.

---

## Bob Prompt

```text
Review the optimization engine for infeasible scenarios.

Example:
Required balancing = 900 MW
Available flexibility = 650 MW

The solver must return INFEASIBLE with diagnostics.

Check:
- constraint violations
- over-allocation
- battery limits
- negative dispatch
- deficit reporting

Do not modify code.
```

---

## Bob Response Summary

Bob reviewed `services/optimization/optimizer.py` and `services/optimization/constraints.py`.

### Findings

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Solver correctly detects `INFEASIBLE` status from OR-Tools | ✅ Pass | Implemented |
| 2 | `diagnostics.deficit_mw` computed as `demand - max_available_flex` | ✅ Pass | Implemented |
| 3 | No fabricated actions returned when status = infeasible | ✅ Pass | Implemented |
| 4 | Battery SOC bounds enforced per period (not just initial) | ✅ Pass | Implemented |
| 5 | Negative dispatch values impossible (variables bounded ≥ 0) | ✅ Pass | Implemented |
| 6 | `has_errors()` gate prevents passing invalid input to solver | ✅ Pass | Implemented |

### Potential Risk Bob Identified

> "If `solver.Solve()` returns `ABNORMAL` (e.g. numerical issues at extreme scales), this should also be treated as infeasible rather than crashing."

**Resolution:** Already handled in our implementation — all non-`OPTIMAL` solver statuses fall through to the infeasible branch.

### Recommended Test Bob Suggested

```python
def test_infeasible_demand_returns_infeasible():
    # demand=9999, renewable=10, grid_cap=500 → must be INFEASIBLE
    result = optimizer.solve(inp)
    assert result.status == "infeasible"
    assert result.diagnostics is not None
    assert result.diagnostics.deficit_mw > 0
```

✅ This test is now in `TestOptimizerFeasibility` in `tests/test_optimization.py`.

---

## Files Bob Changed

None — read-only review session.

---

## What We Accepted

- Confirmation that infeasibility handling is correct
- The `ABNORMAL` edge-case observation (already handled)
- The concrete test recommendation (implemented)

## What We Rejected

- Nothing — Bob's review confirmed the implementation was correct

## Follow-up Work

Added `test_infeasible_demand_is_infeasible()` and `test_infeasible_result_has_diagnostics()` to the test suite.
