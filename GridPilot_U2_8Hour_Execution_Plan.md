# GridPilot AI — U2 8-Hour Execution Plan
## Complete Team Build Plan with Step-by-Step Prompts

> **Purpose:** This is the execution document for a 4-member team building the U2 solution in a very limited time window.
>
> **Primary objective:** Get a working, testable end-to-end system first. UI polish, extra features, and presentation come after the core pipeline works.

---

# 0. U2 Problem We Are Implementing

## U2 — Grid Load Optimisation & Renewable Energy Performance Advisor

The solution must support:

1. Electricity demand forecasting.
2. Upcoming demand-spike detection.
3. Solar generation forecasting.
4. Wind generation forecasting.
5. Renewable-performance anomaly detection.
6. Root-cause analysis for underperforming assets.
7. Load-balancing recommendations.
8. Renewable-energy curtailment minimisation.
9. An integrated operator optimisation brief.

The implementation stack selected for this plan is:

```text
Demand Forecasting      → LightGBM
Demand Spike Detection  → XGBoost Classifier
Solar Forecasting       → LightGBM
Wind Forecasting        → LightGBM
Renewable Anomalies     → Isolation Forest
Root Cause              → XGBoost + SHAP
Optimisation            → OR-Tools / LP / MILP
Operator Brief          → LLM
Frontend                → React + Tailwind + Recharts/Plotly
Backend                 → Node.js + TypeScript
Database                → PostgreSQL
Data Backbone           → OpenSTEF Liander 2024
Additional PV Data      → EDS-lab when needed
Optional Wind Data      → UTSD when needed
```

---

# 1. What We Are Building

GridPilot is a **decision-support system**, not a direct grid-control system.

The operator should be able to see:

```text
CURRENT GRID STATE
        ↓
DEMAND FORECAST
        ↓
DEMAND SPIKE RISK
        ↓
RENEWABLE FORECAST
        ↓
RENEWABLE HEALTH
        ↓
ROOT CAUSE
        ↓
OPTIMIZATION
        ↓
CURTAILMENT PLAN
        ↓
OPERATOR BRIEF
```

The central question is:

> **What is happening, why is it happening, what feasible action should be taken, and what happens if that action is taken?**

---

# 2. Critical Architecture Rules

## Rule A — ML is responsible for predictions

ML handles:

- load forecast
- solar forecast
- wind forecast
- demand spike classification
- renewable anomaly detection
- root-cause feature analysis

## Rule B — The optimizer is responsible for decisions

The optimizer handles:

- battery dispatch
- flexible-load shifting
- load balancing
- curtailment minimisation
- operational constraints
- scenario simulation
- feasibility

## Rule C — LLM is responsible for communication

The LLM handles:

- interpreting structured results
- operator questions
- explanations
- summaries
- operator briefs

The LLM must not invent numbers or replace the mathematical optimizer.

## Rule D — Frontend contains presentation logic only

Frontend must not implement:

- ML
- optimization
- physical equations
- hidden business calculations

---

# 3. 4-Member Ownership

## Member 1 — Team Leader

### Role
System Architect + Integration + Backend Gateway + LLM Operator Layer + Frontend

### Branch

```text
leader/integration
```

### Owns

```text
apps/api/**
apps/web/**
agent/**
shared/contracts/**
shared/types/**
tests/integration/**
tests/e2e/**
docs/**
docker-compose.yml
.env.example
```

### Must NOT directly own

```text
services/data/**
services/forecasting/**
services/renewable/**
services/optimization/**
```

The domain owners implement those modules.

---

## Member 2 — Data + Demand Forecasting

### Role
Data Engineer + Demand Forecasting Engineer

### Branch

```text
member/data-forecast
```

### Owns

```text
services/data/**
services/forecasting/**
ml/models/demand/**
ml/experiments/demand/**
```

### Main work

```text
OpenSTEF
→ data validation
→ cleaning
→ feature engineering
→ LightGBM demand forecast
→ XGBoost spike classifier
→ evaluation
```

---

## Member 3 — Renewable Intelligence

