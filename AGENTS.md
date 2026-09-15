# AGENTS.md

Please refer to [agent.md](file:///f:/bob-ai-hackthon-Relentless-Gladiators/agent.md) for full project context, hackathon submission guidelines, IBM Bob integration specifications, and engineering constraints.

---

## Engineering Boundaries & Agent Ground Rules

### 1. The 4 Non-Negotiable Architectural Rules
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
   - React + Tailwind + Recharts. Purely consumes typed REST/SSE endpoints. No embedded ML, optimization, or physics calculations.

### 2. 4-Member Ownership Boundaries
- **Member 1 (Team Leader):** `apps/api/**`, `apps/web/**`, `agent/**`, `shared/contracts/**`, `shared/types/**`, `tests/integration/**`, `docs/**`, `.env.example`, `submission.yaml`. (Branch: `leader/integration`)
- **Member 2:** `services/data/**`, `services/forecasting/**`, `ml/models/demand/**`, `ml/experiments/demand/**`. (Branch: `member/data-forecast`)
- **Member 3:** `services/renewable/**`, `ml/models/renewable/**`, `ml/experiments/renewable/**`. (Branch: `member/renewable-intelligence`)
- **Member 4:** `services/optimization/**`, `ml/experiments/optimization/**`. (Branch: `member/grid-optimization`)

### 3. Agent Tool Protocol
When interacting with IBM Bob or agent runtimes, invoke tools registered under `agent/tools` and never bypass the analytical pipeline.
