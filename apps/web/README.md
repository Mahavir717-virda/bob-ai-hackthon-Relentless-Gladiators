# `apps/web` — Operator Dashboard Shell

## Module Overview
The presentation layer for GridPilot AI. Provides a real-time command center interface for power grid operators managing renewable integration, demand spikes, and battery dispatch.

- **Technology Stack:** React, Tailwind CSS, Recharts / Plotly
- **Architectural Rule (Rule D):** Presentation logic only. Consumes typed REST/SSE endpoints from `apps/api`. Never embeds ML inferences, optimization algorithms, or physical calculations.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`

## Planned Directory Structure
```text
apps/web/
├── public/
├── src/
│   ├── components/       # Reusable UI widgets (telemetry cards, charts, alerts)
│   ├── pages/            # Command Center, Forecasting, Renewables, Optimization
│   ├── hooks/            # Data-fetching hooks (polling / SSE)
│   ├── services/         # Typed API client
│   ├── styles/           # Tailwind / CSS stylesheets
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── tsconfig.json
```
