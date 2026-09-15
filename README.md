# 🚀 GridPilot AI — Grid Load Optimisation & Renewable Energy Performance Advisor

> AI-driven decision-support platform enabling power grid operators to forecast renewable volatility, detect demand spikes, and mathematically optimize battery dispatch and curtailment mitigation.

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Relentless Gladiators |
| **Track** | AI |
| **Team Lead** | Mahavir Virda — 24ce142@charusat.edu.in |
| **Members** | Deep pathak (24ce095@charusat.edu.in), Savan Patel (24aiml060@charusat.edu.in), Tirth Savan (24aiml046@charusat.edu.in) |

---

## 🎯 Problem Statement

Power grid operators face unprecedented volatility with renewable integration: sudden demand surges, weather-driven renewable drops, and inefficient asset curtailment. Traditional SCADA and monitoring systems lack unified predictive diagnostics and constraint-aware mathematical optimization, causing critical grid stress and clean energy waste.

---

## 💡 Solution

GridPilot AI is an operator decision-support system coupling machine learning forecasting (LightGBM demand, solar, and wind models; XGBoost spike detection; Isolation Forest anomaly tracking) with Google OR-Tools Mixed-Integer Linear Programming (MILP). It translates complex grid telemetry into actionable 15-minute operator briefs and interactive natural language actions powered by local Qwen 2.5 (Ollama) and IBM Bob.

---

## ✨ Key Features

- **High-Frequency Forecasting:** 15, 30, and 60-minute electricity demand, solar generation, and wind output forecasting using LightGBM.
- **Spike & Anomaly Diagnostics:** Multi-class demand spike detection via XGBoost and asset anomaly tracking via Isolation Forest with SHAP root-cause explainability.
- **Constraint-Aware Optimization:** Mathematical MILP optimization using Google OR-Tools for battery energy storage system (BESS) dispatch and industrial flexible load shifting.
- **IBM Bob Shell & Local LLM Integration:** Custom Model Context Protocol (MCP) server enabling IBM Bob and local Qwen 2.5 to query grid telemetry, run optimizations, and synthesize 8-part operator briefs.
- **Interactive Operator Command Center:** Real-time visual telemetry, before/after load balancing comparison, and decision-support dashboard.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, TypeScript, JavaScript |
| **Frameworks** | FastAPI, React, Express, Node.js |
| **Local LLM & Agent** | Qwen 2.5 (Ollama), IBM Bob (BobShell CLI) |
| **Databases & Math** | PostgreSQL, Google OR-Tools (MILP / SCIP) |
| **ML & Analytics** | LightGBM, XGBoost, Scikit-learn, SHAP, Pandas |
| **Other** | Docker, Git, Model Context Protocol (MCP) |

---

## 📁 Repository Structure

```text
├── apps/
│   ├── api/              # Node.js/TypeScript API Gateway & MCP Server mounting
│   └── web/              # React + Tailwind + Recharts Operator Dashboard
├── services/
│   ├── data/             # Ingestion & preprocessing (OpenSTEF Liander, PV, Wind)
│   ├── forecasting/      # LightGBM demand forecast & XGBoost spike classification
│   ├── renewable/        # Solar/wind generation, Isolation Forest, XGBoost+SHAP
│   └── optimization/     # Google OR-Tools MILP grid balance & curtailment engine
├── agent/
│   ├── provider/         # Local Qwen 2.5 (Ollama) & Bob LLM provider abstraction
│   ├── tools/            # Model Context Protocol (MCP) tools & function registry
│   ├── prompts/          # 8-part operator brief & copilot structured prompts
│   ├── orchestration/    # Headless 15-min incident workflows (`bob run`)
│   └── policies/         # Guardrails (no hallucinations, no LLM math dispatch)
├── shared/
│   ├── contracts/        # Immutable TypeScript schemas (Demand, Renewable, Optimization)
│   ├── types/            # Domain entities, asset types, and status enums
│   ├── constants/        # Physical units (MW/MWh), 15-min horizons, thresholds
│   └── errors/           # Standardized application and service error schemas
├── database/
│   ├── schema/           # PostgreSQL relational DDL
│   ├── migrations/       # Timestamped reversible database migrations
│   └── seed/             # Deterministic scenario fixtures (DEMAND_SPIKE_PLUS_RENEWABLE_DROP)
├── ml/
│   ├── datasets/         # Cleaned feature stores and validation splits
│   ├── models/           # Exported checkpoints and metadata registry
│   └── experiments/      # Training notebooks, baseline evaluations, SHAP plots
├── tests/
│   ├── integration/      # Contract conformance & deterministic scenario replays
│   └── e2e/              # Full-stack smoke and Bob MCP interaction suites
├── docs/                 # Hackathon deliverables, architecture, setup guide
├── scripts/              # Developer tooling, Bob MCP setup, verification scripts
├── demo/                 # Screenshots, demo video links, live URL
├── presentation/         # Hackathon slide deck
├── AGENTS.md             # Multi-agent coordination and architectural boundaries
├── agent.md              # Master operational context & hackathon guidelines
├── CONTRIBUTING.md       # Ownership boundaries, branch rules, and PR workflow
├── .env.example          # Environment configuration template
└── submission.yaml       # Hackathon submission metadata
```


---

## ⚡ How to Run

```bash
# 1. Clone the repo
git clone https://github.com/Mahavir717-virda/bob-ai-hackthon-Relentless-Gladiators.git
cd bob-ai-hackthon-Relentless-Gladiators

# 2. Install dependencies
pip install -r src/requirements.txt

# 3. Configure environment
cp src/.env.example .env

# 4. Run the project API
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

---

## ⚠️ Known Limitations

- Real-time resolution is currently scoped to 15-minute intervals up to 60-minute horizons based on OpenSTEF Liander topology.
- Grid topology assumes single-zone substation balancing; multi-regional transactive energy trading is planned for future phases.
- Hardware battery telemetry is simulated using empirical battery degradation models.

---

## 🏅 What We're Most Proud Of

The clean separation of concerns between predictive machine learning, mathematical constraint optimization (OR-Tools), and communicative generative AI (IBM Bob & local Qwen 2.5). The LLM never hallucinates dispatch numbers; it explains mathematically verified and physically feasible dispatch recommendations.
