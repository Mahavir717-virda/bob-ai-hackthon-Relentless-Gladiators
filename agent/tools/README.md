# `agent/tools` — Agent Tool Registrations & MCP Tools

## Module Overview
Defines tools and functions exposed to the IBM Bob agent copilot and watsonx.ai orchestrator.

- **Standard Tools:**
  1. `get_current_grid_state()` — Fetches real-time 15-minute load, solar, wind, and battery SOC.
  2. `get_demand_forecast(zoneId, horizon)` — Queries LightGBM forecast and XGBoost spike probability.
  3. `get_renewable_status(assetId?)` — Returns solar/wind output and performance ratio.
  4. `get_renewable_anomalies()` — Returns assets flagged by Isolation Forest.
  5. `analyze_root_cause(assetId)` — Retrieves XGBoost+SHAP diagnostic explanation.
  6. `run_optimization(scenarioId)` — Triggers OR-Tools MILP optimization and returns feasible dispatch.
  7. `simulate_action(actionParams)` — Evaluates prospective operator actions without altering state.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
