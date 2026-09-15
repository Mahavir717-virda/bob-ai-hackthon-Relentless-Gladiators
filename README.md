# 🚀 GridPilot AI — Grid Load Optimisation & Renewable Energy Performance Advisor

> AI-driven decision-support platform enabling power grid operators to forecast renewable volatility, detect demand spikes, and mathematically optimize battery dispatch and curtailment mitigation.

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Relentless Gladiators |
| **Track** | AI |
| **Team Lead** | Mahavir Virda — 24ce142@charusat.edu.in |
| **Members** | Deep Patel (24ce095@charusat.edu.in), Savan Patel (24aiml060@charusat.edu.in), Tirth Patel (24aiml046@charusat.edu.in) |

---

## 🎯 Problem Statement

Power grid operators face unprecedented volatility with renewable integration: sudden demand surges, weather-driven renewable drops, and inefficient asset curtailment. Traditional SCADA and monitoring systems lack unified predictive diagnostics and constraint-aware mathematical optimization, causing critical grid stress and clean energy waste.

---

## 💡 Solution

GridPilot AI is an operator decision-support system coupling machine learning forecasting (LightGBM demand, solar, and wind models; XGBoost spike detection; Isolation Forest anomaly tracking) with Google OR-Tools Mixed-Integer Linear Programming (MILP). It translates complex grid telemetry into actionable 15-minute operator briefs and interactive natural language actions powered by IBM watsonx.ai and IBM Bob.

---

## ✨ Key Features

- **High-Frequency Forecasting:** 15, 30, and 60-minute electricity demand, solar generation, and wind output forecasting using LightGBM.
- **Spike & Anomaly Diagnostics:** Multi-class demand spike detection via XGBoost and asset anomaly tracking via Isolation Forest with SHAP root-cause explainability.
- **Constraint-Aware Optimization:** Mathematical MILP optimization using Google OR-Tools for battery energy storage system (BESS) dispatch and industrial flexible load shifting.
- **IBM Bob Shell & watsonx.ai Integration:** Custom Model Context Protocol (MCP) server enabling IBM Bob to query grid telemetry, run optimizations, and synthesize 8-part operator briefs.
- **Interactive Operator Command Center:** Real-time visual telemetry, before/after load balancing comparison, and decision-support dashboard.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, TypeScript, JavaScript |
| **Frameworks** | FastAPI, React, Express, Node.js |
| **IBM Technologies** | IBM watsonx.ai (Granite 3.0), IBM Bob (BobShell CLI) |
| **Databases & Math** | PostgreSQL, Google OR-Tools (MILP / SCIP) |
| **ML & Analytics** | LightGBM, XGBoost, Scikit-learn, SHAP, Pandas |
| **Other** | Docker, Git, Model Context Protocol (MCP) |

---

## 📁 Repository Structure

```
├── src/                  # All source code (FastAPI gateway, ML models, optimizer, MCP server)
├── docs/                 # Written documentation
│   ├── problem-statement.md
│   ├── solution-overview.md
│   ├── architecture.md
│   └── setup-guide.md
├── demo/                 # Demo artifacts
│   ├── screenshots/      # App screenshots
│   └── demo-video-link.txt  # Link to demo video
├── presentation/         # Slide deck
├── agent.md              # AI agent operational guidelines and contracts
└── submission.yaml       # Structured submission metadata
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

The clean separation of concerns between predictive machine learning, mathematical constraint optimization (OR-Tools), and communicative generative AI (IBM Bob & watsonx.ai). The LLM never hallucinates dispatch numbers; it explains mathematically verified and physically feasible dispatch recommendations.
