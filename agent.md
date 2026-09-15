# Agent Playbook: GridPilot AI (U2) & IBM Bob
# Team: Relentless Gladiators | Hackathon: Bob AI Hackathon

> **File:** `agent.md` (referenced by `AGENTS.md`)  
> **System:** GridPilot AI — Grid Load Optimisation & Renewable Energy Performance Advisor (Problem U2)  
> **Team Name:** Relentless Gladiators (Track: AI / Sustainability)  
> **Role:** Master operational context, architectural guardrails, contract specifications, and automation instructions for IBM Bob (BobShell) and agentic workers.

---

## 1. Project & Architectural Mission

**GridPilot AI** is a real-time **decision-support system** for power grid operators managing high-penetration renewable grids (solar, wind, battery, flexible industrial/EV loads).

### Core Pipeline Flow
```text
CURRENT GRID STATE (15-min)
       ↓
DEMAND FORECAST (LightGBM) → SPIKE DETECTION (XGBoost Classifier)
       ↓
RENEWABLE FORECAST (LightGBM Solar/Wind)
       ↓
ANOMALY DETECTION (Isolation Forest) → ROOT CAUSE (XGBoost + SHAP)
       ↓
GRID STATE AGGREGATION
       ↓
MATHEMATICAL OPTIMIZATION (Google OR-Tools / MILP)
       ↓
LOAD BALANCING & CURTAILMENT MINIMISATION PLAN
       ↓
IBM WATSONX.AI / BOB OPERATOR BRIEF & COPILOT
       ↓
OPERATOR DASHBOARD (React + Tailwind + Recharts)
```

### The 4 Non-Negotiable Architectural Rules
1. **Rule A — ML is responsible for PREDICTIONS only:**
   - LightGBM (Demand, Solar, Wind), XGBoost (Spike classification, Root cause), Isolation Forest (Anomalies).
   - ML models predict and diagnose; they **never** invent dispatch decisions or schedule grid resources.
2. **Rule B — The Optimizer is responsible for DECISIONS:**
   - Google OR-Tools / MILP engine calculates battery dispatch, flexible load shifting, curtailment minimisation, and verifies feasibility.
   - The LLM must **never** invent dispatch numbers or bypass the optimizer.
3. **Rule C — LLM (watsonx.ai / Bob) is responsible for COMMUNICATION:**
   - Interprets structured outputs, generates operator briefs, answers operator questions, and calls tools.
   - Preserves mathematical ground truth: never hallucinations, never claims correlation is causation.
4. **Rule D — Frontend contains PRESENTATION logic only:**
   - React + Tailwind + Recharts/Plotly. Purely consumes typed REST/SSE endpoints. No embedded ML, optimization, or physics calculations.

---

## 2. 4-Member Ownership Boundaries (Strict Isolation)

To prevent merge collisions during the 8-hour sprint, strict directory ownership is enforced:

| Member | Role | Branch | Owned Directories |
| :--- | :--- | :--- | :--- |
| **Member 1 (Leader)** | System Architect, API Gateway, Frontend, LLM/Agent, Contracts | `leader/integration` | `apps/api/**`, `apps/web/**`, `agent/**`, `shared/contracts/**`, `shared/types/**`, `tests/integration/**`, `docs/**`, `docker-compose.yml`, `.env.example`, `submission.yaml` |
| **Member 2** | Data + Demand Forecasting | `member/data-forecast` | `services/data/**`, `services/forecasting/**`, `ml/models/demand/**`, `ml/experiments/demand/**` |
| **Member 3** | Renewable Intelligence | `member/renewable-intelligence` | `services/renewable/**`, `ml/models/renewable/**`, `ml/experiments/renewable/**` |
| **Member 4** | Grid Optimization | `member/grid-optimization` | `services/optimization/**`, `ml/experiments/optimization/**` |

### Prohibited Overlaps
- Only Member 1 (Team Leader) modifies `shared/contracts/**`, `shared/types/**`, `package.json`, `tsconfig.json`, `docker-compose.yml`, and `agent.md`.
- No member commits directly to `main`. All merges flow through PRs into `leader/integration` after contract checks.

---

## 3. Shared Contracts (Ground Truth Interfaces)

All modules exchange data strictly using the TypeScript contracts frozen in `shared/contracts/`:

### A. `DemandForecast`
```typescript
export interface DemandForecast {
  zoneId: string;
  generatedAt: string;
  horizonMinutes: 15 | 30 | 60;
  points: {
    timestamp: string;
    demandMw: number;
    lowerBoundMw?: number;
    upperBoundMw?: number;
  }[];
  spikeRisk: {
    level: "normal" | "moderate" | "severe";
    probability: number;
    predictedPeakMw: number;
  };
  modelVersion: string;
}
```

