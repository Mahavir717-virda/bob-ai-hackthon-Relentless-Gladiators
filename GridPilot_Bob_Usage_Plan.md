# GridPilot AI — IBM Bob Usage Plan
## Separate Bob Evidence Plan

This file is intentionally separate from the main engineering plan.

The project will be implemented primarily in the team's main development environment, while IBM Bob will be used for genuine, bounded engineering tasks and documented evidence.

Do not fabricate Bob sessions or claim Bob built work that was actually built elsewhere.

---

# 1. Bob Objective

Use IBM Bob for:

```text
Repository Understanding
        ↓
Architecture Planning
        ↓
Small Bounded Implementation
        ↓
Code / Model Review
        ↓
Testing Review
        ↓
Documentation
```

Do not spend Bob effort on rebuilding the entire project.

---

# 2. Bob Evidence Structure

Create:

```text
docs/bob/
├── member1/
├── member2/
├── member3/
└── member4/
```

Recommended evidence:

```text
docs/bob/member1/
├── session-01-architecture.md
├── session-02-contracts.md
├── session-03-api-review.md
├── session-04-llm-safety.md
└── session-05-integration-review.md

docs/bob/member2/
├── session-01-dataset-analysis.md
├── session-02-feature-design.md
├── session-03-feature-implementation.md
├── session-04-leakage-review.md
└── session-05-forecast-review.md

docs/bob/member3/
├── session-01-renewable-data.md
├── session-02-pipeline-design.md
├── session-03-performance-analysis.md
├── session-04-anomaly-review.md
└── session-05-root-cause-review.md

docs/bob/member4/
├── session-01-optimization-formulation.md
├── session-02-ortools-design.md
├── session-03-constraint-implementation.md
├── session-04-infeasibility-review.md
└── session-05-optimization-review.md
```

If the hackathon provides/export a formal Bob session/task report, preserve the official export as the primary evidence.

---

# 3. Everyone — Bob Session Pattern

For each member:

```text
Session 1 → Understand
Session 2 → Plan
Session 3 → Small real implementation
Session 4 → Review
Session 5 → Documentation / final review
```

Do not ask Bob to build an entire subsystem in one prompt.

---

# 4. Member 1 — Bob Prompts

## Session 1 — Architecture

```text
Analyze the current GridPilot repository.

The project implements U2:
Grid Load Optimisation & Renewable Energy Performance Advisor.

Do not modify files.

Review:
- architecture
- module boundaries
- dependencies
- shared interfaces
- integration risks
- four-member ownership model

Return an architecture review.
```

## Session 2 — Contracts

```text
Review the current GridPilot architecture.

Do not modify implementation code.

Design the interfaces between:

Demand Forecasting
Renewable Intelligence
Optimization
API/UI

Focus on:

DemandForecast
RenewableStatus
GridState
OptimizationInput
OptimizationResult

Explain every field and why it exists.
```

## Session 3 — Small real implementation

```text
Implement validation for the OptimizationResult contract.

Validate:
- required fields
- feasible/infeasible status
- MW numeric values
- action timestamps
- before/after metrics

Do not modify unrelated modules.

Add tests.
```

## Session 4 — LLM Safety Review

```text
Review the GridPilot LLM/operator-assistance design.

The LLM must:
- interpret structured outputs
- explain
- summarize
- answer operator questions

The LLM must NOT:
- invent forecasts
- calculate grid constraints
- select numerical dispatch quantities
- override optimization results

Return a risk review without modifying code.
```

## Session 5 — Integration Review

```text
Review the current integration branch.

Check:
- API consistency
- shared contracts
- service coupling
- error handling
- missing tests
- hardcoded results
- secret exposure
- LLM hallucination risks

Do not modify files.

Return prioritized findings.
```

---

# 5. Member 2 — Bob Prompts

## Session 1 — Dataset Analysis

```text
Analyze the demand-related portion of the OpenSTEF dataset in the project.

Do not modify files.

Identify:
- demand fields
- timestamp field
- frequency
- weather features
- missing-data risks
- leakage risks
- candidate lag features

Return a data-preparation plan.
```

## Session 2 — Forecast Design

```text
Design a demand forecasting pipeline for GridPilot.

Target:
15, 30 and 60 minute forecasts.

Primary model:
LightGBM.

Include:
- baselines
- feature engineering
- chronological split
- metrics
- leakage prevention
- model versioning

Do not modify files.
```

## Session 3 — Small real implementation

```text
Implement the demand feature-generation module.

Add:
- 15-minute lag
- 30-minute lag
- 1-hour lag
- 24-hour lag
- calendar features

Add tests for:
- timestamp ordering
- missing history
- future-data leakage

Do not modify unrelated modules.
```

## Session 4 — Leakage Review

