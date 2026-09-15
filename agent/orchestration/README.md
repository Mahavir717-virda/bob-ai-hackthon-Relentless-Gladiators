# `agent/orchestration` — Agent Workflow & Execution Orchestration

## Module Overview
Coordinates multi-step tool calls, event-driven agent tasks, and automated incident response workflows.

- **Key Responsibilities:**
  1. Automated 15-minute cron execution (`bob run` headless brief generation).
  2. Sequential tool execution pipeline: State → Forecast → Anomaly → Optimizer → Brief.
  3. Safe fallback handling if upstream ML or optimizer services fail.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
