# How to Contribute & Engineering Boundaries

Follow these steps for both team development workflow and final hackathon submission.

---

## 1. 4-Member Ownership Boundaries & Git Workflow

To prevent merge collisions and preserve engineering boundaries, each team member owns a specific branch and directory subset:

| Member | Role | Dedicated Branch | Owned Directories |
| :--- | :--- | :--- | :--- |
| **Member 1 (Leader)** | System Architect, API Gateway, Frontend, LLM/Agent, Contracts | `leader/integration` | `apps/api/**`, `apps/web/**`, `agent/**`, `shared/contracts/**`, `shared/types/**`, `tests/integration/**`, `docs/**`, `docker-compose.yml`, `.env.example`, `submission.yaml` |
| **Member 2** | Data + Demand Forecasting | `member/data-forecast` | `services/data/**`, `services/forecasting/**`, `ml/models/demand/**`, `ml/experiments/demand/**` |
| **Member 3** | Renewable Intelligence | `member/renewable-intelligence` | `services/renewable/**`, `ml/models/renewable/**`, `ml/experiments/renewable/**` |
| **Member 4** | Grid Optimization | `member/grid-optimization` | `services/optimization/**`, `ml/experiments/optimization/**` |

### Prohibited Overlaps & Branch Rules
- Only **Member 1 (Team Leader)** modifies `shared/contracts/**`, `shared/types/**`, `package.json`, `tsconfig.json`, `docker-compose.yml`, and `agent.md`.
- No team member commits directly to `main`.
- All feature work is submitted via Pull Request into `leader/integration`.
- All PRs must verify contract conformance and test execution prior to merging.

---

## 2. The 4 Non-Negotiable Architectural Rules

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

## 3. How to Submit Your Hackathon Entry

### Step 1 — Verify Invariants
1. Click the **"Use this template"** button or use the team repository: `bob-ai-hackathon-[team-name]`.
2. Confirm repository visibility is **Public**.

### Step 2 — Fill in the Required Files
- **`submission.yaml`**: Complete every field marked `# REQUIRED`.
- **`README.md`**: No placeholder brackets remain.
- **`docs/`**: Complete `problem-statement.md`, `solution-overview.md`, `architecture.md`, and `setup-guide.md`.
- **`demo/`**:
  - `demo/demo-video-link.txt`: Video URL (3–5 min showing live pipeline).
  - `demo/live-demo-url.txt`: Deployed demo URL (or "NOT DEPLOYED").
  - `demo/screenshots/`: Minimum 3 screenshots (`01-*.png`, `02-*.png`, `03-*.png`).
- **`presentation/`**: Slide deck present as `presentation/slides.pdf`.

### Step 3 — Verify Validation Passes
Ensure the automated GitHub Action **Validate Submission** passes (green checkmark).

---

## 4. Checklist Before Final Submission

- [ ] `submission.yaml` — all required fields filled
- [ ] `README.md` — no `[placeholder]` text remaining
- [ ] `docs/setup-guide.md` — verified on a clean machine
- [ ] `shared/contracts` — contracts validated and unchanged by non-leads
- [ ] `demo/demo-video-link.txt` — valid public video URL
- [ ] `demo/screenshots/` — at least 3 screenshots
- [ ] `presentation/slides.pdf` — slide deck present
- [ ] GitHub Actions **Validate Submission** is green
- [ ] Repository is **Public**