### Role
Renewable Forecasting + Anomaly + Root-Cause Engineer

### Branch

```text
member/renewable-intelligence
```

### Owns

```text
services/renewable/**
ml/models/renewable/**
ml/experiments/renewable/**
```

### Main work

```text
Solar forecast
Wind forecast
Expected generation
Actual vs expected
Isolation Forest anomaly
XGBoost + SHAP root cause
Curtailment-aware diagnostics
```

---

## Member 4 — Grid Optimization

### Role
Optimization Engineer

### Branch

```text
member/grid-optimization
```

### Owns

```text
services/optimization/**
ml/experiments/optimization/**
```

### Main work

```text
Grid state
Resource constraints
Battery
EV / flexible load
Industrial flexible load
OR-Tools optimization
Curtailment minimization
Scenario simulation
Feasibility diagnostics
```

---

# 4. Repository Structure

```text
gridpilot/
│
├── apps/
│   ├── web/
│   └── api/
│
├── services/
│   ├── data/
│   ├── forecasting/
│   ├── renewable/
│   └── optimization/
│
├── agent/
│   ├── provider/
│   ├── tools/
│   ├── prompts/
│   ├── orchestration/
│   └── policies/
│
├── shared/
│   ├── contracts/
│   ├── types/
│   ├── constants/
│   └── errors/
│
├── database/
│   ├── schema/
│   ├── migrations/
│   └── seed/
│
├── ml/
│   ├── datasets/
│   ├── models/
│   └── experiments/
│
├── tests/
│   ├── integration/
│   └── e2e/
│
├── docs/
│
├── scripts/
│
├── AGENTS.md
├── CONTRIBUTING.md
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# 5. Shared Contracts — Freeze These First

Only the Team Leader modifies:

```text
shared/contracts/**
shared/types/**
```

Everyone else can read them.

## DemandForecast

```typescript
export interface DemandForecast {
  zoneId: string;
  generatedAt: string;
  horizonMinutes: number;

  points: {
    timestamp: string;
    demandMw: number;
    lowerBoundMw?: number;
    upperBoundMw?: number;
  }[];

  modelVersion: string;
}
```

## RenewableStatus

```typescript
export interface RenewableStatus {
  assetId: string;
  assetType: "solar" | "wind" | "hydro";

  timestamp: string;

  expectedMw: number;
  actualMw: number;

  performanceRatio: number;
  anomaly: boolean;

  likelyRootCause?: {
    category: string;
    confidence: number;
  };
}
```

## OptimizationResult

```typescript
export interface OptimizationResult {
  scenarioId: string;
  status: "feasible" | "infeasible";

  actions: {
    resourceId: string;
    actionType: string;
    powerMw: number;
    startTime: string;
    endTime: string;
  }[];

  before: {
    demandMw: number;
    renewableMw: number;
    curtailmentMw: number;
    gridStress: number;
  };

  after: {
    demandMw: number;
    renewableMw: number;
    curtailmentMw: number;
    gridStress: number;
  };

  objectiveValue: number;
}
```

---

# 6. Data Foundation

## Primary dataset

OpenSTEF Liander 2024.

Use it as the main integrated data source for:

- load
- grid measurements
- transformers/substations
- solar
- wind
- weather
- weather forecasts
- optimization inputs

The technical plan uses OpenSTEF as the project backbone because it best matches the integrated U2 problem.

## Secondary

EDS-lab datasets:

Use for dedicated PV/solar forecasting when useful.

## Optional

UTSD:

Use only when extra wind data is actually necessary.

## Optional Indian validation

Karnataka SLDC / Delhi SLDC:

Use only for additional validation if time remains.

---

# 7. Time Resolution

Use:

```text
15-minute
```

Primary forecast horizons:

```text
15 min
30 min
60 min
```

Optional later:

```text
6–24 hours
```

Do not add long-horizon support before the 15/30/60-minute pipeline works.

---

# 8. Member 1 — TEAM LEADER: Complete Build Prompts

## M1 Chunk 1 — Repository Bootstrap

### Objective

Create the repository skeleton and engineering boundaries.

### Prompt to give your coding AI

```text
You are the system architect for GridPilot AI.

Create the repository structure exactly according to the current GridPilot
architecture.

Create:

apps/web
apps/api
services/data
services/forecasting
services/renewable
services/optimization
agent/provider
agent/tools
agent/prompts
agent/orchestration
agent/policies
shared/contracts
shared/types
shared/constants
shared/errors
database/schema
database/migrations
database/seed
ml/datasets
ml/models
ml/experiments
tests/integration
tests/e2e
docs
scripts

Also create:
AGENTS.md
CONTRIBUTING.md
.env.example
.gitignore
README.md

Do not implement business logic yet.

Do not create fake ML results.

Keep the structure modular.

Create placeholder README files only where useful to explain module ownership.
```

### Verify

- Structure exists.
- No domain logic is duplicated.
- Ownership is documented.

---

## M1 Chunk 2 — Shared Contracts

```text
Create and implement the shared TypeScript contracts for GridPilot.

Required contracts:

DemandForecast
RenewableStatus
WeatherData
GridState
OptimizationInput
OptimizationResult
Recommendation
Scenario
AgentContext

Keep the contracts implementation-neutral.

Do not include model-specific internals.

Add validation schemas for external API boundaries.

Do not modify services/forecasting, services/renewable, or
services/optimization.

Add contract tests.

Return a summary of every contract and why it exists.
```

---

## M1 Chunk 3 — API Gateway

```text
Implement the GridPilot Node.js TypeScript API gateway.

Create API modules for:

/api/grid
/api/forecast
/api/renewable
/api/optimization
/api/scenario
/api/agent

Requirements:

- request validation
- typed responses
- consistent error format
- structured logging
- request ID
- health endpoint
- environment-based configuration
- no hardcoded credentials

The API gateway must delegate to domain services.

Do not reimplement ML or optimization logic inside the gateway.

Use the shared contracts.

Add unit tests for validation and error handling.
```

---

## M1 Chunk 4 — Grid State Aggregator

```text
Implement a Grid State service that aggregates structured outputs from the
forecasting, renewable and optimization layers.

The service should expose a read-only operational snapshot containing:

- current demand
- forecast demand
- renewable generation
- renewable anomalies
- available flexible resources
- curtailment
- grid stress indicators

Do not invent values.

If a dependency is unavailable, represent the field as unavailable rather
than silently using fake data.

Keep aggregation logic separate from the domain models.
```

---

## M1 Chunk 5 — LLM Provider

```text
Implement an LLM provider abstraction for GridPilot.

Requirements:

- provider interface
- IBM watsonx.ai implementation
- environment-based credentials
- timeout handling
- error handling
- structured prompt input
- model/provider abstraction so the provider can be replaced later

The LLM is only responsible for interpreting structured system outputs.

It must never be the source of numerical forecasts or optimization quantities.
```

---

## M1 Chunk 6 — Operator Brief

```text
Implement the GridPilot Operator Brief generator.

Input:

- current grid state
- demand forecast
- demand spike risk
- renewable forecasts
- renewable anomalies
- root causes
- optimization result
- curtailment result

Output sections:

1. Current situation
2. Risk
3. Renewable alert
4. Root cause
5. Recommended actions
6. Expected impact
7. Confidence/uncertainty
8. Data limitations

Rules:

- Never invent numbers.
- Never change optimization results.
- Never claim correlation is causation.
- Clearly state missing data.
- Preserve feasible/infeasible optimization status.
```

---

## M1 Chunk 7 — Agent/Copilot

Only implement this after the core services are functioning.

```text
Implement an operator copilot on top of the existing GridPilot services.

Create tools:

get_current_grid_state()
get_demand_forecast()
get_renewable_status()
get_weather_forecast()
get_renewable_anomalies()
analyze_root_cause()
run_optimization()
simulate_action()

The agent should:

1. determine which information is needed
2. call the appropriate tools
3. use their structured outputs
4. explain the situation
5. recommend actions only from optimizer results
6. state uncertainty where relevant

Do not allow free-form numerical dispatch decisions by the LLM.

Do not bypass the optimizer.

Add tests for:
- successful tool calls
- missing data
- tool failure
- infeasible optimization
```

---

## M1 Chunk 8 — Frontend Shell

```text
Implement the GridPilot React application shell.

Pages:

1. Command Center
2. Demand Forecast
3. Renewable Assets
4. Optimization Center
5. AI Copilot
6. Scenario Simulator

Build reusable components for:

- metric cards
- alerts
- time-series charts
- asset status
- optimization actions
- before/after comparison
- operator brief

Use Tailwind CSS.

Use Recharts or Plotly.

Do not hardcode production-like model results.

Use typed API responses.

Keep API access in a dedicated client/service layer.
```

---

## M1 Chunk 9 — E2E Integration

```text
Integrate the full GridPilot pipeline.

Required flow:

data
→ demand forecast
→ spike risk
→ renewable forecast
→ anomaly
→ root cause
→ grid state
→ optimization
→ operator brief
→ dashboard

Create one deterministic end-to-end scenario called:

DEMAND_SPIKE_PLUS_RENEWABLE_DROP

The test must verify:

- forecast exists
- anomaly exists when expected
- optimizer returns feasible/infeasible status correctly
- operator brief reflects actual outputs
- UI receives structured results

Do not use hardcoded final answers.
```

---

# 9. Member 2 — DATA + DEMAND FORECASTING: Complete Build Prompts

## M2 Chunk 1 — Inspect OpenSTEF

```text
Analyze the OpenSTEF Liander 2024 dataset available for this project.

Do not modify application code yet.

Identify the exact fields relevant to:

- demand/load
- timestamps
- zones/feeders
- weather
- solar
- wind

Document:

- field names
- units
- frequency
- missing-value behavior
- duplicate behavior
- timezone
- possible leakage fields
- candidate target variables

Create:
docs/data/openstef-demand.md

Do not invent fields that do not exist.
```

---

## M2 Chunk 2 — Data Ingestion

```text
Implement the demand-data ingestion pipeline.

Requirements:

1. Load the selected OpenSTEF demand data.
2. Validate schema.
3. Normalize timestamps.
4. Sort by timestamp.
5. Detect duplicate timestamps.
6. Detect missing intervals.
7. Handle missing demand values explicitly.
8. Validate physical numeric ranges.
9. Produce a cleaned canonical dataset.

Do not train a model yet.

Create data-quality reporting.

Do not modify other team modules.
```

---

## M2 Chunk 3 — Feature Engineering

```text
Implement demand forecasting feature engineering.

Create features from past information only.

Required candidates:

- lag 15 min
- lag 30 min
- lag 1 hour
- lag 24 hours
- temperature
- humidity
- cloud cover
- wind speed
- solar radiation
- hour
- day of week
- weekend
- holiday
- season

Add rolling features if data availability is sufficient.

Prevent leakage.

Write tests proving no future values enter features.
```

---

## M2 Chunk 4 — Baselines

```text
Implement two demand forecasting baselines:

1. persistence / last-value
2. seasonal naive

Evaluate them on chronological train/validation/test data.

Calculate:

MAE
RMSE
MAPE

Save results in a machine-readable evaluation artifact.

Do not randomly shuffle time-series data.
```

---

## M2 Chunk 5 — LightGBM Forecasting

```text
Implement the primary demand forecasting model using LightGBM.

Forecast:

15 minutes
30 minutes
60 minutes

Requirements:

- chronological split
- reproducible training
- configurable hyperparameters
- model version
- feature version
- training metadata
- validation metrics
- saved model artifact

Compare against the baseline models.

Do not claim the ML model is better unless the measured validation/test results
support it.
```

---

## M2 Chunk 6 — Forecast Service

```text
Implement the demand forecast service.

Interface:

forecastDemand(zoneId, startTime, horizon)

Return the shared DemandForecast structure.

Requirements:

- load trained model
- validate requested zone
- validate sufficient history
- handle missing features
- return clear errors
- attach model version
- include forecast timestamps

Do not expose training internals through the service.
```

---

## M2 Chunk 7 — Demand Spike Classifier

```text
Implement the demand spike detection model.

Primary model:
XGBoost classifier.

Classes:

0 = Normal
1 = Moderate Spike
2 = Severe Spike

Features:

- current load
- forecast load
- load growth percentage
- historical peak
- temperature
- hour
- day
- weather

First define a reproducible labeling rule for the classes based on the
historical demand distribution.

Then train and evaluate the classifier.

Report:

precision
recall
F1
confusion matrix

Do not use an arbitrary hardcoded threshold without documenting it.
```

---

## M2 Chunk 8 — M2 Tests

```text
Create tests for the complete demand module.

Cover:

- schema validation
- missing timestamps
- duplicates
- missing demand
- lag feature generation
- leakage prevention
- model loading
- forecast generation
- unknown zone
- insufficient history
- spike classifier input validation

Create one end-to-end test using a small deterministic fixture.
```

---

# 10. Member 3 — RENEWABLE INTELLIGENCE: Complete Build Prompts

## M3 Chunk 1 — Inspect Renewable Data

```text
Analyze the renewable-energy data available in the project.

Identify:

- solar asset IDs
- wind asset IDs
- generation measurements
- timestamps
- weather variables
- operational fields
- possible curtailment indicators

Document fields, units and frequency.

Create:

docs/data/openstef-renewable.md

Do not modify other domains.
```

---

## M3 Chunk 2 — Solar Forecasting

```text
Implement solar generation forecasting.

Primary data:
EDS-lab PV data where useful, otherwise OpenSTEF.

Primary model:
LightGBM.

Features should include where available:

- historical solar generation
- solar irradiance
- cloud cover
- temperature
- humidity
- time of day
- day of year

Forecast short-term expected solar generation.

Use chronological validation.

Report:
MAE
RMSE
MAPE

Save model metadata and version.
```

---

## M3 Chunk 3 — Wind Forecasting

```text
Implement wind generation forecasting.

Primary dataset:
OpenSTEF.

Optional:
UTSD only if needed.

Primary model:
LightGBM.

Features:

- historical wind generation
- wind speed
- wind direction
- temperature
- pressure
- time
- season

Use chronological validation.

Return expected generation through a clean service interface.
```

---

## M3 Chunk 4 — Expected-vs-Actual Performance

```text
Implement renewable performance analysis.

For every asset and timestamp calculate:

expected generation
actual generation
absolute deviation
percentage deviation
performance ratio

Formula:

performance_ratio =
actual_generation / expected_generation

Handle zero expected generation safely.

Do not classify every low-output event as a failure.
```

---

## M3 Chunk 5 — Curtailment-Aware Logic

```text
Add logic to distinguish:

1. normal production
2. weather-driven reduction
3. physical asset underperformance
4. intentional curtailment
5. data-quality problem

If curtailment information exists, suppress false anomaly classification
for intentionally curtailed output.

If curtailment information is unavailable, mark the diagnostic as uncertain
rather than assuming an asset failure.
```

---

## M3 Chunk 6 — Isolation Forest

```text
Implement renewable anomaly detection using Isolation Forest.

Input features can include:

- actual generation
- expected generation
- residual / deviation
- weather
- rolling performance
- relevant operational signals

Return:

asset ID
timestamp
anomaly flag
anomaly score
key measurements

Tune the detector on deterministic validation scenarios.

Do not hardcode one asset as anomalous.
```

---

## M3 Chunk 7 — Root Cause Model

```text
Implement root-cause analysis using XGBoost with SHAP explainability.

Target:
Explain the observed renewable performance deviation.

Candidate features:

- solar irradiance
- cloud cover
- temperature
- humidity
- wind speed
- wind direction
- historical performance
- operational signals
- weather forecast
- curtailment indicators

Output:

likely root cause
confidence
feature contribution/evidence

Do not describe SHAP feature importance as proof of causation.

Use language such as:
"most strongly associated with the observed deviation."
```

---

## M3 Chunk 8 — Renewable Service

```text
Implement renewable service interfaces:

getRenewableStatus(assetId, timestamp)
detectAnomalies(timeRange)
analyzeRootCause(assetId, timestamp)

Return the shared RenewableStatus contract.

Validate missing data.

Return explicit uncertainty when root cause cannot be supported.
```

---

## M3 Chunk 9 — M3 Tests

```text
Create deterministic tests for:

1. healthy solar
2. cloud-driven generation reduction
3. inverter-performance degradation
4. sensor/data corruption
5. intentional curtailment
6. wind generation reduction
7. multiple simultaneous anomalies

Verify that curtailment does not automatically become a physical fault.
```

---

# 11. Member 4 — GRID OPTIMIZATION: Complete Build Prompts

## M4 Chunk 1 — Mathematical Formulation

```text
Design the GridPilot optimization model.

Do not code yet.

Define:

Decision variables
Hard constraints
Objective function
Resource limits
Battery constraints
Flexible load constraints
Grid capacity
Renewable availability
Curtailment
Ramp limits
Time periods

Use a linear formulation wherever possible.

Use MILP only when discrete decisions are necessary.

Return the complete mathematical formulation and explain every variable.
```

---

## M4 Chunk 2 — Resource Model

```text
Implement resource models for:

1. Battery
2. EV charging
3. Flexible industrial load

Battery:

- current SOC
- minimum SOC
- maximum SOC
- maximum charge
- maximum discharge
- efficiency

EV:

- current demand
- flexible fraction
- allowed shift window

Industrial:

- current demand
- flexible fraction
- allowed shift window
- maximum shift

Validate every resource before optimization.
```

---

## M4 Chunk 3 — Grid State and Constraints

```text
Implement the grid-state model.

Required quantities:

- demand
- renewable generation
- other generation
- grid capacity
- renewable availability
- battery availability
- flexible load availability
- time period

Implement explicit hard constraints for:

- generation availability
- grid capacity
- battery limits
- battery SOC
- EV flexibility
- industrial flexibility
- ramp limits where modeled

Create tests for constraint violations.
```

---

## M4 Chunk 4 — Load Balancing Optimizer

```text
Implement the load-balancing optimizer using OR-Tools.

Inputs:

- demand forecast
- solar forecast
- wind forecast
- battery state
- flexible resources
- grid capacity
- renewable availability
- ramp constraints

Objective:

minimize a configurable combination of:
- grid imbalance
- operational cost
- flexible-load disruption
- battery penalty
- curtailment where relevant

Return:
OptimizationResult

The optimizer must calculate actions.
Do not hardcode expected actions.
```

---

## M4 Chunk 5 — Curtailment Minimization

```text
Implement renewable curtailment minimization using OR-Tools.

Curtailment:

available renewable generation
-
renewable generation accepted by the modeled grid

Use realistic simulated grid constraints when the public data does not provide
all required network/resource constraints.

The objective should reduce:

- curtailment cost
- energy cost
- peak-demand risk
- grid imbalance

Respect:

- generation capacity
- transmission/grid capacity
- battery SOC
- ramp limits
- resource limits

Return the before/after curtailment values from the actual solver.
```

---

## M4 Chunk 6 — Feasibility

```text
Make infeasibility a first-class result.

If the required balancing exceeds available flexibility, return:

status = "infeasible"

and diagnostics containing:

required balancing
available flexibility
estimated deficit
binding constraints where available

Never return a fabricated plan for an infeasible problem.
```

---

## M4 Chunk 7 — Scenario Simulation

```text
Implement:

simulateAction(...)
compareScenario(...)

Required scenarios:

NORMAL_DAY
EVENING_DEMAND_SPIKE
SOLAR_UNDERPERFORMANCE
HIGH_RENEWABLE_CURTAILMENT
DEMAND_SPIKE_PLUS_RENEWABLE_DROP
BATTERY_UNAVAILABLE
NO_FLEXIBLE_LOAD
INFEASIBLE_DEMAND

The simulator must call the real optimizer.

Return before/after metrics.
```

---

## M4 Chunk 8 — M4 Tests

```text
Create deterministic optimization tests.

Test:

- normal operation
- evening demand spike
- renewable surplus
- high curtailment
- battery unavailable
- no flexible load
- infeasible demand
- reduced grid capacity
- lower renewable availability

For each test verify:

- feasibility status
- hard constraints
- action limits
- objective behavior
- curtailment calculation
```

---

# 12. MEMBER 1 Integration After M2/M3/M4 Deliver Their Modules

The leader should wait for stable module interfaces, not internal perfection.

## Integration Prompt 1

```text
Integrate the existing GridPilot modules without rewriting their internal logic.

Connect:

DemandForecast
RenewableStatus
GridState
OptimizationResult

Verify that the API layer can consume each module through typed interfaces.

Do not alter domain algorithms.

Add integration adapters only where required.
```

## Integration Prompt 2

```text
Create a deterministic scenario runner.

Scenario:

DEMAND_SPIKE_PLUS_RENEWABLE_DROP

Data:
- rising demand
- falling solar
- falling wind
- available battery
- flexible EV load
- flexible industrial load

Run:

forecast
→ spike detection
→ renewable analysis
→ grid state
→ optimization
→ operator brief

Log every stage and save one final structured JSON result.
```

## Integration Prompt 3

```text
Run a full system review.

Check:

- numerical values
- contract compatibility
- missing data behavior
- infeasibility handling
- false anomaly behavior
- optimization constraints
- LLM hallucination risks
- frontend/backend consistency

Do not rewrite working domain models.

Return a prioritized list of confirmed problems.
```

---

# 13. Operator UI — Final Required Screens

## 1. Command Center

Show:

```text
Demand
Renewable generation
Grid stress
Curtailment
Top alerts
Current operator recommendation
```

## 2. Forecast

Show:

```text
Demand forecast
Spike probability
Solar forecast
Wind forecast
```

## 3. Renewable Assets

Show:

```text
Asset
Expected
Actual
Performance ratio
Anomaly
Likely root cause
Confidence
```

## 4. Optimization Center

Show:

```text
Before
After

Battery action
EV shift
Industrial shift
Curtailment

Feasible / Infeasible
```

## 5. AI Copilot

Allow questions such as:

```text
Will the grid be stressed in the next hour?

Why is Solar-17 underperforming?

What actions can reduce the risk?

What happens if Battery-01 is unavailable?
```

## 6. Scenario Simulator

Allow controlled changes:

```text
Demand +
Solar -
Wind -
Battery unavailable
EV flexibility -
```

Then rerun the optimizer and show before/after results.

---

# 14. Model Evaluation Requirements

## Demand

Report:

```text
MAE
RMSE
MAPE
```

Compare:

```text
Persistence
Seasonal Naive
LightGBM
```

## Spike Classifier

Report:

```text
Precision
Recall
F1
Confusion Matrix
```

## Solar/Wind

Report:

```text
MAE
RMSE
MAPE
```

## Anomaly Detector

Evaluate on controlled scenarios:

```text
normal
known anomaly
curtailment
weather drop
sensor error
```

## Optimization

Report:

```text
feasible / infeasible
objective value
curtailment before
curtailment after
grid stress before
grid stress after
```

---

# 15. Eight-Hour Priority Order

Because the team has only 8 hours, use this order.

## Hour 0–1

All:

```text
Repository
contracts
dataset inspection
environment
ownership
```

Leader freezes the interfaces.

## Hour 1–3

Parallel:

```text
M2 → data + demand forecast
M3 → renewable forecast + anomaly
M4 → optimizer + constraints
M1 → API + frontend shell
```

## Hour 3–5

Parallel:

```text
M2 → spike classifier
M3 → root cause
M4 → curtailment + simulator
M1 → backend integration
```

## Hour 5–6

Leader:

```text
forecast
+
renewables
+
optimizer
```

into one end-to-end scenario.

Everyone fixes integration issues in their own modules.

## Hour 6–7

Leader:

```text
LLM operator brief
AI Copilot
dashboard integration
```

Everyone:

```text
scenario testing
```

## Hour 7–8

All:

```text
bug fixing
validation
README
demo scenario
final test
```

Do not spend the final hour adding new architecture.

---

# 16. What to Cut if You Fall Behind

## Cut first

```text
6–24h forecasts
UTSD
Indian validation datasets
advanced agent autonomy
complex UI animation
full user authentication
microservices deployment
extra renewable types
```

## Do NOT cut

```text
15/30/60 min demand forecast
demand spike detection
solar/wind expected generation
anomaly detection
root cause
OR-Tools optimizer
curtailment
scenario simulation
basic dashboard
operator brief
```

---

# 17. Git Workflow

Branches:

```text
main

leader/integration
member/data-forecast
member/renewable-intelligence
member/grid-optimization
```

No direct pushes to `main`.

Flow:

```text
Member Branch
   ↓
Commit
   ↓
Push
   ↓
Pull Request
   ↓
Leader Review
   ↓
leader/integration
   ↓
Integration Tests
   ↓
main
```

---

# 18. Ownership Rules

## Only Leader edits

```text
shared/contracts/**
shared/types/**
database/migrations/**
database/schema/**
apps/api/**
apps/web/**
agent/**
docker-compose.yml
.env.example
AGENTS.md
CONTRIBUTING.md
```

## Member 2 edits

```text
services/data/**
services/forecasting/**
ml/models/demand/**
ml/experiments/demand/**
```

## Member 3 edits

```text
services/renewable/**
ml/models/renewable/**
ml/experiments/renewable/**
```

## Member 4 edits

```text
services/optimization/**
ml/experiments/optimization/**
```

If another member needs a change:

```text
request
→ contract discussion
→ owner implements
→ PR
```

---

# 19. Files That Should Never Be Edited Simultaneously

```text
shared/contracts/**
database/migrations/**
database/schema/**
docker-compose.yml
package.json
tsconfig.json
AGENTS.md
CONTRIBUTING.md
```

This is mandatory for conflict prevention.

---

# 20. Definition of Done

A module is done only when:

```text
Code
 ↓
Tests
 ↓
Edge cases
 ↓
Contract validation
 ↓
Documentation
 ↓
PR
 ↓
Leader review
 ↓
Integration test
```

---

# 21. Final Working System

The final architecture should demonstrate:

```text
                     GRIDPILOT
                         │
        ┌────────────────┼─────────────────┐
        │                │                 │
        ▼                ▼                 ▼
   Demand Data      Renewable Data      Weather
        │                │                 │
        ▼                ▼                 ▼
    LightGBM         LightGBM          Context
        │                │
        ▼                ▼
  Demand Forecast  Expected Generation
        │                │
        ▼                ▼
 XGBoost Spike     Isolation Forest
 Detection               │
                         ▼
                 XGBoost + SHAP
                         │
        └────────────┬───┘
                     ▼
                GRID STATE
                     │
                     ▼
              OR-Tools / MILP
                     │
             ┌───────┴────────┐
             ▼                ▼
        Load Balance     Curtailment
             │                │
             └────────┬───────┘
                      ▼
                   LLM
                      ▼
               Operator Brief
                      ▼
                  Dashboard
```

---

# 22. End-to-End Acceptance Test

The project is considered operationally functional when this sequence works:

```text
1. Load historical/replay data
2. Produce a demand forecast
3. Detect a demand spike
4. Produce solar/wind expected generation
5. Identify renewable underperformance
6. Produce an evidence-based root cause
7. Build current grid state
8. Solve a feasible optimization
9. Show reduced curtailment / improved grid metrics
10. Simulate an alternative action
11. Generate an operator brief from actual outputs
12. Show all results in the dashboard
```

If any step is not functioning, fix that before adding polish.

---

# 23. Final Principle

The architecture should remain:

```text
ML models
→ PREDICT / DIAGNOSE

Optimization
→ DECIDE FEASIBLE ACTION

LLM
→ EXPLAIN / SUMMARIZE

Human operator
→ REVIEW / APPROVE
```

This is the core technical contract of GridPilot.