### B. `RenewableStatus`
```typescript
export interface RenewableStatus {
  assetId: string;
  assetType: "solar" | "wind" | "hydro";
  timestamp: string;
  expectedMw: number;
  actualMw: number;
  performanceRatio: number; // actual / expected
  anomaly: boolean;
  anomalyScore?: number;
  likelyRootCause?: {
    category: "cloud_cover" | "inverter_fault" | "soiling" | "curtailment" | "sensor_error";
    confidence: number;
    evidence: string;
  };
}
```

### C. `OptimizationResult`
```typescript
export interface OptimizationResult {
  scenarioId: string;
  status: "feasible" | "infeasible";
  actions: {
    resourceId: string;
    actionType: "battery_charge" | "battery_discharge" | "shift_flexible_load" | "curtail_solar" | "curtail_wind";
    powerMw: number;
    startTime: string;
    endTime: string;
  }[];
  before: {
    demandMw: number;
    renewableMw: number;
    curtailmentMw: number;
    gridStressIndex: number; // 0 to 1
  };
  after: {
    demandMw: number;
    renewableMw: number;
    curtailmentMw: number;
    gridStressIndex: number;
  };
  objectiveValue: number;
}
```

---

## 4. IBM Bob (BobShell) Load-Bearing Integration

To secure all **10 points for IBM Bob Integration**, Bob must be actively executing in the operational loop, not just cosmetically mentioned.

### Bob's 3 Operational Roles
1. **Tool-Equipped Grid Copilot via MCP:**
   Bob connects to `apps/api` via Model Context Protocol tools:
   - `get_current_grid_state()`
   - `get_demand_forecast(zoneId, horizon)`
   - `get_renewable_anomalies()`
   - `analyze_root_cause(assetId)`
   - `run_optimization(scenarioId)`
   - `simulate_action(actionParams)`
2. **Headless Incident & Brief Automator (`bob run`):**
   Automated cron/script invoking Bob to synthesize the 15-minute Operator Brief from the structured pipeline outputs.
3. **Automated Submission Validator:**
   Bob executes verification suites and checks `submission.yaml` and `.github/workflows/validate.yml` invariants before git push.

### Configuring Bob MCP Tools (PowerShell / Windows Syntax)
```powershell
# In PowerShell, always quote the '--' separator
bob mcp add gridpilot-api node "--" ./apps/api/dist/mcp-server.js
# Or register via JSON config in .bob/mcp.json
```

---

## 5. Hackathon Submission Checklist & Invariants

Automated GitHub Action `.github/workflows/validate.yml` runs on every push:
1. `submission.yaml` exists and is 100% valid YAML (all `# REQUIRED` fields filled, no empty strings).
2. `docs/setup-guide.md` exists and contains reproducible end-to-end setup commands tested on a clean machine.
3. `demo/demo-video-link.txt` contains a valid, public/unlisted URL (YouTube/Loom/Box) of 3-5 min running demo.
4. `demo/screenshots/` has at least 3 sequential PNGs:
   - `01-command-center.png`
   - `02-anomaly-root-cause.png`
   - `03-optimization-result.png`
5. `README.md` contains ZERO bracket placeholders `[...]`.
6. `.env` is in `.gitignore` — NEVER commit real credentials. `src/.env.example` must contain all required variable keys.

---

## 6. End-to-End Deterministic Scenario: `DEMAND_SPIKE_PLUS_RENEWABLE_DROP`

The final integration test must prove the full pipeline on this scenario:
1. **Replay Step:** Load historical OpenSTEF 2024 timestamp.
2. **Forecasting:** LightGBM predicts +18% demand spike over next 30 min. XGBoost classifies severity: `Severe Spike`.
3. **Renewables:** LightGBM predicts 42 MW solar, but actual output drops to 19 MW. Isolation Forest flags anomaly (Score 0.88).
4. **Root Cause:** XGBoost + SHAP isolates `cloud_cover` with 84% confidence.
5. **Optimization:** OR-Tools solves MILP model: dispatches 15 MW battery storage, shifts 8 MW flexible industrial load, balances grid stress from 0.89 to 0.42.
6. **Operator Brief:** Bob / watsonx generates concise 8-section incident report with actionable recommendations.
7. **UI:** React dashboard updates live with telemetry, comparison charts, and AI chat explanation.
