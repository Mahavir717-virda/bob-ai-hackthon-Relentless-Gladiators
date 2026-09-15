# `apps/api` — API Gateway & Controller

## Module Overview
The central backend gateway for GridPilot AI. Handles external client requests, orchestrates calls to analytical services, exposes REST & SSE endpoints, and mounts the Model Context Protocol (MCP) server for IBM Bob integration.

- **Technology Stack:** Node.js, TypeScript, Express / Fastify
- **Architectural Boundary:** Orchestrates requests, enforces shared contracts (`shared/contracts`), validates payloads, and delegates predictions to ML services and decisions to the optimization engine.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`

## Endpoints Roadmap
- `/api/grid` — Current 15-minute grid state and telemetry
- `/api/forecast` — Demand forecasts and spike risk classifications
- `/api/renewable` — Asset performance, anomaly status, and root-cause explanations
- `/api/optimization` — Dispatched scenarios, battery schedules, load-shifting recommendations
- `/api/scenario` — Deterministic incident replay scenarios
- `/api/agent` — Operator copilot interactions and automated brief generation

## MCP Server Integration
Exposes MCP tools (`get_current_grid_state`, `get_demand_forecast`, `run_optimization`, etc.) for direct invocation by IBM Bob CLI and watsonx.ai.