```text
Review the current demand forecasting pipeline for data leakage.

Check:
- lag alignment
- rolling windows
- train/validation/test boundaries
- future weather information
- target leakage
- timestamp issues

Do not modify code.
Return confirmed issues and severity.
```

## Session 5 — Model Review

```text
Review the demand forecasting implementation.

Check:
- baseline comparison
- LightGBM training
- evaluation metrics
- reproducibility
- missing data behavior
- model versioning

Do not modify files.
```

---

# 6. Member 3 — Bob Prompts

## Session 1 — Renewable Data

```text
Analyze the solar and wind data available to GridPilot.

Do not modify files.

Identify:
- asset IDs
- generation fields
- weather fields
- operational fields
- timestamp frequency
- possible curtailment indicators

Return a data map.
```

## Session 2 — Pipeline Design

```text
Design the renewable intelligence pipeline.

It must include:

1. solar forecasting
2. wind forecasting
3. expected-vs-actual performance
4. anomaly detection
5. root-cause analysis

Recommended methods:
LightGBM
Isolation Forest
XGBoost + SHAP

Do not modify files.
```

## Session 3 — Small implementation

```text
Implement the renewable performance-ratio calculation.

Calculate:
actual / expected

Also calculate:
- absolute deviation
- percentage deviation

Handle zero expected generation safely.

Add tests.

Do not implement the entire anomaly subsystem.
```

## Session 4 — Anomaly Review

```text
Review the renewable anomaly design.

Check whether it can distinguish, where data allows:

- normal behavior
- weather-driven reduction
- physical underperformance
- intentional curtailment
- data-quality issues

Do not modify code.
Return false-positive risks.
```

## Session 5 — Root Cause Review

```text
Review the XGBoost + SHAP root-cause approach.

Check:
- feature interpretation
- correlation vs causation
- SHAP interpretation
- confidence representation
- curtailment handling

Do not modify code.
```

---

# 7. Member 4 — Bob Prompts

## Session 1 — Mathematical Formulation

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

## Session 2 — OR-Tools Design

```text
Design the OR-Tools implementation plan.

Prefer linear programming.

Use MILP only when discrete decisions are actually required.

Include:
- variables
- constraints
- objective
- output format
- infeasibility behavior

Do not modify code.
```

## Session 3 — Small implementation

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

## Session 4 — Infeasibility Review

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

## Session 5 — Optimization Review

```text
Review the complete optimization module.

Check:
- constraints
- objective function
- curtailment
- scenario simulation
- reproducibility
- infeasible behavior

Do not modify implementation.
Return prioritized findings.
```

---

# 8. How to Save Each Bob Session

For each session record:

```text
Date
Team Member
Purpose
Bob Prompt
Bob Response Summary
Files Bob Changed
What We Accepted
What We Rejected
Follow-up Work
```

Example:

```markdown
# Session 3 — Feature Engineering

Member:
M2

Purpose:
Implement demand lag features.

Prompt:
<exact Bob prompt>

Bob changed:
services/forecasting/features.py
tests/forecasting/test_features.py

Accepted:
- lag 15m
- lag 30m
- lag 60m
- lag 24h

Rejected:
- automatic feature selection because it was unnecessary for MVP.

Follow-up:
Full model training performed in the team's primary development environment.
```

Use the exact session prompt/result where possible.

---

# 9. Do Not Do These Things

Do not:

```text
fabricate session reports
claim Bob built the whole project
claim Bob trained models if it did not
claim Bob deployed infrastructure if it did not
copy generated output into the report without actually using it
```

Do:

```text
use Bob for bounded genuine tasks
keep prompts
keep useful responses
keep small real code changes
keep reviews
keep documentation evidence
```

---

# 10. Best Evidence Per Member

| Member | Strongest Bob Evidence |
|---|---|
| M1 | Architecture + contracts + LLM safety + integration review |
| M2 | Dataset analysis + feature engineering + leakage review |
| M3 | Renewable data + anomaly review + SHAP/root-cause review |
| M4 | Optimization formulation + constraints + infeasibility review |

---

# 11. Bob + Primary Development Environment

Recommended workflow:

```text
Bob
 ↓
Understand / Plan / Review / Small Task
 ↓
Primary Development Environment
 ↓
Main implementation
 ↓
Tests
 ↓
Bob review where useful
```

The primary development environment can handle:

- large implementation
- model experimentation
- data exploration
- optimization experiments
- UI work
- integration

Bob should remain a genuine part of the development process rather than a fake reporting step.

---

# 12. Final Bob Evidence

Before submission:

1. Export the required official Bob task/session report if the hackathon provides that feature.
2. Keep the export in the repository according to the submission rules.
3. Keep `docs/bob/` only if it provides useful supplemental evidence.
4. Ensure all claims in the Bob usage documentation correspond to real sessions.

